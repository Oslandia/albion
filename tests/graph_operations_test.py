# coding=utf-8
import unittest

from hypothesis import given, reject
from hypothesis.strategies import integers, lists, builds, floats
from mock import patch
from functools import partial
from shapely.wkt import loads

# from .graph_operations import build_subgraph_from_graph_in_section
from albion.graph_operations import (build_subgraph_from_graph_in_section,
                                     _is_feature_a_polygon_extremity,
                                     _extract_connectivity_information,
                                     _extract_section_polygons_information,
                                     GraphConnection,
                                     graph_connection_list_to_list,
                                     compute_segment_geometry)


class FakeLayer():
    def customProperty(self, prop):
        return 'dummy'


class FakeFeature():
    def __init__(self, i): self.__id = i

    def id(self): return self.__id


class TestBuildSubGraph(unittest.TestCase):
    @patch('albion.graph_operations.get_all_features_attributes',
           return_value=[])
    def test_no_feature(self, mock_get_all_features_attributes):
        self.assertEqual([],
                         build_subgraph_from_graph_in_section(
                                FakeLayer(),
                                FakeLayer(),
                                FakeLayer()))

    @patch('albion.graph_operations.get_all_features_attributes',
           return_value=[(1, FakeFeature(2), FakeFeature(3))])
    @patch('albion.graph_operations.get_layer_by_id', return_value=1)
    @patch('albion.graph_operations.get_feature_by_id',
           side_effect=lambda l, f: f)
    @patch('albion.graph_operations.get_intersecting_features',
           side_effect=lambda l, f: [f])
    @patch('albion.graph_operations.query_layer_features_by_attributes',
           return_value=[])
    def test_1_feature(self, m1, m2, m3, m4, m5):
        self.assertEqual([[2, 3]],
                         build_subgraph_from_graph_in_section(
                                FakeLayer(),
                                FakeLayer(),
                                FakeLayer()))


class Test_is_feature_a_polygon_extremity(unittest.TestCase):

    @patch('albion.graph_operations.layer_has_field', return_value=False)
    @given(lists(integers(), min_size=3, max_size=10))
    def test_pants_is_a_polygon_extremity(self, m1, connections):
        self.assertTrue(_is_feature_a_polygon_extremity(
            connections, None, None))

    @patch('albion.graph_operations.layer_has_field', return_value=True)
    @patch('albion.graph_operations.get_feature_attribute_values',
        return_value='Fake')
    def test_fake_generatrice_is_a_polygon_extremity(self, m1, m2):
        self.assertTrue(_is_feature_a_polygon_extremity(
            [], None, None))


class FeatureEdgeDesc():
    def __init__(self, features_id, layers):
        self.generatrice_layer = layers[0]
        self.graph_layer = layers[1]
        self.ids = features_id
        self.features = [('feature', i) for i in features_id]
        self.edges = [('edge', features_id[i], features_id[i + 1], i)
                      for i in range(0, len(features_id)-1)]  # N-1 edges

    def __str__(self):
        return 'layers=({}, {}) features={} edges={}'.format(
            self.generatrice_layer, self.graph_layer,
            self.features, self.edges)


feature_edge_desc = builds(
    FeatureEdgeDesc,
    lists(integers(), unique=True, min_size=3, max_size=10),
    lists(integers(), unique=True, min_size=2, max_size=2))


# simple mock returning a single edge between each pair of vertices
def mock_query_layer_features_by_attributes(self, feature_desc,
                                            layer, *attr):
    if layer is feature_desc.graph_layer:
        if attr[0].keys()[0] is 'layer':
            return feature_desc.edges
        elif attr[0].keys()[0] is 'link':
            return feature_desc.edges[attr[0]['link']]

    self.assertFalse('unsupported args layer="{}", params="{}"'.format(
        layer, attr))


def mock_get_feature_attribute_values(self, feature_desc,
                                      layer, edge, *attr):
    self.assertEqual(layer, feature_desc.graph_layer)
    self.assertEqual(len(attr), 3)
    return edge[1:4]


