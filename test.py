from __future__ import print_function
# coding = utf-8

if __name__ == "__main__":

    from pglite import start_cluster, stop_cluster, init_cluster, check_cluster
    from albion.project import Project
    import os

    if not check_cluster():
        init_cluster()
    start_cluster()

    project_name = "niger"
    srid = 32632
    data_dir = "/home/vmo/areva/old_albion/test_data"

    if False: # new project
        if Project.exists(project_name):
            Project.delete(project_name)
        project = Project.create(project_name, srid)
        project.import_data(data_dir)
    else:
        project = Project(project_name)
        project.update()


    

    #project.triangulate()


    project.execute_script(os.path.join(os.path.dirname(__file__), 'test.sql'))

    with project.connect() as con:
        cur = con.cursor()
        cur.execute("""
        select (t.r).from_, (t.r).to_, (t.r).oc, (t.r).accu, (t.r).grade
        from (
            select albion.segmentation(array_agg(gamma order by from_), array_agg(from_ order by from_), array_agg(to_ order by from_), 1., 1., 10, min(from_)) as r
            from _albion.radiometry
            where hole_id='GART_0556_1'
            ) as t
            """)
        for rec in cur.fetchall():
            # fix_print_with_import
            print(rec)

    #con = project.connect()
    #cur = con.cursor()
    #cur.execute("""
    #    delete from albion.section
    #    """)
    #cur.execute("""
    #    insert into albion.section(anchor)
    #    values ('SRID={srid};LINESTRING(322705.36 2078500, 327627.06 2078500)'::geometry)
    #    """.format(srid=srid))



    ##cur.execute("""
    ##    update albion.section set geom=albion.offset_section(20, anchor, geom)
    ##    """)

    #con.commit()


    #stop_cluster()

