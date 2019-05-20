"""
packaging script for the albion documentation

USAGE
    python -m albion.doc [-h]

OPTIONS
    -h, --help
        print this help

"""

from builtins import str
import sys
import getopt
from . import build

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

build()
exit(0)


