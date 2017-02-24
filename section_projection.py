# coding=utf-8
import logging

from shapely.wkt import loads
from shapely.ops import transform

from qgis.core import (QgsGeometry)

from .qgis_hal import (remove_all_features_from_layer,
                       clone_feature_with_geometry_transform,
                       intersect_linestring_layer_with_wkt,
                       get_name,
                       insert_features_in_layer,
                       create_new_feature)
from .graph_operations import compute_section_polygons_from_graph
from .utils import create_projected_layer, project_point, unproject_point

from functools import partial


def project(line, z_scale, qgs_geometry):
    return __transform(qgs_geometry,
                       partial(project_point, line, z_scale))


def unproject(line, z_scale, qgs_geometry):
    return __transform(qgs_geometry,
                       partial(unproject_point, line, z_scale))


def project_layer_as_linestring(line, z_scale, line_width,
                                layer,
                                projected_layer,
                                remove_all=True):
    "project source features on section plane defined by line"
    logging.debug('Apply projection to layer {}'.format(
        projected_layer.name()))

    if remove_all:
        remove_all_features_from_layer(projected_layer)

    logging.debug('projecting {} (geom={})'.format(
        get_name(layer), projected_layer.geometryType()))

    projected_features = [
        clone_feature_with_geometry_transform(
            f,
            partial(project, line, z_scale))
        for f in intersect_linestring_layer_with_wkt(
            layer,
            line.wkt,
            line_width)]

    insert_features_in_layer(projected_features, projected_layer)


def project_layer_as_polygon(line, z_scale, line_width,
                             layer,
                             projected_layer,
                             remove_all=True):
    "project source features on section plane defined by line"

    logging.debug('polygon projection')
    if remove_all:
        remove_all_features_from_layer(projected_layer)

    logging.info('projecting {} -> {}'.format(
        get_name(layer),
        projected_layer.geometryType()))

    # build a temporary layer to hold graph_layer features projections
    graph_projection = create_projected_layer(layer, 'dummy')
    project_layer_as_linestring(line, 1.0, line_width,
                                layer, graph_projection)

    polygons = compute_section_polygons_from_graph(layer, graph_projection,
                                                   line, line_width)

    for p in polygons:
        # project each vertices
        vertices = []
        for idx in range(0, len(p), 2):
            vertices += [list(project_point(line, z_scale, *p[idx]))]
        for idx in range(len(p)-1, 0, -2):
            vertices += [list(project_point(line, z_scale, *p[idx]))]
        vertices += [vertices[0]]

        wkt = ' '.join(str(x) for x in vertices[0])
        for v in vertices[1:]:
            wkt += ', {}'.format(' '.join(str(x) for x in v))

        wkt = 'POLYGON Z (({}))'.format(wkt)

        try:
            feature = create_new_feature(projected_layer, wkt)
            insert_features_in_layer([feature], projected_layer)
        except Exception as e:
            logging.error(
                'Failed to create polygon. Invalid wkt. {}'.format(e))


def __transform(qgs_geometry, point_transformation):
    """returns a transformed geometry"""
    # TODO use wkb to optimize ?
    geom = loads(qgs_geometry.exportToWkt().replace("Z", " Z"))
    return QgsGeometry.fromWkt(
            transform(
                lambda x, y, z: point_transformation(x, y, z),
                geom).wkt)
