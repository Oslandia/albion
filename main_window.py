# coding: utf-8

"""
This modules provides a ready to use section windows containing a section
a canvas and a layer tree
"""

from qgis.core import QgsPluginLayerRegistry

from PyQt4.QtGui import QMainWindow
from PyQt4.QtCore import Qt

from .section import Section
from .section_toolbar import Toolbar
from .canvas import Canvas
from .axis_layer import AxisLayer, AxisLayerType
from .action_state_helper import ActionStateHelper

import atexit

AXIS_LAYER_TYPE = AxisLayerType()
QgsPluginLayerRegistry.instance().addPluginLayerType(AXIS_LAYER_TYPE)


@atexit.register
def unload_axi_layer_type():
    QgsPluginLayerRegistry.instance().removePluginLayerType(
        AxisLayer.LAYER_TYPE)


class MainWindow(QMainWindow):
    def __init__(self, iface, section_id, parent=None):
        QMainWindow.__init__(self, parent)
        self.setWindowFlags(Qt.Widget)

        self.__iface = iface
        self.__section = Section(section_id)
        self.__canvas = Canvas(self.__section, iface, self)
        self.__toolbar = Toolbar(iface,
                                 self.__section.id,
                                 iface.mapCanvas(),
                                 self.__canvas)
        self.__toolbar.buffer_width.setText(str(10))

        self.__toolbar.line_clicked.connect(self.__section.update)
        self.__toolbar.z_autoscale_toggled.connect(self.__canvas.z_autoscale)

        self.addToolBar(Qt.TopToolBarArea, self.__toolbar)
        self.setCentralWidget(self.__canvas)

        ActionStateHelper.update_all()
        self.__iface.layerTreeView().currentLayerChanged.connect(
            ActionStateHelper.update_all)
        self.__section.needs_redraw.connect(self.__refresh_canvas)

    def add_default_section_buttons(self):
        actions = self.__canvas.build_default_section_actions()
        self.__canvas.add_section_actions_to_toolbar(actions, self.__toolbar)

    def unload(self):
        self.__section.needs_redraw.disconnect(self.__refresh_canvas)
        self.__iface.layerTreeView().currentLayerChanged.disconnect(
            ActionStateHelper.update_all)
        ActionStateHelper.remove_all()

        for a in self.__canvas.section_actions:
            self.__toolbar.removeAction(a['action'])

        self.__canvas.unload()
        self.__toolbar.unload()
        self.__section.unload()

        self.__toolbar.line_clicked.disconnect(self.__section.update)
        self.removeToolBar(self.__toolbar)
        self.__canvas = None
        self.__section = None

    def __refresh_canvas(self):
        self.__canvas.refresh()
        # For some reason refresh() is not enough
        self.__iface.mapCanvas().refreshAllLayers()

    def __getattr__(self, name):
        if name == "canvas":
            return self.__canvas
        elif name == "toolbar":
            return self.__toolbar
        elif name == "section":
            return self.__section
        raise AttributeError(name)
