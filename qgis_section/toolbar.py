# coding=utf-8

from qgis.core import * # unable to import QgsWKBTypes otherwize (quid?)
from qgis.gui import *

from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QToolBar, QLineEdit, QLabel, QIcon

from shapely.geometry import LineString
import os
import logging

from .axis_layer import AxisLayer
from .section_tools import LineSelectTool
from .helpers import is_layer_projected_in_section
from .layer import hasZ
from .action_state_helper import ActionStateHelper


class Toolbar(QToolBar):
    line_clicked = pyqtSignal(str, float)
    z_autoscale_toggled = pyqtSignal(bool)
    projected_layer_created = pyqtSignal(QgsVectorLayer, QgsVectorLayer)

    def __init__(self, iface, section_id, iface_canvas, section_canvas):
        QToolBar.__init__(self)
        self.__iface = iface
        self.__iface_canvas = iface_canvas
        self.__section_canvas = section_canvas
        self.__section_id = section_id

        icon = lambda name: QIcon(os.path.join(os.path.dirname(__file__), 'icons', name))

        self.addAction(icon('axis_layer.svg'), 'axis').triggered.connect(self.__add_axis)


        add_projected_layer_action = self.addAction(icon('add_layer.svg'), 'add projected layer')
        add_projected_layer_action.triggered.connect(self.__add_layer)
        h = ActionStateHelper(add_projected_layer_action)
        h.add_is_enabled_test(lambda action: (not iface.mapCanvas().currentLayer() is None, "Select layer to project"))
        h.add_is_enabled_test(lambda action: (iface.mapCanvas().currentLayer().customProperty("section_id") is None, "Select layer is a projection"))
        h.add_is_enabled_test(lambda action: (not is_layer_projected_in_section(iface.mapCanvas().currentLayer().id(), self.__section_id), "Layer is already projected"))
        h.add_is_enabled_test(lambda action: (hasZ(iface.mapCanvas().currentLayer()), "Selected layer doens't have XYZ geom"))


        self.selectLineAction = self.addAction(icon('select_line.svg'), 'select line')
        self.selectLineAction.setCheckable(True)
        self.selectLineAction.triggered.connect(self.__pick_section_line)

        self.buffer_width = QLineEdit("100")
        self.buffer_width.setMaximumWidth(50)
        self.addWidget(QLabel("Width:"))
        self.addWidget(self.buffer_width)

        self.z_autoscale = self.addAction(icon('autoscale.svg'), 'autoscale')
        self.z_autoscale.setCheckable(True)
        self.z_autoscale.toggled.connect(self.z_autoscale_toggled.emit)

        self.__tool = None
        self.__old_tool = None
        self.__bridge = None

    def unload(self):
        self.__iface = None
        if self.__iface_canvas.mapTool() == self.__tool:
            self.__iface_canvas.unsetMapTool(self.__tool)
        self.__bridge = None

    def __pick_section_line(self):
        logging.debug('set_section_line')
        if not self.selectLineAction.isChecked():
            if self.__iface_canvas.mapTool() == self.__tool:
                self.__iface_canvas.unsetMapTool(self.__tool)
            self.__tool = None
        else:
            self.__tool = LineSelectTool(self.__iface_canvas)
            self.__tool.line_clicked.connect(self.__line_clicked)
            self.__iface_canvas.setMapTool(self.__tool)

    def __line_clicked(self, wkt_):
        group = self.__iface.layerTreeView().layerTreeModel().rootGroup().findGroup(self.__section_id)
        self.__update_bridge(group)

        self.selectLineAction.setChecked(False)
        self.__iface_canvas.unsetMapTool(self.__tool)
        self.line_clicked.emit(wkt_, float(self.buffer_width.text()))
        ActionStateHelper.update_all()

    def __add_layer(self):
        logging.debug('add layer')
        layer = self.__iface_canvas.currentLayer()

        if layer is None:
            return
        section = QgsVectorLayer(
            "{geomType}?crs={crs}&index=yes".format(
                geomType={
                    QGis.Point:"Point",
                    QGis.Line:"LineString",
                    QGis.Polygon:"Polygon"
                    }[layer.geometryType()],
                crs=self.__iface_canvas.mapSettings().destinationCrs().authid()
                ), layer.name(), "memory")
        section.setCustomProperty("section_id", self.__section_id)
        section.setCustomProperty("projected_layer", layer.id())

        # cpy attributes structure
        section.dataProvider().addAttributes([layer.fields().field(f) for f in range(layer.fields().count())])
        section.updateFields()

        # cpy style
        section.setRendererV2(layer.rendererV2().clone())

        self._add_layer_to_section_group(section)
        self.projected_layer_created.emit(layer, section)

    def _add_layer_to_section_group(self, layer):
        # Add to section group
        group = self.__iface.layerTreeView().layerTreeModel().rootGroup().findGroup(self.__section_id)
        if group is None:
            # Add missing group
            group = self.__iface.layerTreeView().layerTreeModel().rootGroup().addGroup(self.__section_id)
            group.setCustomProperty('section_id', self.__section_id)

        self.__update_bridge(group)

        assert not(group is None)
        QgsMapLayerRegistry.instance().addMapLayer(layer, False)
        group.addLayer(layer)


    def __update_bridge(self, group):
        if self.__bridge is None and group is not None:
            # Create bridge
            self.__bridge = QgsLayerTreeMapCanvasBridge(group, self.__section_canvas)


    def __add_axis(self):
        self.axislayer = AxisLayer(self.__iface_canvas.mapSettings().destinationCrs())
        self._add_layer_to_section_group(self.axislayer)

