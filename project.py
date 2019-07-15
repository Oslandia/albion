# coding = utf-8

from builtins import str
from builtins import object
from pglite import cluster_params
import psycopg2
import os
import sys
import atexit
import binascii
import string
from shapely import wkb
from dxfwrite import DXFEngine as dxf

from pglite import (
    start_cluster,
    stop_cluster,
    init_cluster,
    check_cluster,
    cluster_params,
    export_db,
    import_db,
)

from builtins import bytes

from qgis.core import QgsMessageLog

import time
from psycopg2.extras import LoggingConnection, LoggingCursor
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
# MyLoggingCursor simply sets self.timestamp at start of each query
class MyLoggingCursor(LoggingCursor):
    def execute(self, query, vars=None):
        self.timestamp = time.time()
        return super(MyLoggingCursor, self).execute(query, vars)

    def callproc(self, procname, vars=None):
        self.timestamp = time.time()
        return super(MyLoggingCursor, self).callproc(procname, vars)

# MyLogging Connection:
#   a) calls MyLoggingCursor rather than the default
#   b) adds resulting execution (+ transport) time via filter()
class MyLoggingConnection(LoggingConnection):
    def filter(self, msg, curs):
        return "{} {} ms".format(msg, int((time.time() - curs.timestamp) * 1000))

    def cursor(self, *args, **kwargs):
        kwargs.setdefault('cursor_factory', MyLoggingCursor)
        return LoggingConnection.cursor(self, *args, **kwargs)


if not check_cluster():
    init_cluster()
start_cluster()

#atexit.register(stop_cluster)
TABLES = [
    {'NAME': 'radiometry',
     'FIELDS_DEFINITION': 'gamma real',
     'FIELDS': 'gamma',
     },
    {'NAME': 'resistivity',
     'FIELDS_DEFINITION': 'rho real',
     'FIELDS': 'rho',
     },
    {'NAME': 'formation',
     'FIELDS_DEFINITION': 'code integer, comments varchar',
     'FIELDS': 'code, comments',
     },
    {'NAME': 'lithology',
     'FIELDS_DEFINITION': 'code integer, comments varchar',
     'FIELDS': 'code, comments',
     },
    {'NAME': 'facies',
     'FIELDS_DEFINITION': 'code integer, comments varchar',
     'FIELDS': 'code, comments',
     },
    {'NAME': 'chemical',
     'FIELDS_DEFINITION': 'num_sample varchar, element varchar, thickness real, gt real, grade real, equi real, comments varchar',
     'FIELDS': 'num_sample, element, thickness, gt, grade, equi, comments',
     },
    {'NAME': 'mineralization',
     'FIELDS_DEFINITION': 'level_ real, oc real, accu real, grade real, comments varchar',
     'FIELDS': 'level_, oc, accu, grade, comments'
     }]


def find_in_dir(dir_, name):
    for filename in os.listdir(dir_):
        if filename.find(name) != -1:
            return os.path.abspath(os.path.join(dir_, filename))
    return ""


