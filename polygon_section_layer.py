from qgis.core import *

from .qgis_section.layer import Layer
from .graph import to_surface
from shapely.geometry import Point, LineString
from shapely.wkt import loads

import numpy as np
import logging

class PolygonLayerProjection(Layer):
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

        polygon = QgsGeometry.fromWkt(PolygonLayerProjection.buildPolygon(section, source, buf, with_projection=True).wkt)

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


    @staticmethod
    def buildPolygon(section, graphLayer, buf, with_projection=True):
        logging.info('_rebuildPolygon')

        vertices = []
        indices = {}
        edges = []

        def addProjectedVertices(section, geom):
            v = loads(geom.geometry().exportToWkt().replace('Z', ' Z'))
            return [[ list(section.project_point(v.coords[0][0], v.coords[0][1], v.coords[0][2])),
                      list(section.project_point(v.coords[1][0], v.coords[1][1], v.coords[1][2]))]]

        def addVertices(geom):
            v = loads(geom.geometry().exportToWkt().replace('Z', ' Z'))
            return [[ [v.coords[0][0], v.coords[0][1], v.coords[0][2]],
                      [v.coords[1][0], v.coords[1][1], v.coords[1][2]] ]]


        for feature in graphLayer.getFeatures():
            centroid = feature.geometry().boundingBox().center()
            if (not buf is None) and (not Point(centroid.x(), centroid.y()).intersects(buf)):
                continue

            layer = QgsMapLayerRegistry.instance().mapLayer(feature.attribute("layer"))
            start = layer.getFeatures(QgsFeatureRequest(feature.attribute("start"))).next()
            end = layer.getFeatures(QgsFeatureRequest(feature.attribute("end"))).next()

            if not(start.id() in indices):
                indices[start.id()] = len(vertices)
                vertices += addProjectedVertices(section, start) if with_projection else addVertices(start)

            if not(end.id() in indices):
                indices[end.id()] = len(vertices)
                vertices += addProjectedVertices(section, end) if with_projection else addVertices(end)

            edges += [(indices[start.id()], indices[end.id()])]


        nodes = np.array(vertices)
        surface = to_surface(nodes, tuple(edges))

        logging.debug(surface.wkt)
        return surface
