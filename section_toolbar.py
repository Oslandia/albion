# coding=utf-8

from qgis.core import (QgsVectorLayer,
                       QgsMapLayerRegistry)

from qgis.gui import QgsLayerTreeMapCanvasBridge

from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QToolBar, QLineEdit, QLabel

import logging

from .axis_layer import AxisLayer
from .section_tools import LineSelectTool
from .qgis_hal import (is_layer_projected_in_section,
                       get_layers_with_properties,
                       get_name,
                       layer_has_z)

from .action_state_helper import ActionStateHelper

from .utils import (create_projected_layer,
                    create_projected_polygon_layer,
                    icon)


def root_group_from_iface(iface):
    return iface.layerTreeView().layerTreeModel().rootGroup()


class Toolbar(QToolBar):
    """ Section specific toolbar (contains all actions for 1 section) """
    line_clicked = pyqtSignal(str, float)
    z_autoscale_toggled = pyqtSignal(bool)
    projected_layer_created = pyqtSignal(QgsVectorLayer, QgsVectorLayer)

    def __init__(self, iface, section_id, iface_canvas, section_canvas):
        QToolBar.__init__(self)
        self.__iface = iface
        self.__iface_canvas = iface_canvas
        self.__section_canvas = section_canvas
        self.__section_id = section_id

        self.addAction(
            icon('axis_layer.svg'), 'axis').triggered.connect(
                self.__add_axis)

        add_projected_layer_action = self.addAction(
            icon('add_layer_to_section.svg'), 'add projected layer')
        add_projected_layer_action.triggered.connect(self.__add_layer)
        h = ActionStateHelper(add_projected_layer_action)
        h.add_is_enabled_test(
            lambda action: (not iface.mapCanvas().currentLayer() is None,
                            'Select layer to project'))
        h.add_is_enabled_test(
            lambda action: (
                iface.mapCanvas().currentLayer().customProperty(
                    'section_id') is None,
                'Select layer is a projection'))
        h.add_is_enabled_test(
            lambda action: (not is_layer_projected_in_section(
                iface.mapCanvas().currentLayer().id(), self.__section_id),
                'Layer is already projected'))
        h.add_is_enabled_test(
            lambda action: (layer_has_z(iface.mapCanvas().currentLayer()),
                            'Selected layer doesnt have XYZ geom'))
        self.__action_helper = h

        self.selectLineAction = self.addAction(
            icon('select_line.svg'), 'select line')
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
        group = self.__iface.layerTreeView().\
            layerTreeModel().\
            rootGroup().\
            findGroup(self.__section_id)
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

        section = create_projected_layer(layer, self.__section_id)
        self._add_layer_to_section_group(section)

        assert get_name(layer) in [
            get_name(l) for l in get_layers_with_properties(
                {'section_id': self.__section_id})]

        if layer.customProperty('graph'):
            polygon = create_projected_polygon_layer(layer, self.__section_id)
            self._add_layer_to_section_group(polygon)

    def _add_layer_to_section_group(self, layer):
        # Add to section group
        group = root_group_from_iface(self.__iface).findGroup(
            self.__section_id)
        if group is None:
            # Add missing group
            group = root_group_from_iface(self.__iface).addGroup(
                self.__section_id)
            group.setCustomProperty('section_id', self.__section_id)

        self.__update_bridge(group)

        assert not(group is None)
        QgsMapLayerRegistry.instance().addMapLayer(layer, False)
        group.addLayer(layer)

    def __update_bridge(self, group):
        if self.__bridge is None and group is not None:
            # Create bridge
            self.__bridge = QgsLayerTreeMapCanvasBridge(group,
                                                        self.__section_canvas)

    def __add_axis(self):
        self.axislayer = AxisLayer(
            self.__iface_canvas.mapSettings().destinationCrs())
        self._add_layer_to_section_group(self.axislayer)
