# coding: utf-8

import os
import math
import itertools

from PyQt4.QtGui import QIcon

from qgis.core import QGis
from shapely.geometry import Point
from shapely.wkt import loads

from .qgis_hal import (
    clone_layer_as_memory_layer,
    get_id,
    create_memory_layer,
    copy_layer_attributes_to_layer,
    init_layer_polygon_renderer)


def max_value(values, default):
    """Return the max of values

    If values is empty, return the `default` value
    """
    return default if len(values) == 0 else max(values)


def icon(name):
    """Return a QIcon instance from the `res` directory
    """
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
    """Project a 3D point

    Carry out a 3D -> 2D transformation.

    Paramaters
    ----------

    line : LineString
    z_scale: float
    x : scalar or tuple
    y : scalar or tuple
    z : scalar or tuple

    Return a coordinate or a list of coords [(x1, x2), (y1, y1), (0, 0)]
    """
    # project a 3d point
    # x/y/z can be scalars or tuples
    # Z axis is mapped on Y axis in projection canvas.
    # We want positive Z going downward, so reverse z_scale
    z_scale = -z_scale
    if isinstance(x, tuple):
        coords_x = ()
        coords_y = ()
        coords_z = tuple((0 for _ in x))
        for xx, yy, zz in zip(x, y, z):
            coords_x += (line.project(Point(xx, yy)),)
            coords_y += (zz * z_scale,)
        return coords_x, coords_y, coords_z
    else:
        coord_x = line.project(Point(x, y))
        coord_y = z * z_scale
        return coord_x, coord_y, 0


def unproject_point(line, z_scale, x, y, z):
    """Unproject a 3D point

    Carry out a 2D -> 3D transformation.

    line : LineString
    z_scale : float
    x : scalar or tuple
    y : scalar or tuple
    z : scalar or tuple

    Return a coordinate or a list of coords [(x1, x2), (y1, y1), (z1, z2)]
    """
    # Z axis is mapped on Y axis in projection canvas.
    # We want positive Z going downward, so reverse z_scale
    z_scale = -z_scale
    if isinstance(x, tuple):
        coords_x = ()
        coords_y = ()
        for xx in x:
            q = line.interpolate(xx)
            coords_x += (q.x, )
            coords_y += (q.y, )
        return (coords_x, coords_y, tuple((v / z_scale for v in y)))
    else:
        q = line.interpolate(x)
        return (q.x, -q.y, y / z_scale)


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

    if abs(unit[1]) > 0.7:
        # order along growing Y if Y direction is important
        reverse = unit[1] < 0
    else:
        # default: order along growing X
        reverse = unit[0] < 0

    return sorted(projections, key=projections.get, reverse=reverse)


def centroids_to_line_wkt(centroids):
    points = []
    for coords in centroids:
        points += [' '.join(str(x) for x in coords)]
    return 'LINESTRING({})'.format(', '.join(points))


def distance2(coords1, coords2):
    """compute squared distance between two points
    """
    return sum([pow(x - y, 2) for x, y in zip(coords1, coords2)])


def length(coords):
    return math.sqrt(sum([x*x for x in coords]))
