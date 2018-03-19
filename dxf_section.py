# coding: utf-8

"""
USAGE

dxf_section "dbname..." graph_id file.dxf
"""

import sys
import psycopg2 
from dxfwrite import DXFEngine as dxf
from shapely import wkb
from builtins import bytes

con = psycopg2.connect(sys.argv[1])
cur = con.cursor()
 
cur.execute("""
    delete from albion.section 
    where graph_id='{}'""".format(sys.argv[2]))

cur.execute("""
    insert into albion.section(id, triangulation, graph_id, grid_id)
    select 
        _albion.unique_id()::varchar,
        st_collectionhomogenize(st_collect(albion.triangulate_edge(ceil_, wall_))),
        graph_id, grid_id
    from albion.edge
    where graph_id='{}'
    group by graph_id, grid_id
    """.format(sys.argv[2]))

cur.execute("""
    select st_collectionhomogenize(st_collect(triangulation)) 
    from albion.section 
    where graph_id='{}'
    """.format(sys.argv[2]))
drawing = dxf.drawing(sys.argv[3]+'.dxf')
m = wkb.loads(bytes.fromhex(cur.fetchone()[0]))
for p in m:
    r = p.exterior.coords
    drawing.add(dxf.face3d([tuple(r[0]), tuple(r[1]), tuple(r[2])], flags=1))
drawing.save()

cur.execute("""
    select albion.to_obj(st_collectionhomogenize(st_collect(triangulation))) 
    from albion.section 
    where graph_id='{}'
    """.format(sys.argv[2]))
open(sys.argv[3]+'.obj', 'w').write(cur.fetchone()[0])


