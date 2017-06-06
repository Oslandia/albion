# coding: utf-8

import logging
import traceback
from operator import xor

from shapely.geometry import LineString
from shapely.wkt import loads

from .qgis_hal import (
    query_layer_feature_by_id,
    get_layer_max_feature_attribute,
    get_all_features_attributes,
    get_feature_by_id,
    get_layer_by_id,
    get_intersecting_features,
    query_layer_features_by_attributes,
    get_layer_unique_attribute,
    intersect_linestring_layer_with_wkt,
    get_feature_attribute_values,
    get_id,
    compute_feature_length,
    get_feature_centroid,
    feature_to_shapely_wkt,
    get_all_layer_features,
    query_layer_features_by_attributes_in,
    get_layer_features_count_by_attributes,
    layer_has_field,
    remove_features_from_layer,
    qgeom_from_wkt)
from .graph import extract_paths
from .utils import project_point


def is_fake_feature(layer, feature):
    for field in ['HoleId']:
        if layer_has_field(layer, field):
            h = get_feature_attribute_values(layer, feature, field)
            return h == 'Fake'
    for field in ['mine', 'mine:Integer64(10,0)']:
        if layer_has_field(layer, field):
            field = get_feature_attribute_values(layer, feature, field)
            return h == -1

    return False


class GraphConnection():
    def __init__(self, fro_, t_, edge_feature_link_):
        self.from_ = fro_
        self.to_ = t_
        self.edge_feature_link = edge_feature_link_

    def __getattr__(self, name):
        if name == 'other':
            return self.to_
        if name == 'start':
            return self.from_
        elif name == 'edge_link':
            return self.edge_feature_link
        raise AttributeError(name)


def graph_connection_list_to_list(connections, ids):
    result = [[] for i in ids]
    for c in connections:
        i = connections.index(c)
        for ci in c:
            assert ci.start == ids[i]
            result[ids.index(ci.start)] += [ci.other]

    return result


def compute_section_polygons_from_graph(graph_layer, graph_projection,
                                        line, line_width,
                                        limit_to_layers_id=None):
    """ Convert connectivity and geometries to polygons

    Return value is a list of polygons.
    Each polygon is a list of vertices
    Each vertices is a list of 3 coords (x,y,z)
    """
    result = []

    try:
        # read unique layers (of generating lines) that are connected
        layers = get_layer_unique_attribute(graph_layer, 'layer') \
            if limit_to_layers_id is None else limit_to_layers_id

        logging.debug('Polygon export [source layers: {}]'.format(layers))

        for lid in layers:
            projected_feature_count = get_layer_features_count_by_attributes(
                graph_projection, {'layer': lid})

            logging.debug('  - processing layer {}. Features: {}|{}'.format(
                lid, projected_feature_count, graph_projection.featureCount()))

            if projected_feature_count == 0:
                continue

            generatrice_layer = get_layer_by_id(lid)

            polygons_extremities, considered_ids, connections, pants =\
                _extract_section_polygons_information(line, line_width,
                                                      graph_layer,
                                                      generatrice_layer,
                                                      graph_projection)

            logging.debug('polygons_extremities {}'.format(
                polygons_extremities))

            if len(polygons_extremities) == 0:
                continue

            # compute all features length (3d)
            features_length = {}
            for i in considered_ids:
                feature = get_feature_by_id(generatrice_layer, i)
                features_length[i] = compute_feature_length(feature)

            paths = extract_paths(considered_ids,
                                  polygons_extremities,
                                  graph_connection_list_to_list(
                                      connections,
                                      considered_ids))

            for path in paths:
                polygon = __path_to_polygon(path,
                                            generatrice_layer,
                                            pants,
                                            features_length,
                                            pants)
                if len(polygon) > 0:
                    result += [polygon]

    except Exception as e:
        logging.error(e)
        traceback.print_exc()
    finally:
        return result


