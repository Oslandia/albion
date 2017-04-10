# coding: utf-8

from qgis.core import (QgsMapLayer,
                       QgsRectangle,
                       QgsGeometry,
                       QgsFeatureRequest,
                       QGis)
from qgis.gui import QgsMapTool

from PyQt4.QtCore import pyqtSignal
from shapely.geometry import LineString
import logging


class LineSelectTool(QgsMapTool):
    line_clicked = pyqtSignal(str)

    def __init__(self, canvas):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas

    def canvasReleaseEvent(self, event):
        # Get the click
        radius = QgsMapTool.searchRadiusMU(self.canvas)
        for layer in self.canvas.layers():
            layerPoint = self.toLayerCoordinates(layer, event.pos())
            rect = QgsRectangle(layerPoint.x() - radius,
                                layerPoint.y() - radius,
                                layerPoint.x() + radius,
                                layerPoint.y() + radius)
            rect_geom = QgsGeometry.fromRect(rect)
            if layer.type() == QgsMapLayer.VectorLayer and\
               layer.geometryType() == QGis.Line:
                for feat in layer.getFeatures(QgsFeatureRequest(rect)):
                    if feat.geometry().intersects(rect_geom) and\
                       feat.geometry().length() > 0:
                        logging.info('found line in {}'.format(layer.name()))
                        self.line_clicked.emit(
                            QgsGeometry.exportToWkt(feat.geometry()))
                        return
        # emit a small linestring in the x direction
        layerPoint = self.toMapCoordinates(event.pos())
        self.line_clicked.emit(
            LineString([(
                layerPoint.x()-radius, layerPoint.y()),
                (layerPoint.x()+radius, layerPoint.y())]).wkt)
