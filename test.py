# coding=utf-8

"""
run all tests

USAGE
    python -m albion.test [-h, -etest]

OPTIONS
    -h
        print this help

    -e test1,tes2
        exclude test1 and test2
"""

import subprocess
import os
import re
from subprocess import Popen, PIPE
from tempfile import gettempdir
from time import time
from multiprocessing.pool import ThreadPool
import getopt
import sys

try:
    optlist, args = getopt.getopt(sys.argv[1:],
            "hj:e:",
            ["help"])
except Exception as e:
    sys.stderr.write(str(e)+"\n")
    exit(1)

optlist = dict(optlist)

if "-h" in optlist or "--help" in optlist:
    help(sys.modules[__name__])
    exit(0)

excludes = optlist['-e'].split(',') if '-e' in optlist else []

if len(excludes):
    print "excluded", ' '.join(excludes)


# test model creation

debug = "-d" in optlist or "--debug" in optlist

start = time()

def list_tests():
    "return module names for tests"
    tests = []
    base_dir = os.path.abspath(os.path.dirname(__file__))
    top_dir = os.path.dirname(base_dir)
    for root, dirs, files in os.walk(base_dir):
        for file_ in files:
            if re.match(r".*_test.py$", file_):
                # remove the trailing '.py' (3 characters)
                # replace \ or / by dots
                test = '.'.join(
                            os.path.abspath(
                                os.path.join(root, file_)
                            ).replace(base_dir, "albion").split(os.sep))[:-3]
                if test not in excludes:
                    tests.append(test)
    #tests += ['albion.docs.build']

    return tests


def run(test):
    start = time()
    out, err = subprocess.Popen(["python", "-m", test],
            stderr=PIPE,
            stdout=PIPE).communicate()
    if len(err):
        print 'DEBUG:\n#########\n{}#########\n'.format(out)
        return 1, '%s: %s'%(test, str(err))
    return  0, "%s ran in %.2f sec"%(test, time() - start)

tests = list_tests()
nb_proc = int(optlist['-j']) if '-j' in optlist else len(tests)

if nb_proc > 1:
    print "start %d processes"%(nb_proc)
    i = 0
    for rc, msg in ThreadPool(processes=nb_proc).map(run, tests):
        print "% 3d/%d %s"%(i+1, len(tests), msg)
        if rc != 0:
            exit(1)
        i += 1
else:
    for i, test in enumerate(tests):
        rc, msg = run(test)
        print "% 3d/%d %s"%(i+1, len(tests), msg)


print "everything is fine %d sec"%(int(time() - start))
