# coding = utf-8

if __name__ == "__main__":
    from albion.project import Project
    import os
    import sys
    import time


    project_name = "import_test"
    if Project.exists(project_name):
        Project.delete(project_name)
    
    project = Project.create(project_name, 32632)
    start = time.time()
    project.import_data(sys.argv[1])
    print "time for import", time.time() - start, 'sec'
    #project = Project(project_name)
    #
    #project.triangulate()
    #project.create_section_view_0_90(4)

