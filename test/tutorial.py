from __future__ import print_function
# coding = utf-8

if __name__ == "__main__":
    from albion.project import Project
    import os
    import sys
    import time
    import tempfile
    import zipfile

    project_name = "tutorial_test"
    
    if Project.exists(project_name):
        Project.delete(project_name)
    
    project = Project.create(project_name, 32632)
    start = time.time()
    zip_ref = zipfile.ZipFile(os.path.join(os.path.dirname(__file__), '..', 'data', 'nt.zip'), 'r')
    zip_ref.extractall(tempfile.gettempdir())
    zip_ref.close()
    data_dir = os.path.join(tempfile.gettempdir(), 'nt')
    project.import_data(data_dir)
    project.create_section_view_0_90(4)
    project.compute_mineralization(1000, 1, 1)

    project.triangulate()

    with project.connect() as con:
        cur = con.cursor()
        cur.execute("delete from albion.cell where aspect_ratio > 10")
        con.commit()

    with project.connect() as con:
        cur = con.cursor()
        cur.execute("select name from albion.layer")
        layers = [r[0] for r in cur.fetchall()]
        print(layers)

    #for l in layers:
    #    project.refresh_section_geom(l)
    

    project.new_graph('330')
    project.new_graph('min1000', '330')

    with project.connect() as con:
        cur = con.cursor()
        cur.execute("""
            insert into albion.node(from_, to_, hole_id, graph_id) 
            select from_, to_, hole_id, '330' from albion.formation where code=330
            """)
        con.commit()

    project.accept_possible_edge('330')
    project.create_terminations('330')
    project.create_volumes('330')

    # test that all volumes are closed and positive
    with project.connect() as con:
        cur = con.cursor()
        cur.execute("""
            select cell_id from albion.volume where not albion.is_closed_volume(triangulation)
            """
            )
        unclosed = cur.fetchall()
        if len(unclosed):
            print("unclosed volume for cells", unclosed)
        assert(len(unclosed) == 0)
        cur.execute("""
            select count(1) from albion.volume where albion.volume_of_geom(triangulation) <= 0
            """
            )
        assert(cur.fetchone()[0]==0)

        
    with project.connect() as con:
        cur = con.cursor()
        cur.execute("""
            insert into albion.node(from_, to_, hole_id, graph_id)
            select from_, to_, hole_id, 'min1000' from albion.mineralization
            """)

        con.commit()

    project.accept_possible_edge('min1000')
    project.create_terminations('min1000')
    project.create_volumes('min1000')


    

