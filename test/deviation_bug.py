from __future__ import print_function
# coding = utf-8

if __name__ == "__main__":
    from albion.project import Project
    import os
    from pglite import import_db

    for f,dbname in (('git1.dump', 'deviation_bug_test_1'), ('git2.dump', 'deviation_bug_test_2')):
        if Project.exists(dbname):
            Project.delete(dbname)
        import_db(os.path.join(os.path.dirname(__file__), f), dbname)

    
