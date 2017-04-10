# coding: utf-8

from qgis.core import * # unable to import QgsWKBTypes otherwize (quid?)
from qgis.gui import *
from shapely.wkt import loads

from PyQt4.QtCore import QObject, pyqtSignal

from .qgis_hal import (get_layers_with_properties,
                        projected_layer_to_original,
                        get_all_layer_features,
                        get_name)

from .section_projection import (project_layer_as_linestring,
                                  project_layer_as_polygon)

import logging

# TODO
# - restaurer ces signaux
# projection.source_layer.featureAdded.connect(self.__projections[sourceId]['needs_update_fn'])
# projection.source_layer.editCommandEnded.connect(self.__projections[sourceId]['needs_update_fn'])
# projection.source_layer.editCommandEnded.connect(self.request_canvas_redraw)
# projection.source_layer.selectionChanged.connect(self.__synchronize_selection)


class Section(QObject):
    changed = pyqtSignal(str, float)
    needs_redraw = pyqtSignal()
    # section_layer_modified = pyqtSignal(Layer)

    def __init__(self, id_='section', parent=None):
        QObject.__init__(self, parent)
        self.__line = None
        self.__id = id_
        self.__width = 0
        self.__z_scale = 1
        self.__enabled = True

    def unload(self):
        pass

    def _reproject_all_layers(self):
        logging.info('_reproject_all_layers {}'.format(self.__enabled))
        if not self.__enabled:
            return

        logging.debug('section project: {} {}'.format(self.__z_scale,
            [get_name(l) for
             l in get_layers_with_properties({'section_id': self.__id})]))

        for layer in get_layers_with_properties({'section_id': self.__id}):
            geom_type = QgsWKBTypes.geometryType(int(layer.wkbType()))

            if geom_type == QgsWKBTypes.LineGeometry:
                source_layer = projected_layer_to_original(layer)
                project_layer_as_linestring(
                    self.__line, self.__z_scale, self.__width,
                    source_layer, layer, True)
            elif geom_type == QgsWKBTypes.PolygonGeometry:
                source_layer = projected_layer_to_original(
                    layer, 'polygon_projected_layer')
                project_layer_as_polygon(
                    self.__line, self.__z_scale, self.__width,
                    source_layer, layer, True)
            else:
                raise Exception(
                    '''
                    Layer {} has unsupported geom type {} (expected {} or {})
                    '''.
                    format(get_name(layer),
                           geom_type,
                           QgsWKBTypes.LineGeometry,
                           QgsWKBTypes.PolygonGeometry))

    def update(self, wkt_line, width=0):
        try:
            self.__line = loads(wkt_line.replace('Z', ' Z'))
            self.__width = width
            # always reset z-scale when setting a new line
            self.__z_scale = 1.0
        except Exception:
            self.__line = None

        self._reproject_all_layers()

        self.changed.emit(wkt_line, width)

    def set_z_scale(self, scale):
        self.__z_scale = scale
        self._reproject_all_layers()

    def z_range(self, smin, smax):
        z_min = -float('inf')
        z_max = float('inf')

        for layer in get_layers_with_properties({'section_id': self.__id}):
            # min|max y of projected feature
            for feature in get_all_layer_features(layer):
                bbox = feature.geometry().boundingBox()
                if bbox.xMinimum() >= smin and bbox.xMaximum() <= smax:
                    z_min = max(z_min, bbox.yMinimum())
                    z_max = min(z_max, bbox.yMaximum())

        return (z_min / self.__z_scale, z_max / self.__z_scale)

    def __synchronize_selection(self, selected, deselected):
        source = self.sender()

        if source.id() in self.__projections:
            self.__synchronize_selection_source_proj(self.__projections[source.id()], selected, deselected)
        else:
            for s_id in self.__projections:
                for layer in self.__projections[s_id]['layers']:
                    if layer.projected_layer.id() == source.id():
                        layer.synchronize_selection_proj_to_source()
                        return


    def __synchronize_selection_source_proj(self, l, selected, deselected):
        # sync selected items from layer_from in [layers_to]
        if len(l['layers']) == 0:
            return

        source_layer = l['layers'][0].source_layer

        selected_ids = [f.attribute('link') for f in source_layer.selectedFeatures()]

        for layer in l['layers']:
            layer.synchronize_selection_source_to_proj(selected_ids)

    def request_canvas_redraw(self):
        self.needs_redraw.emit()

    def disable(self):
        self.__enabled = False

    def enable(self):
        self.__enabled = True

    def __getattr__(self, name):
        if name == "line":
            return self.__line
        elif name == "width":
            return self.__width
        elif name == "id":
            return self.__id
        elif name == "is_valid":
            return self.line is not None
        elif name == "z_scale":
            return self.__z_scale
        elif name == "enabled":
            return self.__enabled
        raise AttributeError(name)
