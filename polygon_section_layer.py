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

            print 'MIEN', wkt
            print 'AUTR', PolygonLayerProjection.buildPolygon(section, source, buf, with_projection=True).wkt
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


        if not buf is None:
            bbox = QgsRectangle(buf.bounds[0], buf.bounds[1], buf.bounds[2], buf.bounds[3])
            for feature in graphLayer.getFeatures(QgsFeatureRequest(bbox)):
                extents = loads(feature.geometry().boundingBox().asWktPolygon())
                if not buf.intersects(extents):
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
