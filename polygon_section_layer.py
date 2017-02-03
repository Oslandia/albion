from qgis.core import *

from .qgis_section.layer import Layer
from .graph import to_surface
from shapely.geometry import Point, LineString
from shapely.wkt import loads

import numpy as np
import logging

def project_vertex(section, vertex):
    return section.project_point(vertex[0], vertex[1], vertex[2])


class PolygonLayerProjection(Layer):
    def __init__(self, source_layer, projected_layer, toolbar_wip):
        Layer.__init__(self, source_layer, projected_layer)
        self.toolbar_wip = toolbar_wip

    def apply(self, section, remove_all):
        "project source features on section plnae defined by line"

        logging.debug('polygon projection')
        projected = self.projected_layer
        if remove_all:
            projected.dataProvider().deleteFeatures(projected.allFeatureIds())

        if not section.is_valid:
            return None

        logging.info('projecting {} -> {}'.format(self.source_layer.name(), self.projected_layer.geometryType()))

        source = self.source_layer
        line = section.line
        features = []
        # square cap style for the buffer -> less points
        buf = line.buffer(section.width, cap_style=2)

        polygons = self.toolbar_wip.export_polygons_impl(source, None, section)

        for p in polygons:
            # project each vertices
            vertices = []
            for idx in range(0, len(p), 2):
                vertices += [list(project_vertex(section, p[idx]))]
            for idx in range(len(p)-1, 0, -2):
                vertices += [list(project_vertex(section, p[idx]))]
            vertices += [vertices[0]]

            print vertices
            wkt = ' '.join(str(x) for x in vertices[0])
            for v in vertices[1:]:
                wkt += ', {}'.format(' '.join(str(x) for x in v))

            wkt = 'POLYGON Z (({}))'.format(wkt)

            polygon = QgsGeometry.fromWkt(wkt)

            if polygon is None:
                return

            feature = QgsFeature()
            feature.setGeometry(polygon)
            projected.beginEditCommand('layer projection')
            projected.dataProvider().addFeatures([ feature ])
            projected.endEditCommand()
            projected.updateExtents()

    def synchronize_selection_source_to_proj(self, selected_ids):
        # Doesn't make sense for the polygon
        pass

    def synchronize_selection_proj_to_source(self):
        # Doesn't make sense for the polygon
        pass
