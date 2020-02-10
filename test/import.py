from __future__ import print_function
# coding = utf-8

if __name__ == "__main__":
    from albion.project import Project
    import os
    import sys
    import time
    import tempfile
    import zipfile



    project_name = "import_test"
    
    if Project.exists(project_name):
        Project.delete(project_name)
    
    project = Project.create(project_name, 32632)
    start = time.time()
    zip_ref = zipfile.ZipFile(os.path.join(os.path.dirname(__file__), '..', 'data', 'nt.zip'), 'r')
    zip_ref.extractall(tempfile.gettempdir())
    zip_ref.close()
    data_dir = os.path.join(tempfile.gettempdir(), 'nt')
    print('###############################', data_dir)
    project.import_data(data_dir)
    project.triangulate()
    project.create_section_view_0_90(4)

