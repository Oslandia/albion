# coding=utf-8

from qgis.core import *
from qgis.gui import *

from .graph_edit_tool import GraphEditTool
from shapely.geometry import Point

import math
# Helper methods to manage fake generatrices


def create(section, source_layer, source_feature, id_, translation, sign):
    source_has_field_HoleID = source_layer.fields().fieldNameIndex("HoleID") >= 0
    source_has_field_mine = source_layer.fields().fieldNameIndex("mine") >= 0

    fake = QgsFeature()
    fake.setAttributes(source_feature.attributes())
    fake.setFields(source_layer.fields(), False)
    if source_has_field_HoleID:
        fake.setAttribute("HoleID", "Fake")
    if source_has_field_mine:
        fake.setAttribute("mine", -1)
    fake.setAttribute("id", id_)
    fake.setGeometry(source_feature.geometry())


    fake.geometry().translate(translation[0] * sign, translation[1] * sign)

    # we need to make sure that the newly created geometry is inside the section
    buf = section.line.buffer(section.width, cap_style=2)
    centroid = fake.geometry().boundingBox().center()

    # max 10 step
    step = 10
    sign = -sign / float(step)
    print centroid.x(), centroid.y()
    while not Point(centroid.x(), centroid.y()).intersects(buf) and step > 0:
        fake.geometry().translate(translation[0]  * sign, translation[1] * sign)
        centroid = fake.geometry().boundingBox().center()
        step = step - 1


    return fake

def insert(layer, feature):
    id_ = feature.attribute("id")

    layer.beginEditCommand('fake features')
    layer.dataProvider().addFeatures([ feature ])
    layer.endEditCommand()
    layer.updateExtents()

    return layer.getFeatures(QgsFeatureRequest().setFilterExpression(u'"id" = {0}'.format(id_))).next()

def connect(subgraph, feature1, feature2, id_, source_layer):
    subgraph.beginEditCommand('subgraph update')
    subgraph.dataProvider().addFeatures([ GraphEditTool.createSegmentEdge(feature1, feature2, id_, subgraph.fields(), source_layer.id()) ])
    subgraph.endEditCommand()
    subgraph.updateExtents()


def fake_generatrices(source_layer, layer):
    query = ""
    if source_layer.fields().fieldNameIndex("HoleID") >= 0:
        query = u"attribute($currentfeature, 'HoleID') = 'Fake' OR attribute($currentfeature, 'HoleID:Integer64(10,0)') = 'Fake'"
    elif source_layer.fields().fieldNameIndex("mine") >= 0:
        query = u"attribute($currentfeature, 'mine') = -1 OR attribute($currentfeature, 'mine:Integer64(10,0)') = -1"
    else:
        return None

    return layer.getFeatures(QgsFeatureRequest().setFilterExpression(query))
