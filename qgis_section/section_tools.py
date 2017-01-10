# coding=utf-8

from qgis.core import *
from qgis.gui import *

from PyQt4.QtCore import Qt, pyqtSignal
from PyQt4.QtGui import QApplication, QColor

from .helpers import projected_layer_to_original, projected_feature_to_original
from shapely.geometry import LineString
import logging

class LineSelectTool(QgsMapTool):
    line_clicked = pyqtSignal(str)

    def __init__(self, canvas):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas

    def canvasReleaseEvent(self, event):
        #Get the click
        radius = QgsMapTool.searchRadiusMU(self.canvas)
        for layer in self.canvas.layers():
            layerPoint = self.toLayerCoordinates(layer, event.pos())
            rect = QgsRectangle(layerPoint.x() - radius, layerPoint.y() - radius, layerPoint.x() + radius, layerPoint.y() + radius)
            rect_geom = QgsGeometry.fromRect(rect)
            if layer.type() == QgsMapLayer.VectorLayer and layer.geometryType() == QGis.Line:
                for feat in layer.getFeatures(QgsFeatureRequest(rect)):
                    if feat.geometry().intersects(rect_geom) and feat.geometry().length() > 0:
                        logging.info('found line in {}'.format(layer.name()))
                        self.line_clicked.emit(QgsGeometry.exportToWkt(feat.geometry()))
                        return
        # emit a small linestring in the x direction
        layerPoint = self.toMapCoordinates(event.pos())
        self.line_clicked.emit(LineString([(layerPoint.x()-radius, layerPoint.y()), (layerPoint.x()+radius, layerPoint.y())]).wkt)


class SelectionTool(QgsMapToolEmitPoint):
    def __init__(self, canvas):
        QgsMapToolEmitPoint.__init__(self, canvas)
        self.canvas = canvas

        self.canvasClicked.connect(self._new_point)

    @staticmethod
    def nearest_feature(canvas, layer, point):
        radius = QgsMapTool.searchRadiusMU(canvas)
        rect = QgsRectangle(point.x() - radius, point.y() - radius, point.x() + radius, point.y() + radius)
        rect_geom = QgsGeometry.fromRect(rect)

        best_choice = {'distance': 0, 'feature': None }
        for feat in layer.getFeatures(QgsFeatureRequest(rect)):
            dist = feat.geometry().distance(QgsGeometry.fromPoint(QgsPoint(point.x(), point.y())))

            if dist < best_choice['distance'] or best_choice['feature'] is None:
                best_choice['distance'] = dist
                best_choice['feature'] = feat

        return best_choice['feature']

    def _new_point(self, point, button):
        layer = self.canvas.currentLayer()
        source_layer = projected_layer_to_original(layer)

        if layer is None or source_layer is None:
            return

        if not(QApplication.keyboardModifiers() & Qt.ControlModifier):
            source_layer.removeSelection()
            layer.removeSelection()

        feature = SelectionTool.nearest_feature(self.canvas, layer, point)

        if feature:
            layer.select(feature.id())
            source_layer.select(projected_feature_to_original(source_layer, feature).id())


class MoveFeatureTool(QgsMapToolEdit):
    def __init__(self, canvas):
        QgsMapToolEdit.__init__(self, canvas)
        self.canvas = canvas
        self.moving_features = []
        self.rubberband = None


    def canvasPressEvent(self, event):
        self.rubberband = None

        layer = self.canvas.currentLayer()
        if layer is None:
            return

        if not layer.isEditable():
            return


        if layer.selectedFeatureCount() > 0:
            self.moving_features = layer.selectedFeatures()
            self.rubberband = QgsRubberBand(self.canvas, layer.geometryType())
            for feat in self.moving_features:
                self.rubberband.addGeometry(feat.geometry(), layer)

        else:

            # pick nearest feature
            feature = SelectionTool.nearest_feature(self.canvas, layer, event.mapPoint())

            if feature:
                self.moving_features = [ feature ]
                self.rubberband = QgsRubberBand(self.canvas, layer.geometryType())
                self.rubberband.setToGeometry(feature.geometry(), layer)
            else:
                return

        self.start_point = event.mapPoint()
        self.rubberband.setColor( QColor( 255, 0, 0, 65 ) );
        self.rubberband.setWidth( 2 );
        self.rubberband.show();

    def canvasMoveEvent(self, event):
        if self.rubberband is None:
            return

        x = event.mapPoint().x() - self.start_point.x()
        y = event.mapPoint().y() - self.start_point.y()
        self.rubberband.setTranslationOffset(x, y)
        self.rubberband.updatePosition()
        self.rubberband.update()

    def canvasReleaseEvent(self, event):
        layer = self.canvas.currentLayer()

        if self.rubberband is None or layer is None:
            return

        x = event.mapPoint().x() - self.start_point.x()
        y = event.mapPoint().y() - self.start_point.y()

        layer.beginEditCommand("Feature moved")
        for feature in self.moving_features:
            layer.translateFeature(feature.id(), x, y)
        layer.endEditCommand()

        self.rubberband.hide()
        self.rubberband = None
        self.canvas.refresh()
