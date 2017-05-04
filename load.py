# coding = utf-8

import psycopg2

def load_collar(cur, filename, progress):
    cur.execute("""
        select srid from albion.metadata
        """)
    srid, = cur.fetchone()
    with open(filename) as f:
        header = f.readline()
        convert = lambda x: (x[0], float(x[1]),  float(x[2]), float(x[3]), x[4])
        data = [convert(line.rstrip().split(';')) for line in f]
        cur.executemany("""
            insert into albion.collar(id, geom, comments) 
            values (%s, 'SRID={srid}; POINTZ(%s %s %s)'::geometry, %s)
            """.format(srid=srid), data)
        data = [(x[0], x[0]) for x in data]
        # insert one hole for each colar
        cur.executemany("""
            insert into albion.hole(id, collar_id)
            values(%s, %s)
            """, data)

def load_devia(cur, filename, progress=None):
    with open(filename) as f:
        header = f.readline()
        convert = lambda x: (x[0], float(x[1]),  float(x[2]), float(x[3]))
        data = [convert(line.rstrip().split(';')) for line in f]

        # executemany doesn't do mush in psycopg2 (not true in sqlite), so we chunk to perform better
        chunk_size = 1000
        i = 0
        while i < len(data):
            chunk = ','.join([cur.mogrify('(%s,%s,%s,%s)', row) for row in data[i:min(i+chunk_size, len(data))]])
            cur.execute("""
                insert into albion.deviation(hole_id, from_, deep, azimuth) 
                values 
                """ + chunk)
            if progress:
                progress.set_ratio(float(i)/len(data))

            i += chunk_size

        #cur.executemany("""
        #    insert into albion.deviation(hole_id, from_, deep, azimuth) 
        #    values (%s, %s, %s, %s)
        #    """, data)

def load_formation(cur, filename, progress):
    with open(filename) as f:
        header = f.readline()
        convert = lambda x: (x[0], float(x[1]),  float(x[2]), int(x[3]), x[4])
        data = [convert(line.rstrip().split(';')) for line in f]
        cur.executemany("""
            insert into albion.formation(hole_id, from_, to_, code, comments) 
            values (%s, %s, %s, %s, %s)
            """, data)

def load_resi(cur, filename, progress):
    with open(filename) as f:
        header = f.readline()
        convert = lambda x: (x[0], float(x[1]),  float(x[2]), float(x[3]))
        data = [convert(line.rstrip().split(';')) for line in f]

        chunk_size = 1000
        i = 0
        while i < len(data):
            chunk = ','.join([cur.mogrify('(%s,%s,%s,%s)', row) for row in data[i:min(i+chunk_size, len(data))]])
            cur.execute("""
                insert into albion.resistivity(hole_id, from_, to_, rho) 
                values 
                """ + chunk)
            if progress:
                progress.set_ratio(float(i)/len(data))

            i += chunk_size

def load_avp(cur, filename, progress):
    with open(filename) as f:
        header = f.readline()
        convert = lambda x: (x[0], float(x[1]),  float(x[2]), float(x[3]))
        data = [convert(line.rstrip().split(';')) for line in f]

        chunk_size = 1000
        i = 0
        while i < len(data):
            chunk = ','.join([cur.mogrify('(%s,%s,%s,%s)', row) for row in data[i:min(i+chunk_size, len(data))]])
            cur.execute("""
                insert into albion.radiometry(hole_id, from_, to_, gamma) 
                values 
                """ + chunk)
            if progress:
                progress.set_ratio(float(i)/len(data))

            i += chunk_size



def load_file(cur, filename, progress=None):
    if filename.find('collar') != -1:
        load_collar(cur, filename, progress)
    elif filename.find('devia') != -1:
        load_devia(cur, filename, progress)
    elif filename.find('formation') != -1:
        load_formation(cur, filename, progress)
    elif filename.find('resi') != -1:
        load_resi(cur, filename, progress)
    elif filename.find('avp') != -1:
        load_avp(cur, filename, progress)
    else:
        raise RuntimeError('cannot find collar, avp, devia, formation or resi in filename {}'.format(filename))

if __name__ == "__main__":
    import sys

    class ConsoleProgressDisplay(object):
        def __init__(self):
            sys.stdout.write("  0%")
            sys.stdout.flush()

        def set_ratio(self, ratio):
            sys.stdout.write("\b"*4+"% 3d%%"%(int(ratio*100)))
            sys.stdout.flush()

        def __del__(self):
            sys.stdout.write("\b"*4+"100%\n")
            sys.stdout.flush()

   
    con = psycopg2.connect(sys.argv[1])
    cur = con.cursor()
    for filename in sys.argv[2:]:
        progress = ConsoleProgressDisplay()
        load_file(cur, filename, progress)
        del progress

    con.commit()
