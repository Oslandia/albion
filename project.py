# coding = utf-8

from pglite import cluster_params
import psycopg2
import os
import sys
import atexit
from shapely import wkb
from dxfwrite import DXFEngine as dxf

from pglite import start_cluster, stop_cluster, init_cluster, check_cluster, cluster_params, export_db, import_db

if not check_cluster():
    init_cluster()
start_cluster()
#atexit.register(stop_cluster)

def find_in_dir(dir_, name):
    for filename in os.listdir(dir_):
        if filename.find(name) != -1:
            return os.path.join(dir_, filename)
    return ""

class DummyProgress(object):
    def __init__(self):
        sys.stdout.write('\n')
        self.setPercent(0)

    def __del__(self):
        sys.stdout.write('\n')

    def setPercent(self, percent):
        l = 50
        sys.stdout.write('\r|' + '#'*int(l*float(percent)/100) + ' '*int(l*float(100-percent)/100) + '|')
        sys.stdout.flush()

class ProgressBar(object):
    def __init__(self, progress_bar):
        self.__bar = progress_bar
        self.__bar.setMaximum(100)
        self.setPercent(0)

    def setPercent(self, percent):
        self.__bar.setValue(int(percent))

class Project(object):

    def __init__(self, project_name):
        #assert Project.exists(project_name)
        self.__name = project_name
        self.__conn_info = "dbname={} {}".format(project_name, cluster_params())

    def connect(self):
        return psycopg2.connect(self.__conn_info)


    @staticmethod
    def exists(project_name):
        with psycopg2.connect("dbname=postgres {}".format(cluster_params())) as con:
            cur = con.cursor()
            con.set_isolation_level(0)
            cur.execute("select pg_terminate_backend(pg_stat_activity.pid) \
                        from pg_stat_activity \
                        where pg_stat_activity.datname = '{}'".format(project_name))
            
            cur.execute("select count(1) from pg_catalog.pg_database where datname='{}'".format(project_name))
            res = cur.fetchone()[0] == 1
            return res

    @staticmethod
    def delete(project_name):
        assert(Project.exists(project_name))
        with psycopg2.connect("dbname=postgres {}".format(cluster_params())) as con:
            cur = con.cursor()
            con.set_isolation_level(0)
            cur.execute("select pg_terminate_backend(pg_stat_activity.pid) \
                        from pg_stat_activity \
                        where pg_stat_activity.datname = '{}'".format(project_name))
            cur.execute("drop database if exists {}".format(project_name))
            
            cur.execute("select count(1) from pg_catalog.pg_database where datname='{}'".format(project_name))
            con.commit()

    @staticmethod
    def create(project_name, srid):
        assert(not Project.exists(project_name))

        print "create database", project_name
        with psycopg2.connect("dbname=postgres {}".format(cluster_params())) as con:
            cur = con.cursor()
            con.set_isolation_level(0)
            cur.execute("create database {}".format(project_name))
            con.commit()

        project = Project(project_name)
        with project.connect() as con:
            cur = con.cursor()
            cur.execute("create extension postgis")
            cur.execute("create extension plpython3u")
            for file_ in ('_albion.sql', 'albion.sql'):
                for statement in open(os.path.join(os.path.dirname(__file__), file_)).read().split('\n;\n')[:-1]:
                    cur.execute(statement.replace('$SRID', str(srid)))
            con.commit()
        return project


    def update(self):
        "reload schema albion without changing data"
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            cur.execute("drop schema if exists albion cascade")
            for statement in open(os.path.join(os.path.dirname(__file__), 'albion.sql')).read().split('\n;\n')[:-1]:
                #print statement.replace('$SRID', str(srid))
                cur.execute(statement.replace('$SRID', str(srid)))
            con.commit()

    def __getattr__(self, name):
        if name == "has_collar":
            return self.__has_collar()
        elif name == "has_hole":
            return self.__has_hole()
        elif name == "has_section":
            return self.__has_section()
        elif name == "has_group_cell":
            return self.__has_group_cell()
        elif name == "has_radiometry":
            return self.__has_radiometry()
        elif name == "has_cell":
            return self.__has_cell()
        elif name == "name":
            return self.__name
        else:
            raise AttributeError(name)

    def __has_cell(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select count(1) from albion.cell")
            return cur.fetchone()[0] > 1

    def __has_collar(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select count(1) from albion.collar")
            return cur.fetchone()[0] > 1

    def __has_hole(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select count(1) from albion.hole")
            return cur.fetchone()[0] > 1

    def __has_section(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select count(1) from albion.section_geom")
            return cur.fetchone()[0] > 1

    def __has_group_cell(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select count(1) from albion.group_cell")
            return cur.fetchone()[0] > 1

    def __has_radiometry(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select count(1) from albion.radiometry")
            return cur.fetchone()[0] > 1

    def import_data(self, dir_, progress=None):
        progress = progress if progress is not None else DummyProgress()
        with self.connect() as con:
            cur = con.cursor()

            cur.execute("""
                copy _albion.collar(id, x, y, z, date_, comments) from '{}' delimiter ';' csv header 
                """.format(find_in_dir(dir_, 'collar')))
            
            progress.setPercent(5)
            
            cur.execute("""
                update _albion.collar set geom=format('SRID=%s;POINTZ(%s %s %s)',m. srid, x, y, z)::geometry
                from albion.metadata as m
                """)

            cur.execute("""
                insert into _albion.hole(id, collar_id) select id, id from _albion.collar;
                """)

            progress.setPercent(10)

            cur.execute("""
                copy _albion.deviation(hole_id, from_, dip, azimuth) from '{}' delimiter ';' csv header
                """.format(find_in_dir(dir_, 'devia')))

            progress.setPercent(15)

            if find_in_dir(dir_, 'avp'):
                cur.execute("""
                    copy _albion.radiometry(hole_id, from_, to_, gamma) from '{}' delimiter ';' csv header
                    """.format(find_in_dir(dir_, 'avp')))

            progress.setPercent(20)

            if find_in_dir(dir_, 'formation'):
                cur.execute("""
                    copy _albion.formation(hole_id, from_, to_, code, comments) from '{}' delimiter ';' csv header
                    """.format(find_in_dir(dir_, 'formation')))

            progress.setPercent(25)

            if find_in_dir(dir_, 'lithology'):
                cur.execute("""
                    copy _albion.lithology(hole_id, from_, to_, code, comments) from '{}' delimiter ';' csv header
                    """.format(find_in_dir(dir_, 'lithology')))

            progress.setPercent(30)

            if find_in_dir(dir_, 'facies'):
                cur.execute("""
                    copy _albion.facies(hole_id, from_, to_, code, comments) from '{}' delimiter ';' csv header
                    """.format(find_in_dir(dir_, 'facies')))

            progress.setPercent(35)

            if find_in_dir(dir_, 'resi'):
                cur.execute("""
                    copy _albion.resistivity(hole_id, from_, to_, rho) from '{}' delimiter ';' csv header
                    """.format(find_in_dir(dir_, 'resi')))

            progress.setPercent(40)

            cur.execute("""
                with dep as (
                    select hole_id, max(to_) as mx
                        from (
                            select hole_id, max(to_) as to_ from _albion.radiometry group by hole_id
                            union all
                            select hole_id, max(to_) as to_ from _albion.resistivity group by hole_id
                            union all
                            select hole_id, max(to_) as to_ from _albion.formation group by hole_id
                            union all
                            select hole_id, max(to_) as to_ from _albion.lithology group by hole_id
                            union all
                            select hole_id, max(to_) as to_ from _albion.facies group by hole_id
                            ) as t
                    group by hole_id
                )
                update _albion.hole as h set depth_=d.mx
                from dep as d where h.id=d.hole_id
                """)

            progress.setPercent(50)

            cur.execute("update albion.hole set geom=albion.hole_geom(id)")

            progress.setPercent(55)

            cur.execute("update albion.resistivity set geom=albion.hole_piece(from_, to_, hole_id)")

            progress.setPercent(60)

            cur.execute("update albion.formation set geom=albion.hole_piece(from_, to_, hole_id)")

            progress.setPercent(65)

            cur.execute("update albion.radiometry set geom=albion.hole_piece(from_, to_, hole_id)")

            progress.setPercent(70)

            cur.execute("update albion.lithology set geom=albion.hole_piece(from_, to_, hole_id)")

            progress.setPercent(75)

            cur.execute("update albion.facies set geom=albion.hole_piece(from_, to_, hole_id)")

            #progress.setPercent(80)

            #cur.execute("update albion.mineralization set geom=albion.hole_piece(from_, to_, hole_id)")

            progress.setPercent(100)

            con.commit()

    def triangulate(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select albion.triangulate()")
            con.commit()

    def refresh_all_edge(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("refresh materialized view albion.all_edge")
            con.commit()

    def create_sections(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("refresh materialized view albion.section_geom")
            cur.execute("refresh materialized view albion.radiometry_section")
            cur.execute("refresh materialized view albion.resistivity_section")
            con.commit()

    def execute_script(self, file_):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            for statement in open(file_).read().split('\n;\n')[:-1]:
                #print statement.replace('$SRID', str(srid))
                cur.execute(statement.replace('$SRID', str(srid)))
            con.commit()
        
    def new_graph(self, graph, parent=None):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("delete from albion.graph cascade where id='{}';".format(graph))
            if parent:
                cur.execute("insert into albion.graph(id, parent) values ('{}', '{}');".format(graph, parent))
            else:
                cur.execute("insert into albion.graph(id) values ('{}');".format(graph))
            con.commit()

    def delete_graph(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("delete from albion.graph cascade where id='{}';".format(graph))

    def previous_section(self, section):    
        if not section:
            return
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("""
                select group_id from albion.section where id='{}'
                """.format(section))
            group, = cur.fetchone()
            group = group or 0
            cur.execute("""
                select group_id, geom from albion.section_geom
                where section_id='{section}'
                and group_id < {group}
                order by group_id desc
                limit 1
                """.format(group=group, section=section))
            res = cur.fetchone()
            if res:
                sql = ("""
                    update albion.section set group_id={}, geom='{}'::geometry where id='{}'
                    """.format(res[0], res[1], section))
            else:
                sql = ("""
                    update albion.section set group_id=null, geom=albion.first_section(anchor) where id='{}'
                    """.format(section))
            cur.execute(sql)
            con.commit()

    def next_section(self, section):    
        if not section:
            return
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("""
                select group_id from albion.section where id='{}'
                """.format(section))
            group, = cur.fetchone()
            group = group or 0
            cur.execute("""
                select group_id, geom from albion.section_geom
                where section_id='{section}'
                and group_id > {group}
                order by group_id asc
                limit 1
                """.format(group=group, section=section))
            res = cur.fetchone()
            if res:
                sql = ("""
                    update albion.section set group_id={}, geom='{}'::geometry where id='{}'
                    """.format(res[0], res[1], section))
                cur.execute(sql)
                con.commit()

    def next_group_ids(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("""
                select cell_id from albion.next_group where section_id='{}'
                """.format(self.__current_section.currentText()))
            return [cell_id for cell_id, in cur.fetchall()]

    def create_group(self, section, ids):
        with self.connect() as con:
            # add group
            cur = con.cursor()
            cur.execute("""
                insert into albion.group default values returning id
                """)
            group, = cur.fetchone()
            print "new group", group
            cur.executemany("""
                insert into albion.group_cell(section_id, cell_id, group_id) values(%s, %s, %s)
                """,
                ((section, id_, group) for id_ in ids))
            con.commit()

    def sections(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select id from albion.section")
            return [id_ for id_, in cur.fetchall()]

    def graphs(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select id from albion.graph")
            return [id_ for id_, in cur.fetchall()]

    def compute_mineralization(self, cutoff, ci, oc):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("delete from albion.mineralization where level_={}".format(cutoff))
            cur.execute("""
                insert into albion.mineralization(hole_id, level_, from_, to_, oc, accu, grade)
                select hole_id, (t.r).level_, (t.r).from_, (t.r).to_, (t.r).oc, (t.r).accu, (t.r).grade
                from (
                select hole_id, albion.segmentation(
                    array_agg(gamma order by from_),array_agg(from_ order by from_),  array_agg(to_ order by from_), 
                    {ci}, {oc}, {cutoff}) as r
                from albion.radiometry
                group by hole_id
                ) as t
                """.format(oc=oc, ci=ci, cutoff=cutoff))
            cur.execute("""
                update albion.mineralization set geom=albion.hole_piece(from_, to_, hole_id)
                where geom is null
                """)
            con.commit() 
            

    def export_obj(self, graph_id, filename):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("""
                select albion.to_obj(st_collectionhomogenize(st_collect(geom)))
                from albion.dynamic_volume
                where graph_id='{}'
                and geom is not null --not st_isempty(geom)
                """.format(graph_id))
            open(filename, 'w').write(cur.fetchone()[0])

    def export_dxf(self, graph_id, filename):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("""
                select st_collectionhomogenize(st_collect(triangulation))
                from albion.volume
                where graph_id='{}'
                """.format(graph_id))
            drawing = dxf.drawing(filename)
            m = wkb.loads(cur.fetchone()[0], True)
            for p in m:
                r = p.exterior.coords
                drawing.add(dxf.face3d([tuple(r[0]), tuple(r[1]), tuple(r[2])], flags=1))
            drawing.save()

    def create_volumes(self, graph_id):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("""
                delete from albion.volume where graph_id='{}'
                """.format(graph_id))
            cur.execute("""
                insert into albion.volume(graph_id, cell_id, triangulation)
                select graph_id, cell_id, geom
                from albion.dynamic_volume
                where graph_id='{}'
                and geom is not null --not st_isempty(geom)
                """.format(graph_id))
            con.commit()

    def export(self, filename):
        export_db(self.name, filename)

    @staticmethod
    def import_(name, filename):
        import_dw(filename, name)
        return Project(name)

    def create_section_view_0_90(self, z_scale):
        """create default WE and SN section views with magnifications

        we position anchors south and east in order to have the top of
        the section with a 50m margin from the extent of the holes
        """

        with self.connect() as con:
            cur = con.cursor()
            cur.execute("""
                select st_3dextent(geom)
                from albion.hole
                """)
            ext = cur.fetchone()[0].replace('BOX3D(','').replace(')','').split(',')
            ext = [[float(c) for c in ext[0].split()],[float(c) for c in ext[1].split()]]

            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            cur.execute("""
                insert into albion.section(id, anchor, scale)
                values('SN x{z_scale}', 'SRID={srid};LINESTRING({x} {ybottom}, {x} {ytop})'::geometry, {z_scale})
                """.format(
                    z_scale=z_scale, 
                    srid=srid, 
                    x=ext[1][0]+50+z_scale*ext[1][2],
                    ybottom=ext[0][1],
                    ytop=ext[1][1]))

            cur.execute("""
                insert into albion.section(id, anchor, scale)
                values('WE x{z_scale}', 'SRID={srid};LINESTRING({xleft} {y}, {xright} {y})'::geometry, {z_scale})
                """.format(
                    z_scale=z_scale, 
                    srid=srid, 
                    y=ext[0][1]-50-z_scale*ext[1][2],
                    xleft=ext[0][0],
                    xright=ext[1][0]))
            con.commit()


    def closest_hole_id(self, x, y):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            cur.execute("""
                select id from albion.hole
                where st_dwithin(geom, 'SRID={srid} ;POINT({x} {y})'::geometry, 25)
                order by st_distance('SRID={srid} ;POINT({x} {y})'::geometry, geom)
                limit 1""".format(srid=srid, x=x, y=y))
            res = cur.fetchone()
            if not res:
                cur.execute("""
                    select hole_id from albion.current_hole_section
                    where st_dwithin(geom, 'SRID={srid} ;POINT({x} {y})'::geometry, 25)
                    order by st_distance('SRID={srid} ;POINT({x} {y})'::geometry, geom)
                    limit 1""".format(srid=srid, x=x, y=y))
                res = cur.fetchone()

            return res[0] if res else None

    def set_section_geom(self, section_id, geom):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            cur.execute("""
                update albion.section set geom=ST_SetSRID('{wkb_hex}'::geometry, {srid}) where id='{id_}'
                """.format(srid=srid, wkb_hex=geom.wkb_hex, id_=section_id))
            con.commit()


