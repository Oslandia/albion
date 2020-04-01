if __name__ == "__main__":

    from albion.project import Project
    import os
    import shutil

    project = Project("tutorial_test")
    
    with project.connect() as con:
        cur = con.cursor()
        cur.execute("select id from albion.cell")
        if os.path.isdir('/tmp/min1000'):
            shutil.rmtree('/tmp/min1000')
        os.mkdir('/tmp/min1000')
        cells = [r for r, in cur.fetchall()]
        project.export_elementary_volume_obj('min1000', cells, '/tmp/min1000')
        project.export_elementary_volume_dxf('min1000', cells, '/tmp/min1000')


