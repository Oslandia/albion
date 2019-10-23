from __future__ import print_function
# coding = utf-8


SQL = """
INSERT INTO albion.collar(id, geom, depth_) VALUES
    (1, 'SRID=32632;POINT(0 0 0)'::geometry, 100),
    (2, 'SRID=32632;POINT(100 0 0)'::geometry, 100),
    (3, 'SRID=32632;POINT(200 0 0)'::geometry, 100),
    (4, 'SRID=32632;POINT(300 0 0)'::geometry, 100),
    (5, 'SRID=32632;POINT(0 100 0)'::geometry, 100)
;
SELECT albion.triangulate()
;
REFRESH MATERIALIZED VIEW albion.all_edge
;
INSERT INTO albion.graph(id) VALUES
    ('graph1')
;
INSERT INTO albion.node(id, graph_id, hole_id, from_, to_, geom) VALUES
    (1, 'graph1', 2, 50, 100, albion.hole_piece(50, 100, '2')),
    (2, 'graph1', 3,  0,  50, albion.hole_piece(0, 50, '3'))
;
INSERT INTO albion.edge(id, graph_id, start_, end_, geom) VALUES
    (1, 'graph1', 1, 2, 'SRID=32632;LINESTRING(100 0 -75, 200 0 -25)'::geometry)
;
"""


if __name__ == "__main__":
    from albion.project import Project
    import os
    import sys
    import time


    project_name = "end_node_test"
    
    if Project.exists(project_name):
        Project.delete(project_name)
    
    project = Project.create(project_name, 32632)
    start = time.time()

    with project.connect() as con:
        cur = con.cursor()
        for sql in SQL.split("\n;\n")[:-1]:
            cur.execute(sql)
        con.commit()

        cur.execute("""
            SELECT node_id, hole_id, st_astext(geom) 
            FROM albion.dynamic_end_node 
            WHERE hole_id !='5'
            """)
        for r in cur.fetchall():
            print(r)