class DummyProgress(object):
    def __init__(self):
        sys.stdout.write("\n")
        self.setPercent(0)

    def __del__(self):
        sys.stdout.write("\n")

    def setPercent(self, percent):
        l = 50
        a = int(round(l * float(percent) / 100))
        b = l - a
        sys.stdout.write("\r|" + "#" * a + " " * b + "| % 3d%%" % (percent))
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
        # assert Project.exists(project_name)
        self.__name = project_name
        self.__conn_info = "dbname={} {}".format(project_name, cluster_params())

    def connect(self):
        con = psycopg2.connect(self.__conn_info, connection_factory=MyLoggingConnection)
        con.initialize(logger)
        return con

    def vacuum(self):
        with self.connect() as con:
            old_isolation_level = con.isolation_level
            con.set_isolation_level(0)
            cur = con.cursor()
            cur.execute("vacuum analyze")
            con.commit()

    @staticmethod
    def exists(project_name):
        with psycopg2.connect("dbname=postgres {}".format(cluster_params())) as con:
            cur = con.cursor()
            con.set_isolation_level(0)
            cur.execute(
                "select pg_terminate_backend(pg_stat_activity.pid) \
                        from pg_stat_activity \
                        where pg_stat_activity.datname = '{}'".format(
                    project_name
                )
            )

            cur.execute(
                "select count(1) from pg_catalog.pg_database where datname='{}'".format(
                    project_name
                )
            )
            res = cur.fetchone()[0] == 1
            return res

    @staticmethod
    def delete(project_name):
        assert Project.exists(project_name)
        with psycopg2.connect("dbname=postgres {}".format(cluster_params())) as con:
            cur = con.cursor()
            con.set_isolation_level(0)
            cur.execute(
                "select pg_terminate_backend(pg_stat_activity.pid) \
                        from pg_stat_activity \
                        where pg_stat_activity.datname = '{}'".format(
                    project_name
                )
            )
            cur.execute("drop database if exists {}".format(project_name))

            cur.execute(
                "select count(1) from pg_catalog.pg_database where datname='{}'".format(
                    project_name
                )
            )
            con.commit()

    @staticmethod
    def create(project_name, srid):
        assert not Project.exists(project_name)

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
            cur.execute("create extension hstore")
            cur.execute("create extension hstore_plpython3u")
            include_elementary_volume = open(
                os.path.join(
                    os.path.dirname(__file__), "elementary_volume", "__init__.py"
                )
            ).read()
            for file_ in ("_albion.sql", "albion.sql"):
                for statement in (
                    open(os.path.join(os.path.dirname(__file__), file_))
                    .read()
                    .split("\n;\n")[:-1]
                ):
                    cur.execute(
                        statement.replace("$SRID", str(srid)).replace(
                            "$INCLUDE_ELEMENTARY_VOLUME", include_elementary_volume
                        )
                    )

            for table in TABLES:
                table['SRID'] = srid
                self.add_table(table)

            con.commit()
        return project


    def add_table(self, table, values=None):
        """ 
        table: a dict with keys
            NAME: the name of the table to create
            FIELDS_DEFINITION: the sql definition (name type) of the "additional" fields (i.e. excludes hole_id, from_ and to_)
            FIELDS: comma-separated list of the fields names, same order as FIELDS_DEFINITION
            SRID: the project's SRID
        values: list of tuples (hole_id, from_, to_, table['FIELDS'])
        """
        with self.connect() as con:
            cur = con.cursor()
            for file_ in ("_albion_table.sql", "albion_table.sql"):
                for statement in (
                    open(os.path.join(os.path.dirname(__file__), file_))
                    .read()
                    .split("\n;\n")[:-1]
                ):
                    cur.execute(
                        string.Template(statement).substitute(table)
                    )
            if values is not None:
                table['FORMAT'] = ','.join([' %s' for v in table['FIELDS'].split(',')])
                print(table)
                cur.executemany("""
                    insert into albion.{NAME}(hole_id, from_, to_, {FIELDS})
                    values (%s, %s, %s, {FORMAT})
                """.format(**table), values)
            cur.execute("""
                refresh materialized view albion.{NAME}_section_geom_cache
                """.format(**table))
            con.commit()
        self.vacuum()

        # TODO add a list of tables in _albion to be able to restore them on update


    def update(self):
        "reload schema albion without changing data"
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            cur.execute("drop schema if exists albion cascade")
            include_elementary_volume = open(
                os.path.join(
                    os.path.dirname(__file__), "elementary_volume", "__init__.py"
                )
            ).read()
            for statement in (
                open(os.path.join(os.path.dirname(__file__), "albion.sql"))
                .read()
                .split("\n;\n")[:-1]
            ):
                cur.execute(
                    statement.replace("$SRID", str(srid)).replace(
                        "$INCLUDE_ELEMENTARY_VOLUME", include_elementary_volume
                    )
                )

            for table in TABLES:
                for statement in (
                    open(os.path.join(os.path.dirname(__file__), "albion_table.sql"))
                    .read()
                    .split("\n;\n")[:-1]
                ):
                    table['SRID'] = str(srid)
                    cur.execute(
                        string.Template(statement).substitute(table)
                    )
            con.commit()

    def __srid(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
        return srid

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
        elif name == "srid":
            return self.__srid()
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


            cur.execute(
                """
                copy _albion.hole(id, x, y, z, depth_, date_, comments) from '{}' delimiter ';' csv header
                """.format(
                    find_in_dir(dir_, "collar")
                )
            )

            progress.setPercent(5)

            cur.execute(
                """
                copy _albion.deviation(hole_id, from_, dip, azimuth) from '{}' delimiter ';' csv header
                """.format(
                    find_in_dir(dir_, "devia")
                )
            )

            progress.setPercent(10)

            cur.execute(
                """
                update _albion.hole set geom = albion.hole_geom(id)
                """
            )

            progress.setPercent(15)


            if find_in_dir(dir_, "avp"):
                cur.execute(
                    """
                    copy _albion.radiometry(hole_id, from_, to_, gamma) from '{}' delimiter ';' csv header
                    """.format(
                        find_in_dir(dir_, "avp")
                    )
                )

            progress.setPercent(20)

            if find_in_dir(dir_, "formation"):
                cur.execute(
                    """
                    copy _albion.formation(hole_id, from_, to_, code, comments) from '{}' delimiter ';' csv header
                    """.format(
                        find_in_dir(dir_, "formation")
                    )
                )

            progress.setPercent(25)

            if find_in_dir(dir_, "lithology"):
                cur.execute(
                    """
                    copy _albion.lithology(hole_id, from_, to_, code, comments) from '{}' delimiter ';' csv header
                    """.format(
                        find_in_dir(dir_, "lithology")
                    )
                )

            progress.setPercent(30)

            if find_in_dir(dir_, "facies"):
                cur.execute(
                    """
                    copy _albion.facies(hole_id, from_, to_, code, comments) from '{}' delimiter ';' csv header
                    """.format(
                        find_in_dir(dir_, "facies")
                    )
                )

            progress.setPercent(35)

            if find_in_dir(dir_, "resi"):
                cur.execute(
                    """
                    copy _albion.resistivity(hole_id, from_, to_, rho) from '{}' delimiter ';' csv header
                    """.format(
                        find_in_dir(dir_, "resi")
                    )
                )

            progress.setPercent(40)

            if find_in_dir(dir_, "chemical"):
                cur.execute(
                    """
                    copy _albion.chemical(hole_id, from_, to_, num_sample,
                        element, thickness, gt, grade, equi, comments)
                    from '{}' delimiter ';' csv header
                    """.format(
                        find_in_dir(dir_, "chemical")
                    )
                )

            progress.setPercent(45)


            progress.setPercent(100)

            con.commit()

        self.vacuum()

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

    def refresh_sections(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("refresh materialized view albion.radiometry_section_geom_cache")
            cur.execute("refresh materialized view albion.resistivity_section_geom_cache")
            con.commit()

    def create_sections(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("refresh materialized view albion.section_geom")
            con.commit()

    def execute_script(self, file_):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            for statement in open(file_).read().split("\n;\n")[:-1]:
                cur.execute(statement.replace("$SRID", str(srid)))
            con.commit()

    def new_graph(self, graph, parent=None):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("delete from albion.graph cascade where id='{}';".format(graph))
            if parent:
                cur.execute(
                    "insert into albion.graph(id, parent) values ('{}', '{}');".format(
                        graph, parent
                    )
                )
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
            cur.execute(
                """
                select group_id from albion.section where id='{}'
                """.format(
                    section
                )
            )
            group, = cur.fetchone()
            group = group or 0
            cur.execute(
                """
                select group_id, geom from albion.section_geom
                where section_id='{section}'
                and group_id < {group}
                order by group_id desc
                limit 1
                """.format(
                    group=group, section=section
                )
            )
            res = cur.fetchone()
            if res:
                sql = """
                    update albion.section set group_id={}, geom='{}'::geometry where id='{}'
                    """.format(
                    res[0], res[1], section
                )
            else:
                sql = """
                    update albion.section set group_id=null, geom=albion.first_section(anchor) where id='{}'
                    """.format(
                    section
                )
            cur.execute(sql)
            con.commit()

    def next_section(self, section):
        if not section:
            return
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                select group_id from albion.section where id='{}'
                """.format(
                    section
                )
            )
            group, = cur.fetchone()
            group = group or 0
            cur.execute(
                """
                select group_id, geom from albion.section_geom
                where section_id='{section}'
                and group_id > {group}
                order by group_id asc
                limit 1
                """.format(
                    group=group, section=section
                )
            )
            res = cur.fetchone()
            if res:
                sql = """
                    update albion.section set group_id={}, geom='{}'::geometry where id='{}'
                    """.format(
                    res[0], res[1], section
                )
                cur.execute(sql)
                con.commit()

    def next_group_ids(self):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                select cell_id from albion.next_group where section_id='{}'
                """.format(
                    self.__current_section.currentText()
                )
            )
            return [cell_id for cell_id, in cur.fetchall()]

    def create_group(self, section, ids):
        with self.connect() as con:
            # add group
            cur = con.cursor()
            cur.execute(
                """
                insert into albion.group default values returning id
                """
            )
            group, = cur.fetchone()
            cur.executemany(
                """
                insert into albion.group_cell(section_id, cell_id, group_id) values(%s, %s, %s)
                """,
                ((section, id_, group) for id_ in ids),
            )
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
            cur.execute(
                "delete from albion.mineralization where level_={}".format(cutoff)
            )
            cur.execute(
                """
                insert into albion.mineralization(hole_id, level_, from_, to_, oc, accu, grade)
                select hole_id, (t.r).level_, (t.r).from_, (t.r).to_, (t.r).oc, (t.r).accu, (t.r).grade
                from (
                select hole_id, albion.segmentation(
                    array_agg(gamma order by from_),array_agg(from_ order by from_),  array_agg(to_ order by from_),
                    {ci}, {oc}, {cutoff}) as r
                from albion.radiometry
                group by hole_id
                ) as t
                """.format(
                    oc=oc, ci=ci, cutoff=cutoff
                )
            )
            cur.execute("refresh materialized view albion.mineralization_section_geom_cache")
            con.commit()
        

    def export_obj(self, graph_id, filename):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                select albion.to_obj(albion.volume_union(st_collectionhomogenize(st_collect(triangulation))))
                from albion.volume
                where graph_id='{}'
                and albion.is_closed_volume(triangulation)
                and  albion.volume_of_geom(triangulation) > 1
                """.format(
                    graph_id
                )
            )
            open(filename, "w").write(cur.fetchone()[0])

    def export_elementary_volume_obj(self, graph_id, cell_id, outdir, closed):
        with self.connect() as con:
            closed_sql = ""
            if not closed:
                closed_sql = "not"

            cur = con.cursor()
            cur.execute(
                """
                select albion.to_obj(geom) from albion.dynamic_volume
                where cell_id='{}' and graph_id='{}'
                and {} albion.is_closed_volume(geom)
                """.format(
                    cell_id, graph_id, closed_sql
                )
            )

            status = "opened"
            if closed:
                status = "closed"

            i = 0
            for obj in cur.fetchall():
                filename = '{}_{}_{}_{}.obj'.format(cell_id, graph_id, status, i)
                i += 1
                path = os.path.join(outdir, filename)
                open(path, "w").write(obj[0])

    def export_elementary_volume_dxf(self, graph_id, cell_id, outdir, closed):
        with self.connect() as con:
            closed_sql = ""
            if not closed:
                closed_sql = "not"

            cur = con.cursor()
            cur.execute(
                """
                select geom from albion.dynamic_volume
                where cell_id='{}' and graph_id='{}'
                and {} albion.is_closed_volume(geom)
                """.format(
                    cell_id, graph_id, closed_sql
                )
            )

            status = "opened"
            if closed:
                status = "closed"

            i = 0
            for wkb_geom in cur.fetchall():
                geom = wkb.loads(bytes.fromhex(wkb_geom[0]))

                filename = '{}_{}_{}_{}.dxf'.format(cell_id, graph_id, status, i)
                path = os.path.join(outdir, filename)
                drawing = dxf.drawing(path)

                for p in geom:
                    r = p.exterior.coords
                    drawing.add(
                        dxf.face3d([tuple(r[0]), tuple(r[1]), tuple(r[2])], flags=1)
                    )
                drawing.save()

                i += 1

    def errors_obj(self, graph_id, filename):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                select albion.to_obj(st_collectionhomogenize(st_collect(triangulation)))
                from albion.volume
                where graph_id='{}'
                and (not albion.is_closed_volume(triangulation) or albion.volume_of_geom(triangulation) <= 1)

                """.format(
                    graph_id
                )
            )
            open(filename, "w").write(cur.fetchone()[0])

    def export_dxf(self, graph_id, filename):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                select albion.volume_union(st_collectionhomogenize(st_collect(triangulation)))
                from albion.volume
                where graph_id='{}'
                and albion.is_closed_volume(triangulation)
                and  albion.volume_of_geom(triangulation) > 1
                """.format(
                    graph_id
                )
            )
            drawing = dxf.drawing(filename)
            m = wkb.loads(bytes.fromhex(cur.fetchone()[0]))
            for p in m:
                r = p.exterior.coords
                drawing.add(
                    dxf.face3d([tuple(r[0]), tuple(r[1]), tuple(r[2])], flags=1)
                )
            drawing.save()

    def create_volumes(self, graph_id):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                delete from albion.volume where graph_id='{}'
                """.format(
                    graph_id
                )
            )
            cur.execute(
                """
                insert into albion.volume(graph_id, cell_id, triangulation)
                select graph_id, cell_id, geom
                from albion.dynamic_volume
                where graph_id='{}'
                and geom is not null --not st_isempty(geom)
                """.format(
                    graph_id
                )
            )
            con.commit()

    def create_terminations(self, graph_id):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                delete from albion.end_node where graph_id='{}'
                """.format(
                    graph_id
                )
            )
            cur.execute(
                """
                insert into albion.end_node(geom, node_id, hole_id, graph_id)
                select geom, node_id, hole_id, graph_id
                from albion.dynamic_end_node
                where graph_id='{}'
                """.format(
                    graph_id
                )
            )
            con.commit()

    def export(self, filename):
        export_db(self.name, filename)

    @staticmethod
    def import_(name, filename):
        import_db(filename, name)
        project = Project(name)
        project.create_sections()
        return project

    def create_section_view_0_90(self, z_scale):
        """create default WE and SN section views with magnifications

        we position anchors south and east in order to have the top of
        the section with a 50m margin from the extent of the holes
        """

        with self.connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                select st_3dextent(geom)
                from albion.hole
                """
            )
            ext = cur.fetchone()[0].replace("BOX3D(", "").replace(")", "").split(",")
            ext = [
                [float(c) for c in ext[0].split()],
                [float(c) for c in ext[1].split()],
            ]

            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            cur.execute(
                """
                insert into albion.section(id, anchor, scale)
                values('SN x{z_scale}', 'SRID={srid};LINESTRING({x} {ybottom}, {x} {ytop})'::geometry, {z_scale})
                """.format(
                    z_scale=z_scale,
                    srid=srid,
                    x=ext[1][0] + 50 + z_scale * ext[1][2],
                    ybottom=ext[0][1],
                    ytop=ext[1][1],
                )
            )

            cur.execute(
                """
                insert into albion.section(id, anchor, scale)
                values('WE x{z_scale}', 'SRID={srid};LINESTRING({xleft} {y}, {xright} {y})'::geometry, {z_scale})
                """.format(
                    z_scale=z_scale,
                    srid=srid,
                    y=ext[0][1] - 50 - z_scale * ext[1][2],
                    xleft=ext[0][0],
                    xright=ext[1][0],
                )
            )

            #cur.execute("refresh materialized view albion.radiometry_section")
            #cur.execute("refresh materialized view albion.resistivity_section")
            con.commit()

    def closest_hole_id(self, x, y):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            cur.execute(
                """
                select id from albion.hole
                where st_dwithin(geom, 'SRID={srid} ;POINT({x} {y})'::geometry, 25)
                order by st_distance('SRID={srid} ;POINT({x} {y})'::geometry, geom)
                limit 1""".format(
                    srid=srid, x=x, y=y
                )
            )
            res = cur.fetchone()
            if not res:
                cur.execute(
                    """
                    select hole_id from albion.current_hole_section
                    where st_dwithin(geom, 'SRID={srid} ;POINT({x} {y})'::geometry, 25)
                    order by st_distance('SRID={srid} ;POINT({x} {y})'::geometry, geom)
                    limit 1""".format(
                        srid=srid, x=x, y=y
                    )
                )
                res = cur.fetchone()

            return res[0] if res else None

    def set_section_geom(self, section_id, geom):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute("select srid from albion.metadata")
            srid, = cur.fetchone()
            cur.execute(
                """
                update albion.section set geom=ST_SetSRID('{wkb_hex}'::geometry, {srid}) where id='{id_}'
                """.format(
                    srid=srid, wkb_hex=geom.wkb_hex, id_=section_id
                )
            )
            con.commit()

    def add_to_graph_node(self, graph, features):
        with self.connect() as con:
            cur = con.cursor()
            cur.executemany(
                """
                insert into albion.node(from_, to_, hole_id, graph_id) values(%s, %s, %s, %s)
                """,
                [(f['from_'], f['to_'], f['hole_id'], graph) for f in features])
            
    def accept_possible_edge(self, graph):
        with self.connect() as con:
            cur = con.cursor()
            cur.execute(
                """
                insert into albion.edge(start_, end_, graph_id, geom, parent)
                select start_, end_, graph_id, geom, parent from albion.possible_edge
                where graph_id=%s
                """,
                (graph,))


