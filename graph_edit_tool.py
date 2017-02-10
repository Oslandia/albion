# coding=utf-8

from qgis.core import *
from qgis.gui import *

from PyQt4.QtCore import Qt, pyqtSignal
from PyQt4.QtGui import QDockWidget, QMenu, QColor, QToolBar, QDialog, QIcon, QCursor, QApplication

import os

from shapely.wkt import loads

from .polygon_section_layer import PolygonLayerProjection
from shapely.geometry import LineString
from shapely.wkt import loads

from .graph import to_surface

from .qgis_section.helpers import projected_layer_to_original, projected_feature_to_original


import numpy as np

class GraphEditTool(QgsMapToolEmitPoint):
    graph_modified = pyqtSignal()

    def __init__(self, sectionCanvas):
        QgsMapToolEmitPoint.__init__(self, sectionCanvas)
        self.__sectionCanvas = sectionCanvas

        self.canvasClicked.connect(self._new_point)
        self.activated.connect(self._reset)
        self.segments = []
        self.rubberband = QgsRubberBand(sectionCanvas)
        self.rubberband.setWidth(2)
        self.rubberband.setColor(QColor(255, 0, 0, 200))
        self.rubberband.addPoint(QgsPoint())
        self.rubberband.addPoint(QgsPoint())

        self._reset()

        self.graphLayer = None

    def _reset(self):
        self.previousFeature = None
        self.rubberband.setVisible(False)

    def set_graph_layer(self, graph_layer):
        self.graphLayer = graph_layer

    def canvasMoveEvent(self, event):
        #QgsMapToolEmitPoint.canvasMoveEvent(self, event)
        point = QgsPoint(self.toMapCoordinates(event.pos()))
        self.rubberband.movePoint(1, point, 0)

    def featureAtPoint(self, point, layer):
        radius = QgsMapTool.searchRadiusMU(self.__sectionCanvas)
        rect = QgsRectangle(point.x() - radius, point.y() - radius, point.x() + radius, point.y() + radius)
        rect_geom = QgsGeometry.fromRect(rect)

        source_layer = projected_layer_to_original(layer)
        if source_layer is None or source_layer == self.graphLayer:
            return

        pt = QgsGeometry.fromPoint(QgsPoint(point.x(), point.y()))
        dist = float('inf')
        best = None
        for feat in layer.getFeatures(QgsFeatureRequest(rect)):
            # select nearest feature
            p =  feat.geometry().centroid().asPoint()
            d = feat.geometry().distance(pt)

            if d < dist:
                dist = d
                best = feat

        if best != None:
            source = projected_feature_to_original(source_layer, best)
            return {'proj': feat, 'source':source, 'layer': layer}

        return None

    @staticmethod
    def segmentGeometry(featureA, featureB):
        def mysum(x, a, b):
            return [(a[i] + b[i]) * x for i in range(0, 3)]

        def bary(coords):
            return reduce(lambda x,y: mysum(1.0 / len(coords), x, y), coords)

        geomA = loads(featureA.geometry().exportToWkt().replace("Z", " Z"))
        centroidAWithZ = bary(geomA.coords)

        geomB = loads(featureB.geometry().exportToWkt().replace("Z", " Z"))
        centroidBWithZ = bary(geomB.coords)

        return LineString([centroidAWithZ, centroidBWithZ])

    @staticmethod
    def createSegmentEdge(featureA, featureB, my_id, fields, layer):
        segment = GraphEditTool.segmentGeometry(featureA, featureB)

        new_feature = QgsFeature()
        new_feature.setGeometry(QgsGeometry.fromWkt(segment.wkt))

        new_feature.setFields(fields)
        new_feature.setAttribute("layer", layer)
        new_feature.setAttribute("start", featureA.id())
        new_feature.setAttribute("end", featureB.id())
        new_feature.setAttribute("id", my_id)
        return new_feature

    def _new_point(self, point, button):
        if self.graphLayer is None:
            return

        layer = self.__sectionCanvas.currentLayer()
        if layer is None:
            self._reset()
            return

        clickedFeature = self.featureAtPoint(point, layer)

        if clickedFeature is None:
            self._reset()
        else:
            p = clickedFeature['proj'].geometry().centroid().asPoint()
            self.rubberband.movePoint(0, p, 0)
            self.rubberband.setVisible(True)

            if self.previousFeature is None:
                self.previousFeature = clickedFeature
            elif self.previousFeature['proj'].id() == clickedFeature['proj'].id():
                self._reset()
            else:

                ids = self.graphLayer.uniqueValues(self.graphLayer.fieldNameIndex('id'))
                my_id = (max(ids) if len(ids) > 0 else 0) + 1

                features = [ GraphEditTool.createSegmentEdge (
                    self.previousFeature['source'],
                    clickedFeature['source'],
                    my_id,
                    self.graphLayer.fields(),
                    clickedFeature['layer'].customProperty("projected_layer")) ]

                self.graphLayer.beginEditCommand('test')
                self.graphLayer.dataProvider().addFeatures(features)
                self.graphLayer.endEditCommand()

                self.previousFeature = clickedFeature

                self.graph_modified.emit()
