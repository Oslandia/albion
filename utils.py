# coding=utf-8
from PyQt4.QtGui import QIcon

from qgis.core import QGis
from shapely.geometry import Point

import os
import logging

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
