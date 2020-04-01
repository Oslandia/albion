# coding=UTF-8

import os
import shutil
import shlex
import warnings
from subprocess import Popen, PIPE

def build():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    build_dir = os.path.join(current_dir, "build")
    html_dir = os.path.join(build_dir, "html")
    source_dir =  os.path.join(current_dir, "fr")
    doctrees_dir = os.path.join(build_dir, "doctrees")
    api_dir = os.path.join(source_dir, "api")
    static_dir = os.path.join(source_dir, "_static")

    def exec_cmd(cmd):
        out, err = Popen(cmd, 
                stderr=PIPE, stdout=PIPE).communicate()
        if err:
            warnings.warn(err)
            #raise RuntimeError("command '{}' failed".format(" ".join(cmd)))

    if not os.path.isdir(build_dir):
        os.mkdir(build_dir)

    if not os.path.isdir(static_dir):
        os.mkdir(static_dir)

    if os.path.isdir(api_dir):
        shutil.rmtree(api_dir)
    os.mkdir(api_dir)

    cmd = shlex.split("sphinx-build -b html -d")+[doctrees_dir, source_dir, html_dir]
    exec_cmd(cmd)



