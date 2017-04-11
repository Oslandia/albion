# coding: utf-8

"""
This module deals with the creation of surfaces and volumes from a graph
linking line segments.

Since we deal with non-planar surfaces, the representation is TIN,
the same holds for the exterior shell of volumes.
"""

import numpy
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import cascaded_union
from collections import defaultdict
import itertools
import logging


def to_surface(nodes, edges):
    """nodes is a numpy array of 2D line segments [n,2,2]
    edge is a iterable of pairs of int [m,2] indexing the nodes.

    the segments must be consistently oriented.

    the return value is a multipolygon.
    """
    return cascaded_union(
            MultiPolygon([Polygon([nodes[edge[0], 0], nodes[edge[0], 1],
                         nodes[edge[1], 1], nodes[edge[1], 0]])
                         for edge in edges]))


def find_4_cycles(edges):
    """return all unique four-cycles in graph"""
    # for each node, add a list of reachable nodes
    # for all pairs of reachable node test if they share a reachable node -> cycle
    reachables = defaultdict(set)
    for edge in edges:
        reachables[edge[0]].add(edge[1])
        reachables[edge[1]].add(edge[0])

    loops = {}
    for a, reachable in reachables.iteritems():
        for b, c in itertools.combinations(reachable, 2):
            for d in reachables[b].intersection(reachables[c]).difference(set([a])):
                loops[tuple(sorted([a, b, d, c]))] = [a, b, d, c]

    return loops.values()


def to_volume(nodes, edges):
    """nodes is a numpy array of 3D line segments [n,2,3]
    edge is a iterable of pairs of int [m,2] indexing the nodes.
    """

    def orient(ring, nodes):
        up = nodes[ring[0], 0] - nodes[ring[0], 1]
        n = numpy.cross(nodes[ring[1], 0] - nodes[ring[0], 0],
                        nodes[ring[2], 0] - nodes[ring[1], 0])
        return ring if numpy.dot(up, n) > 0 else list(reversed(ring))

    rings = [orient(r, nodes) for r in find_4_cycles(edges)]

    logging.debug(rings)

    # we build elementary volumes for each cell
    # the vertices are a flattened version of the nodes, so top
    # is 2*n and bottom 2*n+1
    volumes = []
    for ring in rings:
        top = [[2*ring[0], 2*ring[1], 2*ring[2]]] + (
              [[2*ring[0], 2*ring[2], 2*ring[3]]] if len(ring) == 4 else [])
        bottom = [[2*ring[2]+1, 2*ring[1]+1, 2*ring[0]+1]] + (
                 [[2*ring[3]+1, 2*ring[2]+1, 2*ring[0]+1]] if len(ring) == 4 else [])
        sides = [[2*a, 2*b, 2*a+1] for a, b in zip(ring, ring[1:]+[ring[0]])] \
                + [[2*a+1, 2*b, 2*b+1] for a, b in zip(ring, ring[1:]+[ring[0]])]
        volumes.append(top+bottom+sides)

    #  @todo we union elementary volumes

    return numpy.array(volumes), nodes.reshape(-1, 3)

def _find_path(start_point, vertices, open_starts, connections):
    # build path
    path = []

    current = start_point
    previous = None

    while True:
        idx = vertices.index(current)
        forward_edges = filter(lambda x: x != previous, connections[idx])

        logging.debug('\tCurrent {} (previous:{}) -> choices {}'.format(
            current, previous, forward_edges))
        previous = current
        path += [current]
        # only keep forward edges
        connections[idx] = forward_edges

        if len(forward_edges) == 0 or (
                current in open_starts and current != start_point):
            break

        # use last connection
        current = forward_edges[-1]
        forward_edges.pop()
        # update remaining connection
        connections[idx] = forward_edges

    return (path if (
        len(path) > 1 and path[-1] in open_starts) else [], connections)


def extract_paths(vertices, open_starts, connections):
    paths = []

    conn = connections[:]

    # loop on possible starts
    for f in open_starts:
        logging.debug('** Searching path starting with {} **'.format(f))
        while True:
            p, conn = _find_path(f, vertices, open_starts, conn)

            if p:
                logging.debug('Found path {}\n'.format(p))
                paths += [p]
            else:
                break

    return paths
