# coding=utf-8

from qgis.core import QgsFeatureRequest
from shapely.geometry import Point
from .qgis_hal import (insert_features_in_layer,
                       get_id,
                       create_new_feature,
                       clone_feature_with_geometry_transform,
                       get_feature_attribute_values,
                       feature_to_shapely_wkt)
from .graph_operations import compute_segment_geometry


# Helper methods to manage fake generatrices
def create(section, source_layer, source_feature, link, translation, sign):
    source_has_field_HoleID = source_layer.fields().fieldNameIndex(
        'HoleID') >= 0
    source_has_field_mine = source_layer.fields().fieldNameIndex(
        'mine') >= 0

    fake = clone_feature_with_geometry_transform(
        source_feature,
        lambda geom: geom.translate(
            translation[0] * sign, translation[1] * sign))

    if source_has_field_HoleID:
        fake.setAttribute('HoleID', 'Fake')
    if source_has_field_mine:
        fake.setAttribute('mine', -1)
    fake.setAttribute('link', link)
    fake.setGeometry(source_feature.geometry())

    fake.geometry().translate(translation[0] * sign, translation[1] * sign)

    # we need to make sure that the newly created geometry is inside the section
    buf = section.line.buffer(section.width, cap_style=2)
    centroid = fake.geometry().boundingBox().center()

    # max 10 step
    step = 10
    sign = -sign / float(step)

    while not Point(centroid.x(), centroid.y()).intersects(buf) and step > 0:
        fake.geometry().translate(
            translation[0]  * sign, translation[1] * sign)
        centroid = fake.geometry().boundingBox().center()
        step = step - 1

    return fake


def insert(layer, feature):
    link = get_feature_attribute_values(layer, feature, 'link')
    insert_features_in_layer([feature], layer)
    return layer.getFeatures(
        QgsFeatureRequest().setFilterExpression(
            u'"link" = {0}'.format(link))).next()


def connect(subgraph, feature1, feature2, link, source_layer):
    segment = compute_segment_geometry(
        feature_to_shapely_wkt(feature1),
        feature_to_shapely_wkt(feature2))
    new_feature = create_new_feature(
        subgraph,
        segment.wkt,
        {
            'layer': get_id(source_layer),
            'start': get_id(feature1),
            'end': get_id(feature2),
            'link': link,
        })

    subgraph.beginEditCommand('subgraph update')
    subgraph.dataProvider().addFeatures([new_feature])
    subgraph.endEditCommand()
    subgraph.updateExtents()


def fake_generatrices(source_layer, layer):
    query = ''
    if source_layer.fields().fieldNameIndex('HoleID') >= 0:
        query = u"attribute($currentfeature, 'HoleID') = 'Fake' OR attribute($currentfeature, 'HoleID:Integer64(10,0)') = 'Fake'"
    elif source_layer.fields().fieldNameIndex('mine') >= 0:
        query = u"attribute($currentfeature, 'mine') = -1 OR attribute($currentfeature, 'mine:Integer64(10,0)') = -1"
    else:
        return None

    return layer.getFeatures(QgsFeatureRequest().setFilterExpression(query))
