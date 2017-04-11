# coding: utf-8

import itertools

from PyQt4.QtGui import QIcon

from qgis.core import QGis
from shapely.geometry import Point
from shapely.wkt import loads

import os
import math

from .qgis_hal import (
    clone_layer_as_memory_layer,
    get_id,
    create_memory_layer,
    copy_layer_attributes_to_layer,
    init_layer_polygon_renderer)


def max_value(values, default):
    return default if len(values) == 0 else max(values)


def icon(name):
    return QIcon(os.path.join(os.path.dirname(__file__), 'res', name))


def create_projected_layer(layer, section_id):
    return clone_layer_as_memory_layer(
        layer,
        {
            'section_id': section_id,
            'projected_layer': get_id(layer)
        })


def create_projected_polygon_layer(layer, section_id):
    polygon_layer = create_memory_layer(
            QGis.Polygon,
            layer.crs(),
            layer.name() + '_polygon',
            {
                'polygon_projected_layer': layer.id(),
                'section_id': section_id
            })

    polygon_layer.setReadOnly(True)

    copy_layer_attributes_to_layer(layer, polygon_layer)

    # cpy style
    init_layer_polygon_renderer(polygon_layer)

    return polygon_layer


def project_point(line, z_scale, x, y, z=0):
    # project a 3d point
    # x/y/z can be scalars or tuples
    if isinstance(x, tuple):
        _x = ()
        _y = ()
        _z = tuple((0 for i in range(0, len(x))))
        for i in range(0, len(x)):
            _x += (line.project(Point(x[i], y[i])),)
            _y += (z[i] * z_scale,)
        return (_x, _y, _z)
    else:
        _x = line.project(Point(x, y))
        _y = z * z_scale
        return (_x, _y, 0)


def unproject_point(line, z_scale, x, y, z):
    # 2d -> 3d transfomration
    # x/y/z can be scalars or tuples
    if isinstance(x, tuple):
        _x = ()
        _y = ()
        for i in range(0, len(x)):
            q = line.interpolate(x[i])
            _x += (q.x, )
            _y += (q.y, )

        return (_x,
                _y, tuple((v / z_scale for v in y)))
    else:
        q = line.interpolate(x)
        return (q.x, q.y, y / z_scale)


def sort_id_along_implicit_centroids_line(centroids):
    ''' Receive a dict of 'id: centroid' and returns a sorted list of id.
        Centroids are [] of 2 coords '''
    # find the 2 furthest elements
    extrema = []
    max_distance = 0

    for (i, left), (j, right) in itertools.combinations(centroids.iteritems(), 2):
        d = distance2(left, right)
        if d > max_distance:
            extrema = [left, right]
            max_distance = d

    line_wkt = centroids_to_line_wkt(extrema)
    line = loads(line_wkt)

    # project all centroids on this line
    projections = {}
    for k in centroids:
        x, y = centroids[k]
        projections[k] = line.project(Point(x, y))
    unit = [(extrema[1][i] - extrema[0][i]) / line.length for i in [0, 1]]
    # order along growing X
    reverse = unit[0] < 0
    return sorted(projections, key=projections.get, reverse=reverse)


def centroids_to_line_wkt(centroids):
    points = []
    for coords in centroids:
        points += [' '.join(str(x) for x in coords)]
    return 'LINESTRING({})'.format(', '.join(points))


def distance2(coords1, coords2):
    """compute the euclidean distance between two 2D points
    """
    return sum([pow(x - y, 2) for x,y in zip(coords1, coords2)])

def length(coords):
    return math.sqrt(sum([x*x for x in coords]))
