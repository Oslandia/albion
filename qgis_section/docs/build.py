# coding=utf-8
"""
packaging script for the qgis_section documentation

USAGE
    build.py [-h]

OPTIONS
    -h, --help
        print this help

"""

import os
import getopt
import sys
import shutil
import shlex
from subprocess import Popen, PIPE
from  ..package import zip_, install

def create_package(build_dir):
    zip_filename = os.path.join(build_dir, "qgis_section.zip")
    zip_(zip_filename)
    install(build_dir, zip_filename)

if __name__ == "__main__":

    try:
        optlist, args = getopt.getopt(sys.argv[1:],
                "h",
                ["help"])
    except Exception as e:
        sys.stderr.write(str(e)+"\n")
        exit(1)

    optlist = dict(optlist)

    if "-h" in optlist or "--help" in optlist:
        help(sys.modules[__name__])
        exit(0)

    current_dir = os.path.abspath(os.path.dirname(__file__))
    build_dir = os.path.join(current_dir, "build")
    html_dir = os.path.join(build_dir, "html")
    source_dir =  os.path.join(current_dir, "source")
    doctrees_dir = os.path.join(build_dir, "doctrees")
    module_dir = os.path.join(build_dir, "qgis_section")
    api_dir = os.path.join(source_dir, "api")
    static_dir = os.path.join(source_dir, "_static")

    def exec_cmd(cmd):
        print " ".join(cmd)
        out, err = Popen(cmd,
                stderr=PIPE, stdout=PIPE).communicate()
        if err :
            print "failed"
            print err
            exit(1)

    if not os.path.isdir(build_dir):
        os.mkdir(build_dir)

    if not os.path.isdir(static_dir):
        os.mkdir(static_dir)

    if os.path.isdir(api_dir):
        shutil.rmtree(api_dir)
    os.mkdir(api_dir)

    if not os.path.isdir(html_dir):
        os.mkdir(html_dir)

    create_package(build_dir)

    exec_cmd(shlex.split("sphinx-apidoc -e -d2 -T -o")+[api_dir, module_dir, "**/*_test.py", "*_demo.py"])
    exec_cmd(shlex.split("sphinx-build -b html -d")+[doctrees_dir, source_dir, html_dir])