def find_generatrices_needing_a_fake_generatrice_in_section(
            line,
            graph_layer,
            source_layer,
            projected_layer):
    projected_generatrice_centroids = {}
    for feature in get_all_layer_features(projected_layer):
        link = get_feature_attribute_values(projected_layer, feature, 'link')
        projected_generatrice_centroids[link] = get_feature_centroid(feature)

    logging.info(source_layer.id())
    logging.info(projected_generatrice_centroids)

    source_features = list(
        query_layer_features_by_attributes_in(
                    source_layer,
                    {'link': projected_generatrice_centroids.keys()}))

    connections = _extract_connectivity_information(
        graph_layer,
        [get_id(f) for f in source_features],
        get_id(source_layer))

    ids_missing_generatrice_left = []
    ids_missing_generatrice_right = []

    logging.info(source_features)
    logging.info(connections)

    for i in range(0, len(source_features)):
        source_feature = source_features[i]
        if is_fake_feature(source_layer, source_feature):
            continue

        centroid = get_feature_centroid(source_feature)

        if len(connections[i]) == 0:
            ids_missing_generatrice_left += [(get_id(source_feature), [])]
            ids_missing_generatrice_right += [(get_id(source_feature), [])]
            continue

        logging.info('feat: {} (centroid={} -> {})'.format(
            source_feature.id(),
            centroid,
            project_point(line, 1.0, *centroid)))
        edges = __compute_generatrice_connections(
            project_point(line, 1.0, *centroid)[0],
            connections[i],
            line,
            graph_layer)

        # If this feature is connected on one side only ->
        # add the missing generatrice on the other side
        if xor(len(edges['L']) == 0, len(edges['R']) == 0):
            if len(edges['R']) == 0:
                ids_missing_generatrice_right += [
                    (get_id(source_feature), edges['L'])]
            else:
                ids_missing_generatrice_left += [
                    (get_id(source_feature), edges['R'])]

    return ids_missing_generatrice_left, ids_missing_generatrice_right


def compute_segment_geometry(feature1_wkt, feature2_wkt):
    """ Returns a geometry (LineString) connecting features centers """
    def mysum(x, a, b):
        return [(a[i] + b[i]) * x for i in range(0, 3)]

    def bary(coords):
        return reduce(lambda x, y: mysum(1.0 / len(coords), x, y), coords)

    geom1 = loads(feature1_wkt)
    centroid1_with_z = bary(geom1.coords)

    geomB = loads(feature2_wkt)
    centroid2_with_z = bary(geomB.coords)

    result = LineString([centroid1_with_z, centroid2_with_z])

    if not result.is_valid:
        raise Exception(
            'Cannot compute segment geometry connecting {} and {}'.format(
                feature1_wkt, feature2_wkt))
    return result


def refresh_graph_layer_edges(self, graph_layer):
    """ Browse edges and either update geometries or delete edges """
    if graph_layer is None:
        return

    graph_layer.beginEditCommand('edges geom')

    # Store invalid graph elements for removal
    edge_to_remove = []
    for edge in graph_layer.getFeatures():
        layer_id = get_feature_attribute_values(graph_layer, edge, 'layer')

        feat1 = query_layer_feature_by_id(layer_id,
                                          edge.attribute('start'))
        feat2 = query_layer_feature_by_id(layer_id,
                                          edge.attribute('end'))

        if feat1 and feat2:
            try:
                line_string = compute_segment_geometry(
                    feature_to_shapely_wkt(feat1),
                    feature_to_shapely_wkt(feat2))

                # update geometry
                graph_layer.dataProvider().changeGeometryValues(
                    {edge.id(): qgeom_from_wkt(line_string.wkt)})
            except Exception as e:
                logging.error(e)
        else:
            # feat1|feat2 has been removed -> remove edge as well
            edge_to_remove += [edge.id()]

    self.graphLayerHelper.layer().endEditCommand()

    if len(edge_to_remove) > 0:
        remove_features_from_layer(self.graphLayerHelper.layer(), edge_to_remove)


