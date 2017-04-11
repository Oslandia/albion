# coding: utf-8

"""
run graph tests

USAGE

   python -m albion.graph_test [OPTIONS] [output.obj]

   if output.obj is specified, the volume is saved in this format

OPTIONS

   -h, --help
        print this help

   -g, --graphic
        run in graphic debug mode (vigual output)
"""

from hypothesis import given
from hypothesis.strategies import integers, lists

from albion import graph

import unittest
import numpy as np

import getopt
import sys

try:
    optlist, args = getopt.getopt(sys.argv[1:],
                                  'gh',
                                  ['graphic', 'help'])
except Exception as e:
    sys.stderr.write(str(e)+"\n")
    exit(1)

optlist = dict(optlist)

if "-h" in optlist or "--help" in optlist:
    help(sys.modules[__name__])
    exit(0)
graphic = "-g" in optlist or "--graphic" in optlist


def to_obj(self, vertices, volumes):
    obj = ""
    for vtx in vertices:
        obj += "v %f %f %f\n" % tuple(vtx)
    obj += "\n"
    for vol in volumes:
        for tri in vol:
            obj += "f %d %d %d\n" % tuple([n+1 for n in tri])
    return obj


def build_seq_connections(v):
    # connect all vertices sequentially
    connections = [[v[1]]]
    for i in range(1, len(v) - 1):
        connections += [[v[i-1], v[i+1]]]
    connections += [[v[-2]]]
    return connections


class TestGraph(unittest.TestCase):
    @given(lists(integers(), unique=True, min_size=2, max_size=50))
    def test_simplest_path(self, vertices):
        fakes = [vertices[0], vertices[-1]]

        connections = build_seq_connections(vertices)

        result = graph.extract_paths(vertices, fakes, connections)
        self.assertEquals(len(result), 1)
        self.assertEquals(len(result[0]), len(vertices))

    @given(lists(integers(), unique=True, min_size=8, max_size=50))
    def test_extract_path1(self, vertices):
        fakes = [vertices[0], vertices[2], vertices[-4], vertices[-2]]

        # 0* - 1 - 2* - [...] - 6* - 7 - 8*
        #          `---- 4 -----'
        connections = build_seq_connections(vertices[0:-1])

        connections[vertices.index(fakes[1])] += [vertices[-1]]
        connections[vertices.index(fakes[2])] += [vertices[-1]]
        connections += [[fakes[1], fakes[2]]]

        result = graph.extract_paths(vertices, fakes, connections)
        expected = [
            [vertices[0], vertices[1], vertices[2]],
            [vertices[-4], vertices[-3], vertices[-2]],
            [vertices[2], vertices[-1], vertices[-4]],
            vertices[2:-3]
        ]
        self.assertEquals(len(result), 4,
                          'Expected 4 paths but found {}'.format(result))

        for e in expected:
            test1 = e in result
            e.reverse()
            test2 = e in result
            self.assertTrue(test1 or test2,
                            '{} missing in {}'.format(e, result))

    def test_extract_path2(self):
        vertices = [123, 212, 45]
        fakes = [123, 45]

        # 123* - 212 - 45*
        connections = [
            [212],       # 0
            [123, 45],   # 1
            [212],       # 2
        ]

        result = graph.extract_paths(vertices, fakes, connections)

        self.assertEquals(len(result), 1)
        self.assertEquals(result[0], [123, 212, 45])

    def test_extract_path3(self):
        vertices = [123, 212, 45, 1, 2, 3]
        fakes = [123, 45, 1, 3]

        # 123* - 212 - 45*
        # 1* - 2 - 3*
        connections = [
            [212],       # 0
            [123, 45],   # 1
            [212],       # 2
            [2],
            [1, 3],
            [2]
        ]

        result = graph.extract_paths(vertices, fakes, connections)

        self.assertEquals(len(result), 2)

        self.assertEquals(result[0], [123, 212, 45])
        self.assertEquals(result[1], [1, 2, 3])

    def test_extract_path4(self):
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
        self.assertEquals(len(result), 2)
        fakes = [31, 123, 45]
        result = graph.extract_paths(vertices, fakes, connections)
        self.assertEquals(len(result), 2)

    def test_extract_path5(self):
        vertices = [i for i in range(0, 20)]
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

        self.assertEquals(len(result), 4)

    def test_to_volume(self, outfile=None):
        nodes = np.array(
            [[
                [323337.37, 2075040.74, 418.68],
                [323338.1769061049, 2075040.573191502, 389.1815055051442]
             ], [
                [323362.41, 2075040.84, 418.54],
                [323362.8466387543, 2075040.62750853, 388.9439834779482]
             ], [
                [323386.11, 2075041.93, 418.45],
                [323386.7158632646, 2075042.203939748, 388.4573694598276]
             ], [
                [323337.31, 2075091.36, 418.77],
                [323338.0870240696, 2075091.841963108, 389.9945235459405]
             ], [
                [323362.3730192074, 2075090.59708967, 376.3910339891728],
                [323362.4566999198, 2075090.490597556, 356.9915067534894]
             ], [
                [323387.7354161257, 2075092.429363151, 377.9407885488984],
                [323387.9758615386, 2075093.073148603, 356.4317642498869]
             ], [
                [323337.37, 2075065.8, 418.97],
                [323337.4684484344, 2075065.743206582, 389.3702182032806]
             ], [
                [323338.387685693, 2075092.028453869, 378.8601432854952],
                [323338.9404280669, 2075092.371302234, 358.3904747276925]
             ], [
                [323386.9416483078, 2075042.30602796, 377.2801158118567],
                [323387.3788796305, 2075042.503721145, 355.6354341053657]
             ], [
                [323387.6036935537, 2075066.779308467, 377.3449812794333],
                [323387.664866292, 2075067.090533435, 356.9274447748566]
             ], [
                [323387.6020091448, 2075092.072169922, 389.8746988709335],
                [323387.7189916482, 2075092.385387101, 379.4100388146766]]]
            )

        edges = [(0, 1), (1, 2), (3, 4), (4, 5), (0, 6), (6, 7), (8, 9), (9, 10)]
        volumes, vertices = graph.to_volume(nodes, edges)

        if outfile is not None:
            with open(outfile, 'w') as obj:
                obj.write(to_obj(vertices, volumes))


if __name__ == '__main__':
    unittest.main()
