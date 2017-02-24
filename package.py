# coding=utf-8
"""
packaging script for the albion project

USAGE
    package.py [-h, -i, -u] [directory],

OPTIONS
    -h, --help
        print this help

    -i, --install [directory]
        install the package in the .qgis2 directory, if directory is ommited,
        install in the QGis plugin directory

    -u, --uninstall
        uninstall (remove) the package from .qgis2 directory

    -d, --deploy
        deploy the package to qgis repository directory
"""

import os
import zipfile
import re
import shutil
import getpass
import time
import subprocess

# @todo make that work on windows
qgis_plugin_dir = os.path.join(os.path.expanduser("~"), ".qgis2", "python", "plugins")
repository_dir = "//Dev/repository/"
zipname = "albion"
zipext = ".zip"

def run_tests():
    out, err = subprocess.Popen(["python", "-m", "albion.test"]).communicate()
    if err :
        print "Can not deploy if test fails."
        print err
        exit(1)

def deploy(zip_filename, new_version):
    file_name = repository_dir + zipname + "_" + str(new_version) + zipext
    shutil.copyfile(zip_filename,file_name)
    xmlfile = os.path.join(repository_dir, "albion.xml")
    with open(xmlfile, 'r') as file:
        data = file.readlines()
    data[3]= "  <pyqgis_plugin name='albion' version='" + str(new_version) + "'>\n"
    data[5]= "    <version>" + str(new_version) + "</version>\n"
    data[10]= "    <download_url>file://" + file_name +  "</download_url>\n"
    data[11]= "    <uploaded_by>" + getpass.getuser() + "</uploaded_by>\n"
    data[12]= "    <create_date>" + time.strftime("%x") + "</create_date>\n"
    with open(xmlfile, 'w') as file:
        file.writelines( data )

def update_meta():
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    meta_dir = os.path.join(base_dir, "metadata.txt")
    with open(meta_dir, 'r') as file:
        data = file.readlines()
    newversion = float(data[12].split('=')[1]) + 0.01
    data[12]= "version="+str(newversion)+"\n"
    print data[12]
    with open(meta_dir, 'w') as file:
        file.writelines( data )
    return newversion

def uninstall(install_dir):
    target_dir = os.path.join(install_dir, "base_dir")
    if os.path.isdir(target_dir):
        shutil.rmtree(target_dir)

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
            if not re.match(r".*(test_data|docs).*", root):
                for file_ in files:
                    if re.match(r".*\.(w15|py|txt|ui|json|sql|png|svg|qml)$", file_) \
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
                ["help", "install", "uninstall", "deploy", "test"])
    except Exception as e:
        sys.stderr.write(str(e)+"\n")
        exit(1)

    optlist = dict(optlist)

    if "-h" in optlist or "--help" in optlist:
        help(sys.modules[__name__])
        exit(0)

    if "-t" in optlist:
        run_tests()

    if "-d" in optlist or "--deploy" in optlist:
        run_tests()
        new_version = update_meta()

    zip_filename = os.path.join(os.path.dirname(os.path.dirname(__file__)), zipname+zipext)
    zip_(zip_filename)
    install_dir = qgis_plugin_dir if len(args)==0 else args[0]

    if "-u" in optlist or "--uninstall" in optlist:
        uninstall(install_dir)

    if "-i" in optlist or "--install" in optlist:
        install(install_dir, zip_filename)

    if "-d" in optlist or "--deploy" in optlist:
        deploy(zip_filename, new_version)