def build_subgraph_from_graph(graph_layer, subgraph_layer, generatrice_layer):
    """ Build subgraph edges from graph edges

    Performs intersections between each pair of feature connected in graph
    layers and each feature in generatrice_layer.
    If an intersection is found then add a new edge in subgraph.

    Note: if both graph_layer and generatrice_layer are projected layers, then
    the process will be done only for the active section. Otherwise the process
    is executed for the whole graph
    """

    # consistency check
    if (graph_layer.customProperty('section_id') !=
            generatrice_layer.customProperty('section_id')):
        logging.error('''
            graph and generatrice must be either both projection, or both
             non-projection
            ''')

    features = []

    my_id = get_layer_max_feature_attribute(subgraph_layer, 'link')

    for layer_id, start, end in get_all_features_attributes(graph_layer,
                                                            'layer',
                                                            'start',
                                                            'end'):
        layer = get_layer_by_id(layer_id)
        start = get_feature_by_id(layer, start)
        end = get_feature_by_id(layer, end)

        # select all features of source_layer intersecting 'start'
        s = source_layer.getFeatures(QgsFeatureRequest(start.geometry().boundingBox()))
        # select all features of source_layer intersecting 'end'
        e = source_layer.getFeatures(QgsFeatureRequest(end.geometry().boundingBox()))

        for a in s:
            e = source_layer.getFeatures(QgsFeatureRequest(end.geometry().boundingBox()))
            for b in e:
                req = QgsFeatureRequest().setFilterExpression (u'"start" = {0} AND "end" = {1}'.format(a.id(), b.id()))
                # don't recreate an existing link
                if len(list(graphLayer.getFeatures(req))) > 0:
                    continue

                features += [ GraphEditTool.createSegmentEdge(a, b, my_id, subGraphLayer.fields(), source_layer.id()) ]
                my_id = my_id + 1

    if len(features) > 0:
        insert_features_in_layer(features, subGraphLayer)


def build_subgraph_from_graph_in_section(graph_layer,
                                         subgraph_layer,
                                         generatrice_layer):
    """ Build subgraph edges from graph edges

    Performs intersections between each pair of feature connected in graph
    layers and each feature in generatrice_layer.
    If an intersection is found then adds a new edge [id1, id2] to the
    returned list
    """

    # consistency check
    graph_section_id = graph_layer.customProperty('section_id')
    gen_layer_section_id = generatrice_layer.customProperty('section_id')

    assert graph_section_id is not None
    assert gen_layer_section_id is not None
    assert graph_section_id == gen_layer_section_id

    edges = []

    for layer_id, start, end in get_all_features_attributes(graph_layer,
                                                            'layer',
                                                            'start',
                                                            'end'):
        layer = get_layer_by_id(layer_id)
        start = get_feature_by_id(layer, start)
        end = get_feature_by_id(layer, end)

        # select all features of source_layer intersecting 'start'
        intersecting_start = list(get_intersecting_features(
            generatrice_layer, start))
        # select all features of source_layer intersecting 'end'
        intersecting_end = list(get_intersecting_features(
            generatrice_layer, end))

        # filter duplicates
        intersecting_end = filter(lambda f: not f.id() in intersecting_start,
                                  intersecting_end)

        for a in intersecting_start:
            for b in intersecting_end:
                # verify that edge doesnt exist
                a_id = get_id(a)
                b_id = get_id(b)

                existing_edges = query_layer_features_by_attributes(
                    subgraph_layer, {
                        'start': a_id,
                        'end': b_id
                    })

                if len(list(existing_edges)) > 0:
                    continue

                # verify that reverse edge doesnt exist
                existing_edges = query_layer_features_by_attributes(
                    subgraph_layer, {
                        'end': a_id,
                        'start': b_id
                    })

                if len(list(existing_edges)) > 0:
                    continue

                edges += [[a_id, b_id]]

    return edges


def _extract_connectivity_information(graph_layer,
                                      all_features_id,
                                      layer_id):
    connections = [[] for id_ in all_features_id]

    for edge in query_layer_features_by_attributes(graph_layer, {
            'layer': layer_id}):

        start_id, end_id, edge_link = get_feature_attribute_values(
                                            graph_layer,
                                            edge,
                                            'start', 'end', 'link')

        if not (start_id in all_features_id):
            continue

        if not (end_id in all_features_id):
            continue

        connections[all_features_id.index(start_id)] += [
            GraphConnection(start_id, end_id, edge_link)]
        connections[all_features_id.index(end_id)] += [
            GraphConnection(end_id, start_id, edge_link)]

    return connections


def _is_feature_a_polygon_extremity(connections, generatrice_layer, feature):
    """ Return True if given feature can be a polygon extremity

    Extremities can be either:
       - fake generatrice
       - vertex with > 1 connections on 1 side ("pants")
    """
    return len(connections) > 2 or is_fake_feature(
        generatrice_layer, feature)


