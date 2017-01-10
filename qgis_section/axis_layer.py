# coding=utf-8

from qgis.core import * # unable to import QgsWKBTypes otherwize (quid?)
from qgis.gui import *

from PyQt4.QtCore import pyqtSignal, QThread, QSize
from PyQt4.QtGui import QImage, QApplication

import os
import traceback
import logging

class AxisLayerType(QgsPluginLayerType):
    def __init__(self):
        QgsPluginLayerType.__init__(self, AxisLayer.LAYER_TYPE)

    def createLayer(self):
        return AxisLayer()
        return True

    def showLayerProperties(self, layer):
        return False

class AxisLayer(QgsPluginLayer):

    LAYER_TYPE = "axis"

    __msg = pyqtSignal(str)
    __drawException = pyqtSignal(str)

    def __init__(self, crs):
        QgsPluginLayer.__init__(self, AxisLayer.LAYER_TYPE, "axis plugin layer")
        self.__msg.connect(self.__print)
        self.__drawException.connect(self.__raise)
        self.setCrs(crs)
        self.setValid(True)

    def extent(self):
        return QgsRectangle(-1,-1, 1, 1)

    def __print(self, msg):
        logging.info(msg)

    def __raise(self, err):
        logging.error(err)
        raise Exception(err)

    def draw(self, rendererContext):
        try:
            painter = rendererContext.painter()
            ext = rendererContext.extent()
            map_unit_per_pixel = rendererContext.mapToPixel().mapUnitsPerPixel()
            width, height = \
                int((ext.xMaximum()-ext.xMinimum())/map_unit_per_pixel),\
                int((ext.yMaximum()-ext.yMinimum())/map_unit_per_pixel)
            nb_div = 10
            dw, dh = width/nb_div, height/nb_div
            dx, dy = (ext.xMaximum()-ext.xMinimum())/nb_div, (ext.yMaximum()-ext.yMinimum())/nb_div

            for i in range(nb_div+2):
                painter.drawText(5, int(i*dh), "%.0f"%(ext.yMaximum()-i*dy))
                painter.drawLine(50, int(i*dh), 60, int(i*dh))
            for i in range(nb_div+2):
                painter.drawText(int(i*dw), 20, "%.0f"%(ext.xMinimum()+i*dx))
                painter.drawLine(int(i*dw), 20, int(i*dw), 25)

            #if QApplication.instance().thread() == QThread.currentThread():
            #    print "main thread"
            #else:
            #    self.__msg.emit("rendering in thread")

            return True
        except Exception as e:
            self.__drawException.emit(traceback.format_exc())
            return False

