# coding: utf-8
import logging

from shapely.wkt import loads
from shapely.ops import transform

from .qgis_hal import (remove_features_from_layer,
                       clone_feature_with_geometry_transform,
                       intersect_linestring_layer_with_wkt,
                       get_name,
                       insert_features_in_layer,
                       create_new_feature,
                       get_all_layer_features,
                       get_feature_attribute_values,
                       intersect_features_with_wkt,
                       intersect_point_layer_with_wkt,
                       qgeom_from_wkt)
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
        remove_features_from_layer(projected_layer)

    logging.debug('projecting {} (geom={})'.format(
        get_name(layer), projected_layer.geometryType()))

    to_project = []
    if not layer.customProperty('graph'):
        to_project = intersect_linestring_layer_with_wkt(
                        layer,
                        line.wkt,
                        line_width)
    else:
        def _i(layer_id, feature_id): return layer_id + '_' + str(feature_id)
        # If it's a graph, we want to to project every feature that
        # connects 2 projected features
        edges = [e for e in get_all_layer_features(layer)]

        layers_features = {}
        for edge in edges:
            lid, start, end = get_feature_attribute_values(
                layer, edge,
                'layer', 'start', 'end')

            if lid in layers_features:
                layers_features[lid] += [start, end]
            else:
                layers_features[lid] = [start, end]

        visible_connected_features = [_i(l, fid)
               for (l, fid) in intersect_features_with_wkt(
                        layers_features, line.wkt, line_width)]

        for edge in edges:
            lid, start, end = get_feature_attribute_values(
                layer, edge,
                'layer', 'start', 'end')

            if _i(lid, start) in visible_connected_features and \
               _i(lid, end) in visible_connected_features:
                to_project += [edge]

    projected_features = [
        clone_feature_with_geometry_transform(
            f,
            partial(project, line, z_scale))
        for f in to_project]

    insert_features_in_layer(projected_features, projected_layer)


def project_layer_as_point(line, z_scale, line_width,
                           layer,
                           projected_layer,
                           remove_all=True):
    "project source features on section plane defined by line"
    logging.debug('Apply projection to layer {}'.format(
        projected_layer.name()))

    if remove_all:
        remove_features_from_layer(projected_layer)

    logging.debug('projecting {} (geom={})'.format(
        get_name(layer), projected_layer.geometryType()))

    to_project = intersect_point_layer_with_wkt(
                    layer,
                    line.wkt,
                    line_width)

    projected_features = [
        clone_feature_with_geometry_transform(
            f,
            partial(project, line, z_scale))
        for f in to_project]

    insert_features_in_layer(projected_features, projected_layer)


def project_layer_as_polygon(line, z_scale, line_width,
                             layer,
                             projected_layer,
                             remove_all=True):
    "project source features on section plane defined by line"

    logging.debug('polygon projection')
    if remove_all:
        remove_features_from_layer(projected_layer)

    logging.debug('projecting {} -> {}'.format(
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
    return qgeom_from_wkt(transform(point_transformation, geom).wkt)
