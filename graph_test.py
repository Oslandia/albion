# coding=utf-8

"""
run graph tests

USAGE

   python -m geoledit.graph_test [OPTIONS] [output.obj]

   if output.obj is specified, the volume is saved in this format

OPTIONS

   -h, --help
        print this help

   -g, --graphic
        run in graphic debug mode (vigual output)
"""

from geoledit import graph

import numpy as np

from shapely.geometry import Polygon
from matplotlib import pyplot
from descartes import PolygonPatch
from shapely.wkt import loads

import getopt
import sys
import random

try:
    optlist, args = getopt.getopt(sys.argv[1:],
            "gh",
            ["graphic", "help"])
except Exception as e:
    sys.stderr.write(str(e)+"\n")
    exit(1)

optlist = dict(optlist)

if "-h" in optlist or "--help" in optlist:
    help(sys.modules[__name__])
    exit(0)
graphic = "-g" in optlist or "--graphic" in optlist


def test_extract_path1():
    print 'test_extract_path1'
    vertices = [i for i in range(0, 9)]
    fakes = [0, 2, 6, 8]

    # 0* - 1 - 2* - 3 - 5 - 6* - 7 - 8*
    #          `----- 4 ----'
    connections = [
        [1],       #0
        [0, 2],    #1
        [1, 3, 4], #2
        [2, 5],    #3
        [2, 6],    #4
        [3, 6],    #5
        [4, 7, 5], #6
        [6, 8],    #7
        [7]        #8
    ]

    result = graph.extract_paths(vertices, fakes, connections)

    print result
    assert len(result) == 4

    # 2 possible outcomes
    # option1 = (result[0] == [0, 1, 2, 3, 5, 6, 7, 8] and result[1] == [2, 4, 6])
    # option2 = (result[0] == [0, 1, 2, 4, 6, 7, 8] and result[1] == [2, 3, 5, 6])
    # assert option1 or option2

def test_extract_path2():
    print 'test_extract_path2'
    vertices = [123, 212, 45]
    fakes = [123, 45]

    # 123* - 212 - 45*
    connections = [
        [212],       #0
        [123, 45],   #1
        [212],       #2
    ]

    result = graph.extract_paths(vertices, fakes, connections)

    assert len(result) == 1
    assert result[0] == [123, 212, 45]

def test_extract_path3():
    print 'test_extract_path3'
    vertices = [123, 212, 45, 1, 2, 3]
    fakes = [123, 45, 1, 3]

    # 123* - 212 - 45*
    # 1* - 2 - 3*
    connections = [
        [212],       #0
        [123, 45],   #1
        [212],       #2
        [2],
        [1, 3],
        [2]
    ]

    result = graph.extract_paths(vertices, fakes, connections)

    assert len(result) == 2

    assert result[0] == [123, 212, 45]
    assert result[1] == [1, 2, 3]

def test_extract_path4():
    print 'test_extract_path4'
    vertices = [123, 212, 31, 45]

    # 123 - 212 - 45
    #   `-- 31
    fakes = [123, 31, 45]
    connections = [
        [31, 212],   # 123
        [123, 45],   # 212
        [123],       # 31
        [212],       # 45
    ]

    result = graph.extract_paths(vertices, fakes, connections)
    assert len(result) == 2
    fakes = [31, 123, 45]
    result = graph.extract_paths(vertices, fakes, connections)
    assert len(result) == 2


def test_extract_path5():
    print 'test_extract_path5'
    vertices = [3363,3364,3367,3372,3688,3707,3791,4746,4747,4748,4749]
    fakes = [4746,4747,4748,4749]
    connections = [
        [4748, 4749],       #3363
        [4748, 4749],       #3364
        [3791, 4746],       #3367
        [3791, 3707],       #3372
        [4747, 4748],       #3688
        [3372, 4749],       #3707
        [3367, 3372],       #3791
        [3367],             #4746
        [3688],             #4747
        [3688, 3363, 3364], #4748
        [3707, 3363, 3364]  #4749
    ]

    vertices = [ i for i in range(0, 20) ]
    # 0* -1 - 2* - 3 - 5* - 6 - 7*
    #          `-- 4 --'
    fakes = [0, 2, 5, 7]
    connections = [
       [1],
       [0, 2],
       [1, 3, 4],
       [2, 5],
       [2, 5],
       [3, 4, 6],
       [5, 7],
       [6]
    ]

    result = graph.extract_paths(vertices, fakes, connections)

    print result
    assert len(result) == 5