class Test_extract_connectivity_information(unittest.TestCase):

    @patch('albion.graph_operations.query_layer_features_by_attributes')
    @patch('albion.graph_operations.get_feature_attribute_values')
    @given(feature_edge_desc)
    def test_(self,
              mock_get_feature,
              mock_query_layer,
              test_feature_edge_desc):
        mock_query_layer.side_effect = partial(
            mock_query_layer_features_by_attributes,
            self, test_feature_edge_desc)
        mock_get_feature.side_effect = partial(
            mock_get_feature_attribute_values,
            self, test_feature_edge_desc)

        c = _extract_connectivity_information(
            test_feature_edge_desc.graph_layer,
            test_feature_edge_desc.ids,
            test_feature_edge_desc.generatrice_layer)

        self.assertEqual(len(c[0]), 1)
        self.assertEqual(len(c[-1]), 1)
        for i in range(1, len(test_feature_edge_desc.ids)-1):
            self.assertEqual(len(c[i]), 2)


class Test_extract_section_polygons_information(unittest.TestCase):
    @patch('albion.graph_operations.get_feature_centroid')
    @patch('albion.graph_operations.is_fake_feature')
    @patch('albion.graph_operations.query_layer_features_by_attributes')
    @patch('albion.graph_operations.get_feature_attribute_values')
    @patch('albion.graph_operations.intersect_linestring_layer_with_wkt')
    @patch('albion.graph_operations.get_id', side_effect=lambda x: x)
    @given(feature_edge_desc)
    def test(self,
             mock_get_id,
             mock_intersects,
             mock_get_feature,
             mock_query_layer,
             mock_fake_feature,
             mock_feature_centroid,
             test_feature_edge_desc):
        projected_graph_layer = 'projected_graph_layer'

        mock_intersects.return_value = test_feature_edge_desc.features
        mock_query_layer.side_effect = partial(
            mock_query_layer_features_by_attributes,
            self, test_feature_edge_desc)
        mock_get_feature.side_effect = partial(
            mock_get_feature_attribute_values,
            self, test_feature_edge_desc)
        mock_fake_feature.side_effect = lambda l, f: \
            f in (test_feature_edge_desc.features[0],
                  test_feature_edge_desc.features[-1])

        def centroid(f):
            self.assertTrue(f[0] in ('edge', 'feature'))
            if f[0] is 'edge':
                return (test_feature_edge_desc.edges.index(f), 0)
            else:
                return (test_feature_edge_desc.features.index(f), 0)
        mock_feature_centroid.side_effect = centroid

        class line(object):
            def __init__(self):
                self.wkt = 'unused'

            def project(self, *p):
                return p

        extremities, features_of_interest_id, connections, pants = \
            _extract_section_polygons_information(
                line(), 1,
                test_feature_edge_desc.graph_layer,
                test_feature_edge_desc.generatrice_layer,
                projected_graph_layer)

        self.assertEqual(len(extremities), 2)


class Test_GraphConnection(unittest.TestCase):
    def test(self):
        c = [
            [GraphConnection(0, 2, 'x')],
            [GraphConnection(1, 2, 'x'), GraphConnection(1, 3, 'x'), GraphConnection(1, 4, 'x')],
            [GraphConnection(2, 1, 'x'), GraphConnection(2, 0, 'x')],
            [GraphConnection(3, 1, 'x')],
            [GraphConnection(4, 1, 'x')],
            []]

        result = graph_connection_list_to_list(c, [0, 1, 2, 3, 4, 5])
        self.assertEqual(len(result), 6)
        self.assertEqual(len(result[0]), 1)
        self.assertEqual(len(result[1]), 3)
        self.assertEqual(len(result[2]), 2)
        self.assertEqual(len(result[3]), 1)
        self.assertEqual(len(result[4]), 1)
        self.assertEqual(len(result[5]), 0)


class Test_compute_segment_geometry(unittest.TestCase):
    @given(lists(floats(max_value=1e+100, min_value=-1e+100),
                 min_size=6, max_size=6),
           lists(floats(max_value=1e+100, min_value=-1e+100),
                 min_size=6, max_size=6))
    def test_3d(self, f1, f2):
        wkt1 = 'LINESTRING Z({} {} {}, {} {} {})'.format(*f1)
        wkt2 = 'LINESTRING Z({} {} {}, {} {} {})'.format(*f2)

        a = loads(wkt1)
        b = loads(wkt2)

        if not a.is_valid or \
           not b.is_valid or \
           a.almost_equals(b, decimal=4) or \
           a.union(b).almost_equals(a, decimal=4):
            reject()

        try:
            linestring = compute_segment_geometry(wkt1, wkt2)
            self.assertTrue(linestring.is_valid)
        except Exception as e:
            if e.message.find('Cannot compute segment geometry') == 0:
                reject()
            else:
                raise e







if __name__ == '__main__':
    unittest.main()
