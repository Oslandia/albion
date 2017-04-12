# coding: utf-8

from qgis.core import QgsPoint, QgsRectangle, QgsGeometry, QgsFeatureRequest
from qgis.gui import QgsMapTool, QgsMapToolEmitPoint, QgsRubberBand

from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QColor

from .qgis_hal import (insert_features_in_layer,
                       create_new_feature, get_id,
                       projected_layer_to_original,
                       projected_feature_to_original,
                       feature_to_shapely_wkt)
from .graph_operations import compute_segment_geometry
import logging

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

        logging.info('Nearest clicked feature: {}'.format(best))

        if best is not None:
            source = projected_feature_to_original(source_layer, best)
            assert source is not None
            return {'proj': feat, 'source': source, 'layer': layer}

        return None

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

                ids = self.graphLayer.uniqueValues(self.graphLayer.fieldNameIndex('link'))
                my_id = (max(ids) if len(ids) > 0 else 0) + 1

                featureA = self.previousFeature['source']
                featureB = clickedFeature['source']

                segment = compute_segment_geometry(
                    feature_to_shapely_wkt(featureA),
                    feature_to_shapely_wkt(featureB))

                features = [create_new_feature(
                    self.graphLayer,
                    segment.wkt,
                    {
                        'layer': clickedFeature['layer'].customProperty(
                            'projected_layer'),
                        'start': get_id(featureA),
                        'end': get_id(featureB),
                        'link': my_id,
                    })]

                insert_features_in_layer(features, self.graphLayer)

                self.previousFeature = clickedFeature

                self.graph_modified.emit()
