# coding: utf-8

from .utils import icon
from .action_state_helper import ActionStateHelper

from PyQt4.QtGui import QToolBar, QProgressDialog

from .buttons.export_polygon_button import (
    precondition_check as export_precond,
    execute as export_exec)

from .convert_data_layer import ConvertDataLayer
from .graph_layer_helper import GraphLayerHelper
from .sections_layers_combo import SectionsLayersCombo

from .qgis_hal import get_layer_by_id


import logging


class GlobalToolbar(QToolBar):
    """ Albion plugin's toolbar

        Holds global settings, action, etc """
    def __init__(self, iface, section, plugin_compute_fn):
        QToolBar.__init__(self)
        self.__section = section
        self.mapCanvas = iface.mapCanvas()
        self.__plugin_compute_fn = plugin_compute_fn

        # Graph layers selection UI
        self.graphLayerHelper = GraphLayerHelper()
        self.graphLayerHelper.add_to_toolbar(self, iface)

        # Sections layers selection UI
        self.sections_layers_combo = SectionsLayersCombo(iface, self)
        self.sections_layers_combo.add_to_toolbar(self)

        self.__add_layer_action = self.addAction(
            icon('1_add_layer.svg'), 'create layer from csv')
        self.__add_layer_action.triggered.connect(self.__import_csv)

        self.__export_polygon_action = self.addAction(
            icon('5_export_polygons.svg'),
            'Export polygons')
        self.__export_polygon_action.triggered.connect(self.__export_polygon)
        ActionStateHelper(self.__export_polygon_action).add_is_enabled_test(
            lambda action: export_precond(
                self.graphLayerHelper.active_layer(), self.sections_layers_combo.active_layers_id())).update_state()

    def cleanup(self):
        self.__section = None
        self.__add_layer_action.triggered.disconnect(self.__import_csv)
        self.__export_polygon_action.triggered.disconnect(
            self.__export_polygon)

    def __export_polygon(self):
        section_width = float(self.__section.toolbar.buffer_width.text())
        polygons = []

        for layer in [get_layer_by_id(lid) for lid in self.sections_layers_combo.active_layers_id()]:
            polygons += self.__plugin_compute_fn(
                self.graphLayerHelper.active_layer(),
                layer,
                section_width)
        if len(polygons) == 0:
            return
        export_exec(self, polygons)

    def __import_csv(self):
        data_layer = self.mapCanvas.currentLayer()
        if data_layer is None:
            return

        dialog = QProgressDialog(
            "Importing features", "Cancel", 0, data_layer.featureCount(), self)
        self.importer = ConvertDataLayer(data_layer, dialog)
        dialog.finished.connect(self.__reset_import)
        dialog.finished.connect(self.__reset_import)
        self.importer.tick()

    def __reset_import(self, value):
        logging.warning('finished', value)
        self.importer = None

    def __toggle_edit_graph(self, checked):
        if checked:
            self.edit_graph_tool.activate()
            self.previousTool = self.__section.canvas.mapTool()
            self.__section.canvas.setMapTool(self.edit_graph_tool)
        else:
            self.edit_graph_tool.deactivate()
            self.__section.canvas.setMapTool(self.previousTool)
