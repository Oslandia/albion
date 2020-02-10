from __future__ import print_function
# coding = utf-8

# (1)<--------------100 m----------------->(2)
#                                         6||3
#
#
#
#                                                _ -50m
#  |                                      5||2
#  |                                        
# 1||4                                       
#  |                                        
#  |                                             _ -100 m

SQL = """
INSERT INTO albion.collar(id, geom, depth_) VALUES
    (1, 'SRID=32632;POINT(0 0 0)'::geometry, 100),
    (2, 'SRID=32632;POINT(100 0 0)'::geometry, 100),
    (3, 'SRID=32632;POINT(100 100 0)'::geometry, 100)
;
INSERT INTO albion.cell(id, a, b, c, geom) VALUES
    (1, 1, 2, 3, 'SRID=32632;POLYGON((0 0, 100 0, 100 100, 0 0))'::geometry)
;
REFRESH MATERIALIZED VIEW albion.all_edge
;
INSERT INTO albion.graph(id) VALUES
    ('graph1')
;
INSERT INTO albion.node(id, graph_id, hole_id, from_, to_, geom) VALUES
    (1, 'graph1', 1, 50, 100, 'SRID=32632;LINESTRING(0 0 -50, 0 0 -100)'::geometry),
    (2, 'graph1', 2, 50, 60, 'SRID=32632;LINESTRING(100 0 -50, 100 0 -60)'::geometry),
    (3, 'graph1', 2,  0, 50, 'SRID=32632;LINESTRING(100 0 -40, 100 0 -50)'::geometry)
;
INSERT INTO albion.graph(id, parent) VALUES
    ('graph2', 'graph1')
;
INSERT INTO albion.node(id, graph_id, hole_id, from_, to_, geom) VALUES
    (4, 'graph2', 1, 70, 80, 'SRID=32632;LINESTRING(0 0 -70, 0 0 -80)'::geometry),
    (5, 'graph2', 2, 50, 60, 'SRID=32632;LINESTRING(100 0 -50, 100 0 -60)'::geometry),
    (6, 'graph2', 2,  0, 10, 'SRID=32632;LINESTRING(100 0 0, 100 0 -10)'::geometry)
;
;
"""


if __name__ == "__main__":
    from albion.project import Project
    import os
    import sys
    import time


    project_name = "parent_graph_test"
    
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
            UPDATE albion.metadata SET correlation_angle=1 ;
            """)

        cur.execute("""
            SELECT start_, end_ FROM albion.possible_edge
            """)
        for s,e in cur.fetchall():
            print(s,e)

        cur.execute("""
            INSERT INTO albion.edge(start_, end_, graph_id, geom) SELECT start_, end_, graph_id, geom FROM albion.possible_edge
            """)

        cur.execute("""
            SELECT start_, end_ FROM albion.possible_edge
            """)
        
        edges = [(s,e) for s,e in cur.fetchall()]
        print(edges)
        assert(('1','2') in edges)
        assert(('4','5') in edges)






