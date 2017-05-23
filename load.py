# coding = utf-8

import psycopg2
import StringIO

def load_collar(cur, filename):
    cur.execute("""
        select srid from _albion.metadata
        """)
    srid, = cur.fetchone()
    with open(filename) as f:
        header = f.readline()
        convert = lambda x: (x[0], float(x[1]),  float(x[2]), float(x[3]), x[4])
        data = [convert(line.rstrip().split(';')) for line in f]
        cur.executemany("""
            insert into _albion.collar(id, geom, comments) 
            values (%s, 'SRID={srid}; POINTZ(%s %s %s)'::geometry, %s)
            """.format(srid=srid), data)
        data = [(x[0], x[0]) for x in data]
        # insert one hole for each colar
        cur.executemany("""
            insert into _albion.hole(id, collar_id)
            values(%s, %s)
            """, data)

def load_devia(cur, filename):
    cur.copy_expert("copy _albion.deviation from stdin delimiter ';' csv header", open(filename))

def load_formation(cur, filename):
    cur.copy_expert("copy _albion.formation(hole_id, from_, to_, code, comments) from stdin delimiter ';' csv header", open(filename))

def load_resi(cur, filename):
    cur.copy_expert("copy _albion.resistivity(hole_id, from_, to_, rho) from stdin delimiter ';' csv header", open(filename))

def load_avp(cur, filename):
    cur.copy_expert("copy _albion.radiometry(hole_id, from_, to_, gamma) from stdin delimiter ';' csv header", open(filename))

def load_file(cur, filename):
    if filename.find('collar') != -1:
        load_collar(cur, filename)
    elif filename.find('devia') != -1:
        load_devia(cur, filename)
    elif filename.find('formation') != -1:
        load_formation(cur, filename)
    elif filename.find('resi') != -1:
        load_resi(cur, filename)
    elif filename.find('avp') != -1:
        load_avp(cur, filename)
    else:
        raise RuntimeError('cannot find collar, avp, devia, formation or resi in filename {}'.format(filename))

if __name__ == "__main__":
    import sys

    con = psycopg2.connect(sys.argv[1])
    cur = con.cursor()
    for filename in sys.argv[2:]:
        print("loading {}...".format(filename))
        load_file(cur, filename)

    con.commit()