def __compute_generatrice_connections(projected_feature_centroid_x,
                                      feature_graph_connections,
                                      line,
                                      graph_layer):
    result = {'L': [], 'R': []}
    for connection in feature_graph_connections:
        _e = list(query_layer_features_by_attributes(
            graph_layer, {'link': connection.edge_link}))
        assert len(_e) == 1
        e = _e[0]
        other = connection.other

        centroid = project_point(line, 1.0, *get_feature_centroid(e))

        # logging.info('{} {} | {} <? {}'.format(get_feature_centroid(e), centroid, projected_feature_centroid_x, centroid[0]))
        if projected_feature_centroid_x < centroid[0]:
            result['R'] += [other]
        else:
            result['L'] += [other]

    # check for data inconsistencies
    # TODO: expose this problem to the user
    assert len(result['R']) == len(set(result['R']))
    assert len(result['L']) == len(set(result['L']))

    return result


def _extract_section_polygons_information(line, line_width,
                                          graph,
                                          generatrice_layer,
                                          projected_graph_layer):

    features_of_interest = list(intersect_linestring_layer_with_wkt(
            generatrice_layer, line.wkt, line_width))

    features_of_interest_id = [get_id(f)
                               for f in features_of_interest]

    connections = _extract_connectivity_information(
        graph,
        features_of_interest_id,
        get_id(generatrice_layer))

    extremities = []
    pants = {}
    # extract generatrices belonging to section
    idx = 0
    for feature in features_of_interest:
        if _is_feature_a_polygon_extremity(
                connections[idx],
                generatrice_layer,
                feature):
            feature_id = get_id(feature)
            extremities += [feature_id]

            centroid = get_feature_centroid(feature)

            pants[feature_id] = __compute_generatrice_connections(
                project_point(line, 1.0, *centroid)[0],
                connections[idx],
                line,
                graph)

        idx = idx + 1

    return extremities, features_of_interest_id, connections, pants


def __select_pants_branch(current_id, next_id, pants):
    if next_id in pants['L']:
        return pants['L']
    if next_id in pants['R']:
        return pants['R']
    return None


def _compute_ratio_offset_from_pants(layer,
                                     current,
                                     next_,
                                     pants,
                                     features_length):
    connections_to_consider = __select_pants_branch(
        current,
        next_,
        pants)

    if connections_to_consider is None or len(
            connections_to_consider) <= 1:
        return 1.0, 0.0

    next_feature = get_feature_by_id(layer, next_)
    center_z = get_feature_centroid(next_feature)[2]

    offset = 0
    power_sum = 0
    for feat_id in connections_to_consider:
        power_sum += features_length[feat_id]

        other_feat = get_feature_by_id(layer, feat_id)
        if center_z < get_feature_centroid(other_feat)[2]:
            offset += features_length[feat_id]

    ratio = features_length[next_] / power_sum
    offset /= power_sum
    return ratio, offset


def __path_to_polygon(path, layer, connections, features_length, pants):
    vertices = []

    logging.debug('path = {}'.format(path))
    logging.debug('features_length = {}'.format(features_length))
    logging.debug('pants = {}'.format(pants))
    for i in range(0, len(path)):
        v = path[i]

        ratio = 1.0
        offset = 0.0

        if v in pants:
            # pants can only be at the beginning|end of a path
            assert i is 0 or i is (len(path) - 1)

            next_v = path[(i + 1) if (i == 0) else (i - 1)]
            ratio, offset = _compute_ratio_offset_from_pants(
                layer, v, next_v, pants[v], features_length)

            logging.info('ration={} offset={}'.format(ratio, offset))

        geom = loads(feature_to_shapely_wkt(get_feature_by_id(layer, v)))

        length = features_length[v]
        norm = [
            (geom.coords[1][i] - geom.coords[0][i]) / length
            for i in range(0, 3)]

        v0 = [
            geom.coords[0][i] + norm[i] * length * offset for i in range(0, 3)]
        v1 = [v0[i] + norm[i] * length * ratio for i in range(0, 3)]

        vertices += [v0]
        vertices += [v1]

    return vertices


def does_edge_already_exist(graph_layer, layer_id, feature1_id, feature2_id):
    for f in query_layer_features_by_attributes(graph_layer,
                                                {'layer': layer_id}):
        start, end = get_feature_attribute_values(graph_layer, f,
                                                  'start', 'end')
        if start == feature1_id and end == feature2_id or \
           start == feature2_id and end == feature1_id:
            return True
    return False
