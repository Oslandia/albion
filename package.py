# coding: utf-8
"""
packaging script for the albion project

USAGE
    package.py [-h, -i, -u, -t] [directory],

OPTIONS
    -h, --help
        print this help

    -i, --install [directory]
        install the package in the .qgis2 directory, if directory is ommited,
        install in the QGis plugin directory

    -u, --uninstall
        uninstall (remove) the package from .qgis2 directory

    -t
        launch the tests before installing/uninstalling
"""

import os
import zipfile
import re
import shutil
import subprocess

# @todo make that work on windows
qgis_plugin_dir = os.path.join(os.path.expanduser("~"), ".qgis2", "python", "plugins")
zipname = "albion"
zipext = ".zip"


def run_tests():
    out, err = subprocess.Popen(["pytest"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE).communicate()
    if '0 failed' not in out.splitlines()[-1]:
        print "Can not deploy if test fails."
        print out
        exit(1)

def uninstall(install_dir):
    target_dir = os.path.join(install_dir, "albion")
    if os.path.isdir(target_dir):
        print "uninstall dir", target_dir
        shutil.rmtree(target_dir)
    else:
        print "Install directory '%s' not found" % target_dir

def install(install_dir, zip_filename):
    uninstall(install_dir)
    with zipfile.ZipFile(zip_filename, "r") as z:
        z.extractall(install_dir)
    print "installed in", install_dir

def zip_(zip_filename):
    """the zip file doesn't include tests, demos or docs"""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    with zipfile.ZipFile(zip_filename, 'w') as package:
        for root, dirs, files in os.walk(base_dir):
            if not re.match(r".*(test_data|docs|tests).*", root):
                for file_ in files:
                    if re.match(r".*\.(py|txt|ui|json|sql|png|svg|qml|qgs)$", file_) \
                            and not re.match(r".*(_test|_demo)\.py", file_) \
                            and not re.match(r"(package.py|test.py)", file_):
                        fake_root = root.replace(base_dir, "albion")
                        package.write(os.path.join(root, file_),
                                      os.path.join(fake_root, file_))


if __name__ == "__main__":
    import getopt
    import sys

    try:
        optlist, args = getopt.getopt(sys.argv[1:],
                "hiudt",
                ["help", "install", "uninstall", "test"])
    except Exception as e:
        sys.stderr.write(str(e)+"\n")
        exit(1)

    optlist = dict(optlist)

    if "-h" in optlist or "--help" in optlist or not optlist:
        help(sys.modules[__name__])
        exit(0)

    if "-t" in optlist:
        run_tests()

    zip_filename = os.path.join(os.path.dirname(os.path.dirname(__file__)), zipname+zipext)
    zip_(zip_filename)
    install_dir = qgis_plugin_dir if len(args)==0 else args[0]

    if "-u" in optlist or "--uninstall" in optlist:
        uninstall(install_dir)

    if "-i" in optlist or "--install" in optlist:
        install(install_dir, zip_filename)