def test_to_surface1(graphic):

    surface = loads('MULTIPOLYGON Z (((4.94027261318344 380.7264563568561 0, 4.955781761018398 361.6896534708884 0, 26.99063511463036 379.5359246871234 0, 26.85714883531019 391.0142110210066 0, 4.94027261318344 380.7264563568561 0)), ((26.85714883531019 391.0142110210066 0, 26.99063511463036 379.5359246871234 0, 54.37591453034874 359.32099319199 0, 54.25653707749527 380.6006402339815 0, 26.85714883531019 391.0142110210066 0)), ((54.25653707749527 380.6006402339815 0, 54.37591453034874 359.32099319199 0, 79.66587280242857 355.0902186732959 0, 79.65859035649547 358.0602084952723 0, 54.25653707749527 380.6006402339815 0)), ((79.65859035649547 358.0602084952723 0, 79.66587280242857 355.0902186732959 0, 105.5110552842375 357.8444233113257 0, 105.3641360330013 379.8528272935834 0, 79.65859035649547 358.0602084952723 0)), ((105.3641360330013 379.8528272935834 0, 105.5110552842375 357.8444233113257 0, 129.8894844867128 344.4919046060771 0, 129.8693574974351 353.8516649621346 0, 105.3641360330013 379.8528272935834 0)), ((105.3641360330013 379.8528272935834 0, 105.5110552842375 357.8444233113257 0, 129.8109978298091 380.9909700971133 0, 129.7853660230166 392.9106649095285 0, 105.3641360330013 379.8528272935834 0)))')

    # assert len(surface) == 2
    # assert len(surface[0].exterior.coords) == 5
    # assert len(surface[1].exterior.coords) == 10

    if graphic:
        fig = pyplot.figure(1)
        ax = fig.add_subplot(111)

        ax.set_title('General Polygon')
        ax.set_xlim(0, 150)
        ax.set_ylim(300, 400)

        for surf in ([surface] if isinstance(surface, Polygon) else surface):
            patch = PolygonPatch(surf)
            ax.add_patch(patch)

        pyplot.show()


def test_to_surface(graphic):
    nodes = np.array([
        [[0,.1,10],[0,-.1,1]],
        [[1,.3,1],[1,.2,1]],
        [[1,-.1,1],[1,-.2,1]],
        [[-1,.1,1],[-1,-.3,1]],
        [[1.5,.1,1],[1.6,-.1,1]],
        [[2,.2,1],[2,0,1]]
        ])
    edges = ((3,0),(0,1),(0,2),(4,5))

    surface = graph.to_surface(nodes, edges)

    assert len(surface) == 2
    assert len(surface[0].exterior.coords) == 5
    assert len(surface[1].exterior.coords) == 10

    if graphic:
        fig = pyplot.figure(1)
        ax = fig.add_subplot(111)

        for surf in ([surface] if isinstance(surface, Polygon) else surface):
            patch = PolygonPatch(surf)
            ax.add_patch(patch)

        ax.set_title('General Polygon')
        ax.set_xlim(-2, 3)
        ax.set_ylim(-1, 1)

        pyplot.show()

def to_obj(vertices, volumes):
    obj = ""
    for vtx in vertices:
        obj += "v %f %f %f\n"%tuple(vtx)
    obj += "\n"
    for vol in volumes:
        for tri in vol:
            obj += "f %d %d %d\n"%tuple([n+1 for n in tri])
    return obj

def test_to_volume(outfile=None):

    nodes = np.array(
[[[323337.37, 2075040.74, 418.68], [323338.1769061049, 2075040.573191502, 389.1815055051442]], [[323362.41, 2075040.84, 418.54], [323362.8466387543, 2075040.62750853, 388.9439834779482]], [[323386.11, 2075041.93, 418.45], [323386.7158632646, 2075042.203939748, 388.4573694598276]], [[323337.31, 2075091.36, 418.77], [323338.0870240696, 2075091.841963108, 389.9945235459405]], [[323362.3730192074, 2075090.59708967, 376.3910339891728], [323362.4566999198, 2075090.490597556, 356.9915067534894]], [[323387.7354161257, 2075092.429363151, 377.9407885488984], [323387.9758615386, 2075093.073148603, 356.4317642498869]], [[323337.37, 2075065.8, 418.97], [323337.4684484344, 2075065.743206582, 389.3702182032806]], [[323338.387685693, 2075092.028453869, 378.8601432854952], [323338.9404280669, 2075092.371302234, 358.3904747276925]], [[323386.9416483078, 2075042.30602796, 377.2801158118567], [323387.3788796305, 2075042.503721145, 355.6354341053657]], [[323387.6036935537, 2075066.779308467, 377.3449812794333], [323387.664866292, 2075067.090533435, 356.9274447748566]], [[323387.6020091448, 2075092.072169922, 389.8746988709335], [323387.7189916482, 2075092.385387101, 379.4100388146766]]]
        )

    edges = [(0, 1), (1, 2), (3, 4), (4, 5), (0, 6), (6, 7), (8, 9), (9, 10)]
    volumes, vertices = graph.to_volume(nodes, edges)


    if outfile is not None:
        with open(outfile, 'w') as obj:
            obj.write(to_obj(vertices, volumes))

test_extract_path1()

test_extract_path2()

test_extract_path3()

test_extract_path4()

test_extract_path5()

test_to_surface1(graphic)

test_to_volume(args[0] if len(args) else None)
