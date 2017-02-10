# coding=utf-8

from qgis.core import *
from qgis.gui import *

from PyQt4.QtCore import Qt, pyqtSignal, QObject, QVariant, QTimer
from PyQt4.QtGui import QDockWidget, QMenu, QColor, QToolBar, QDialog, QIcon, QCursor, QMainWindow, QProgressDialog, QPixmap, QFileDialog, QLineEdit, QLabel, QMessageBox, QComboBox

import os, traceback, time, inspect
import math, sys
import numpy as np
from operator import xor

from .qgis_section.main_window import MainWindow
from .qgis_section.section import Section
from .qgis_section.section_tools import SelectionTool
from .qgis_section.helpers import projected_layer_to_original, projected_feature_to_original
from .qgis_section.action_state_helper import ActionStateHelper
from .qgis_section.layer import Layer

from shapely.wkt import loads
from shapely.geometry import Point, LineString

from .create_layer_widget import CreateLayerWidget
from .graph_edit_tool import GraphEditTool
from .polygon_section_layer import PolygonLayerProjection
from .graph import to_volume, to_surface, extract_paths
from .viewer_3d.viewer_3d import Viewer3D

from .fake_generatrice import create as fg_create
from .fake_generatrice import insert as fg_insert
from .fake_generatrice import connect as fg_connect
from .fake_generatrice import fake_generatrices as fg_fake_generatrices

import numpy as np
import logging
# from dxfwrite import DXFEngine as dxf

def build_graph_connections_list(graph_layer, generatrice_layer_id, connectable_ids):
    graph_attr = ['start', 'end'] if graph_layer.fields().fieldNameIndex('start') >= 0 else ['start:Integer64(10,0)', 'end:Integer64(10,0)']
    id_field = 'id' if graph_layer.fields().fieldNameIndex('id') >= 0 else 'id:Integer64(10,0)'

    connections = [[] for id_ in connectable_ids]
    edges = [[] for id_ in connectable_ids]

    for edge in graph_layer.getFeatures():
        if edge.attribute('layer')  != generatrice_layer_id:
            continue
        start_id = edge.attribute(graph_attr[0])
        if not (start_id in connectable_ids):
            continue

        end_id = edge.attribute(graph_attr[1])
        if not (end_id in connectable_ids):
            continue

        connections[connectable_ids.index(start_id)] += [end_id]
        edges[connectable_ids.index(start_id)] += [edge.attribute(id_field)]

        connections[connectable_ids.index(end_id)] += [start_id]
        edges[connectable_ids.index(end_id)] += [edge.attribute(id_field)]

    return connections, edges


def edges_from_edges_id(projected_graph, considered_edges_id, projected_feature_centroid_x):
    connected_edges = {'L':[], 'R':[]}
    id_field = 'id' if projected_graph.fields().fieldNameIndex('id') >= 0 else 'id:Integer64(10,0)'

    # TODO : fix others
    expr = ','.join(str(x) for x in considered_edges_id)

    # Lookup all edges connected to this feature
    for edge in projected_graph.getFeatures(QgsFeatureRequest().setFilterExpression ( u'"{}" IN ({})'.format(id_field, expr))):
        # edge is connected, check direction
        edge_center = edge.geometry().centroid().asPoint()

        # if feature is to the left of the projected edge
        if projected_feature_centroid_x < edge_center[0]:
            connected_edges['R'] += [edge]
        else:
            connected_edges['L'] += [edge]

    return connected_edges

def feature_on_the_other_side(edge, feature_id, projected_graph):
    graph_attr = ['start', 'end'] if projected_graph.fields().fieldNameIndex('start') >= 0 else ['start:Integer64(10,0)', 'end:Integer64(10,0)']
    if edge.attribute(graph_attr[0]) == feature_id:
        return edge.attribute(graph_attr[1])
    else:
        return edge.attribute(graph_attr[0])

def centroid_z(feature_id, layer):
    feature = layer.getFeatures(QgsFeatureRequest(feature_id)).next()
    v = loads(feature.geometry().exportToWkt().replace('Z', ' Z'))
    return (v.coords[1][2] + v.coords[0][2]) * 0.5


def icon(name):
    return QIcon(os.path.join(os.path.dirname(__file__), 'icons', name))

class GraphLayerHelper(QObject):
    graph_layer_tagged = pyqtSignal(QgsVectorLayer)

    def __init__(self, custom_property):
        QObject.__init__(self)
        self.graphLayer = None
        self.custom_property = custom_property

    def add_to_toolbar(self, iface, toolbar, icon_name):
        self.iface = iface
        self.action = toolbar.addAction(icon(icon_name), self.__tooltip())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.__on_click)

    def lookup(self, layers):
        for layer in layers:
            if layer.customProperty(self.custom_property):
                self.__tag_layer(layer)

    def layer(self):
        return self.graphLayer

    def layer_is_projection(self, layer):
        if layer is None or self.graphLayer is None:
            return False
        return layer.customProperty("projected_layer") == self.graphLayer.id()

    def __tooltip(self):
        if self.graphLayer:
            return "'{}' layer is '{}'".format(self.custom_property, self.graphLayer.name())
        else:
            return "No '{}' layer defined".format(self.custom_property)

    def __tag_layer(self, layer):
        self.graphLayer = layer
        self.graphLayer.setCustomProperty(self.custom_property, True)
        self.action.setChecked(True)
        self.action.setToolTip(self.__tooltip())
        self.graph_layer_tagged.emit(self.graphLayer)

    def __untag_layer(self):
        self.graphLayer.removeCustomProperty(self.custom_property)
        self.graphLayer = None
        self.graph_layer_tagged.emit(self.graphLayer)
        self.action.setToolTip(self.__tooltip())
        self.action.setChecked(False)

    def __on_click(self):
        if not self.action.isChecked():
            self.__untag_layer()
            return

        # mark active layer as the graph layer
        layer = self.iface.mapCanvas().currentLayer()

        if layer is None: return
        if not isinstance(layer, QgsVectorLayer):   return
        if not (layer.geometryType() == QGis.Line): return
        if layer.fieldNameIndex("start") == -1:     return
        if layer.fieldNameIndex("end") == -1:       return
        if layer.fieldNameIndex("layer") == -1:     return

        self.__tag_layer(layer)

class DataToolbar(QToolBar):
    def __init__(self, iface, section, viewer3d, graphLayerHelper, subGraphLayerHelper):
        QToolBar.__init__(self)
        self.__iface = iface
        self.__section = section;
        self.__logger = iface.messageBar()
        self.viewer3d = viewer3d
        self.mapCanvas = iface.mapCanvas()

        self.addAction(icon('1_add_layer.svg'), 'create line layer').triggered.connect(self.__add_layer)
        self.addAction(icon('1_add_layer.svg'), 'create layer from csv').triggered.connect(self.__import_csv )

        self.graphLayerHelper = graphLayerHelper
        self.subGraphLayerHelper = subGraphLayerHelper
        self.graphLayerHelper.add_to_toolbar(iface, self, '3_tag_layer_graph.svg')
        self.subGraphLayerHelper.add_to_toolbar(iface, self, '4_tag_layer_sous_graph.svg')

        QgsMapLayerRegistry.instance().layersAdded.connect(self.add_layers)

        ex = self.addAction(icon('5_export_polygons.svg'), 'Export polygons (graph)')
        ex.triggered.connect(lambda c: self.__export_polygons(self.graphLayerHelper.layer()))
        ActionStateHelper(ex).add_is_enabled_test(lambda action: self.__export_polygons_precondition_check(self.graphLayerHelper.layer())).update_state()

        ex2 = self.addAction(icon('5b_export_polygons_sous_graphes.svg'), 'Export polygons (subgraph)')
        ex2.triggered.connect(lambda c: self.__export_polygons(self.subGraphLayerHelper.layer()))
        ActionStateHelper(ex2).add_is_enabled_test(lambda action: self.__export_polygons_precondition_check(self.subGraphLayerHelper.layer())).update_state()

        self.__section.toolbar.projected_layer_created.connect(self.__add_polygon_layer)

    def cleanup(self):
        self.__section.toolbar.projected_layer_created.disconnect(self.__add_polygon_layer)
        self.__section = None
        QgsMapLayerRegistry.instance().layersAdded.disconnect(self.add_layers)

    def __export_polygons_precondition_check(self, graphLayer):
        layer = self.mapCanvas.currentLayer()
        if layer is None:
            return (False, "No active layer")
        if graphLayer is None:
            return (False, "No graph layer defined")
        if not layer.customProperty("session_id") is None:
            return (False, "Select a non-projected layer")
        if not layer.isSpatial():
            return (False, "Selected layer has no geometry")
        if layer.featureCount() == 0:
            return (False, "Selected layer has no features")
        return (True, "")

    def create_projected_layer(self, layer, section_id):
        if layer is None:
            return

        section = QgsVectorLayer(
            "{geomType}?crs={crs}&index=yes".format(
                geomType={
                    QGis.Point:"Point",
                    QGis.Line:"LineString",
                    QGis.Polygon:"Polygon"
                    }[layer.geometryType()],
                crs=self.__iface.mapCanvas().mapSettings().destinationCrs().authid()
                ), layer.name() + "_export", "memory")
        section.setCustomProperty("section_id", section_id)
        section.setCustomProperty("projected_layer", layer.id())

        # cpy attributes structure
        section.dataProvider().addAttributes([layer.fields().field(f) for f in range(layer.fields().count())])
        section.updateFields()

        # cpy style
        section.setRendererV2(layer.rendererV2().clone())
        return section

    def __export_polygons(self, graphLayer):
        file = QFileDialog.getSaveFileName(self, "Save polygon-csv export to...")
        if len(file) == 0:
            return

        layer = self.mapCanvas.currentLayer()

        polygons = self.export_polygons_impl(graphLayer, layer)

        out_file = open(file, 'w')
        for index in range(0, len(polygons)):
            vertices = polygons[index]

            for i in range(0, len(vertices), 2):
                v = vertices[i]
                out_file.write('{};{};{};{}\n'.format(index, v[0], v[1], v[2]))

            for i in range(len(vertices)-1, 0, -2):
                v = vertices[i]
                out_file.write('{};{};{};{}\n'.format(index, v[0], v[1], v[2]))

            # last but not least: close the polygon
            v = vertices[0]
            out_file.write('{};{};{};{}\n'.format(index, v[0], v[1], v[2]))

        QMessageBox().information(self, 'Export', 'Wrote {} polygon(s)'.format(len(polygons)))

        out_file.close()



    def __export_polygons_for_one_section_line(self, section, graph_section_layer, scratch_projection, fakes_id, request, generatrice_layer):
        # project graph features in scratch_projection layer using current section line
        graph_section_layer.apply(section, True)

        # export for real
        if scratch_projection.featureCount() == 0:
            return []

        gen_ids = [] # generatrice_layer.allFeatureIds()
        lid = generatrice_layer.id()

        potential_starts = []
        potential_starts += fakes_id

        def compute_feature_length(feat_id):
            feat = generatrice_layer.getFeatures(QgsFeatureRequest(feat_id)).next()
            return section.project(feat.geometry()).length()


        logging.debug('BEFORE (fakes) {}'.format(potential_starts))
        pants = {}
        powers = {}

        buf = section.line.buffer(section.width, cap_style=2)
        bbox = QgsRectangle(buf.bounds[0], buf.bounds[1], buf.bounds[2], buf.bounds[3])
        source_features = []

        logging.info('{} ={}'.format(section.width, bbox.asWktCoordinates()))

        for source_feature in generatrice_layer.getFeatures(QgsFeatureRequest(bbox)):
            bb = source_feature.geometry().boundingBox()
            extents = loads('LINESTRING ({} {}, {} {})'.format(bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum()))

            if buf.intersects(extents):
                gen_ids += [source_feature.id()]
                source_features += [source_feature]

        connections, edges_id = build_graph_connections_list(scratch_projection, generatrice_layer.id(), gen_ids)

        for i in range(0, len(source_features)):
            source_feature = source_features[i]
            centroid = source_feature.geometry().centroid().asPoint()
            p = edges_from_edges_id(scratch_projection, edges_id[i], section.project_point(centroid[0], centroid[1], 0)[0])

            if len(p['L']) > 1 or len(p['R']) > 1:
                potential_starts += [source_feature.id()]

                for edge in p['L'] + p['R']:
                    feat_id = feature_on_the_other_side(edge, source_feature.id(), scratch_projection)
                    if not feat_id in powers:
                        powers[feat_id] = compute_feature_length(feat_id)

                pants[source_feature.id()] = p

        # remove invalid
        logging.debug('AFTER {} | {}'.format(potential_starts, gen_ids))
        potential_starts = filter(lambda i: i in gen_ids, potential_starts)
        logging.debug('LAST {}'.format(potential_starts))

        # export graph
        paths = extract_paths(gen_ids, potential_starts, connections)

        if paths == None or len(paths) == 0:
            logging.warning('No path found ({})'.format(request.filterExpression().expression()))
            return []

        logging.info('Found {} paths: {}'.format(len(paths), paths))


        result = []
        for path in paths:
            edges = []
            vertices = []

            for i in range(0, len(path)):
                v = path[i]
                p = generatrice_layer.getFeatures(QgsFeatureRequest(v)).next()

                ratio = 1.0
                offset = 0.0
                if v in pants:
                    # so, 'p' is a starting point of the polygon and
                    # is shared by several connections.
                    # 1st step: determine where we going
                    next_v = path[(i + 1) if (i == 0) else (i - 1)]
                    connections_to_consider = None

                    for edge in pants[v]['L']:
                        if feature_on_the_other_side(edge, v, scratch_projection) == next_v:
                            connections_to_consider = pants[v]['L']
                            break
                    for edge in pants[v]['R']:
                        if feature_on_the_other_side(edge, v, scratch_projection) == next_v:
                            connections_to_consider = pants[v]['R']
                            break

                    if len(connections_to_consider) > 1:
                        center_z = centroid_z(next_v, generatrice_layer)

                        power_sum = 0
                        for c in connections_to_consider:
                            feat_id = feature_on_the_other_side(c, v, scratch_projection)
                            power_sum += powers[feat_id]

                            if center_z < centroid_z(feat_id, generatrice_layer):
                                offset += powers[feat_id]

                        ratio = powers[next_v] / power_sum
                        offset /= power_sum

                v = loads(p.geometry().exportToWkt().replace('Z', ' Z'))

                length = math.sqrt(sum([pow(v.coords[1][i]-v.coords[0][i],2) for i in range(0, 3)]))
                norm = [(v.coords[1][i]-v.coords[0][i]) / length for i in range(0, 3)]

                v0 = [v.coords[0][i] + norm[i] * length * offset for i in range(0, 3)]
                v1 = [v0[i] + norm[i] * length * ratio for i in range(0, 3)]

                vertices += [ v0 ]
                vertices += [ v1 ]

            if len(vertices) > 0:
                result += [vertices]

        return result

    def export_polygons_impl(self, graph_layer, sections_layer, section_param = None):
        result = []

        try:
            section = section_param if section_param else Section("dummy")

            # build a scratch (temporary) layer to hold graph_layer features projections
            scratch_projection = self.create_projected_layer(graph_layer, section.id)
            # QgsMapLayerRegistry.instance().addMapLayer(scratch_projection, False)

            # associate graph_layer to its projection layer
            graph_section_layer = Layer(graph_layer, scratch_projection)

            line_width = float(self.__section.toolbar.buffer_width.text())

            logging.info('Start polygon export')

            # read unique layers (of generating lines) that are connected in the graph
            layers = graph_layer.uniqueValues(graph_layer.fields().fieldNameIndex('layer'))

            for lid in layers:
                logging.info('Processing layer {}'.format(lid))
                generatrice_layer = QgsMapLayerRegistry.instance().mapLayer(lid)
                fakes = fg_fake_generatrices(generatrice_layer, generatrice_layer)
                fakes_id = [f.id() for f in fakes]

                # a valid path starts and ends on a fake generatrice, so skip this layer
                # if there aren't any fakes
                if len(fakes_id) == 0:
                    logging.warning('No fake generatrices in {}'.format(generatrice_layer.id()))
                    continue

                request = QgsFeatureRequest().setFilterExpression(u"'layer' = '{0}'".format(lid))

                if section_param is None:
                    # for each section line
                    for feature in sections_layer.getFeatures():
                        logging.info('Processing section {}'.format(feature.id()))
                        wkt_line = QgsGeometry.exportToWkt(feature.geometry())
                        section.update(wkt_line, line_width) # todo

                        # export for real
                        result += self.__export_polygons_for_one_section_line(section, graph_section_layer, scratch_projection, fakes_id, request, generatrice_layer)
                else:
                    # export for real
                    result += self.__export_polygons_for_one_section_line(section, graph_section_layer, scratch_projection, fakes_id, request, generatrice_layer)

        except Exception as e:
            logging.error(e)
        finally:
            if section_param is None:
                section.unload()
            # QgsMapLayerRegistry.instance().removeMapLayer(scratch_projection.id())

            return result



    def draw_volume(self, section_layers):
        logging.info('build volume')

        nodes = []
        indices = {}
        edges = []

        def addVertice(geom):
            v = loads(geom.geometry().exportToWkt().replace('Z', ' Z'))
            return [[ list(v.coords[0]), list(v.coords[1]) ]]

        graphLayer = self.graphLayerHelper.layer()

        if graphLayer is None:
            return

        volumes, vertices = self.buildVolume(graphLayer, section_layers)

        self.viewer3d.updateVolume(vertices, volumes)
        self.viewer3d.updateGL()

    def buildVolume(self, graph_layer, section_layers):
        def same_vertex(v1, v2):
            return v1[0] == v2[0] and v1[1] == v2[1] and v1[2] == v2[2]

        def index_of(generatrice):
            for i in range(0, len(nodes)):
                if same_vertex(generatrice[0], nodes[i][0]) and same_vertex(generatrice[1], nodes[i][1]):
                    return i
            return -1

        nodes = []
        edges = []

        total = 0
        for layer in section_layers:
            if not layer is None:
                for polygon in self.export_polygons_impl(graph_layer, layer):
                    previous_idx = -1
                    for i in range(0, len(polygon), 2):
                        total += 1
                        generatrice = [polygon[i], polygon[i + 1]]

                        idx = index_of(generatrice)
                        if idx < 0:
                            nodes += [generatrice]
                            idx = len(nodes) - 1

                        # connect to previous node
                        if previous_idx >= 0:
                            edges += [(idx, previous_idx)]
                        previous_idx = idx

        return to_volume(np.array(nodes), edges)



    def draw_active_section_3d(self, section_layers):
        if self.__section.section.is_valid:
            # draw section line
            section_vertices = []
            for c in self.__section.section.line.coords:
                section_vertices += [[c[0], c[1], 250], [c[0], c[1], 500]]
            self.viewer3d.define_section_vertices(section_vertices)

    def draw_polygons_3d(self, section_layers, scale_z = 1.0):
        graphLayer = self.graphLayerHelper.layer()

        if graphLayer is None:
            return

        def centroid(l):
            return [0.5*(l.coords[0][i]+l.coords[1][i]) for i in range(0, 3)]

        if len(self.viewer3d.polygons_vertices) == 0:
            logging.info('Rebuild polygons!')
            self.viewer3d.polygons_colors = []
            for layer in section_layers:
                color = [1, 0, 0, 1] if section_layers.index(layer) == 0 else [0, 0, 1, 1]
                if not layer is None:
                    v = self.export_polygons_impl(graphLayer, layer)
                    self.viewer3d.polygons_vertices += v

                    for i in range(0, len(v)):
                        self.viewer3d.polygons_colors += [color]


    def redraw_3d_view(self, z_scale = None):
        if z_scale:
            self.viewer3d.scale_z = z_scale

        self.viewer3d.updateGL()

    def __create_polygon_projected_layer(self, layer):
        polygon_layer = QgsVectorLayer(
            "Polygon?crs={crs}&index=yes".format(
                crs=self.mapCanvas.mapSettings().destinationCrs().authid()
                ), layer.name() + "_polygon", "memory")

        polygon_layer.setReadOnly(True)

        # cpy attributes structure
        polygon_layer.dataProvider().addAttributes([layer.fields().field(f) for f in range(layer.fields().count())])
        polygon_layer.updateFields()
        # cpy style
        polygon_layer.setRendererV2(QgsSingleSymbolRendererV2(QgsFillSymbolV2()))
        return polygon_layer

    def __add_polygon_layer(self, layer, projected):
        if layer is None:
            return

        if not(layer is self.graphLayerHelper.layer() or layer is self.subGraphLayerHelper.layer()):
            return


        polygon_layer = self.__create_polygon_projected_layer(layer)

        section_id = projected.customProperty("section_id")
        # Do not tag as projected_layer here, so it's not added twice
        polygon_layer.setCustomProperty("polygon_projected_layer", layer.id())
        polygon_layer.setCustomProperty("section_id", section_id)

        QgsMapLayerRegistry.instance().addMapLayer(polygon_layer)

        group = self.__iface.layerTreeView().layerTreeModel().rootGroup().findGroup(section_id)
        assert not(group is None)
        group.addLayer(polygon_layer)
        logging.debug('register polygon!')
        self.__section.section.register_projection_layer(PolygonLayerProjection(layer, polygon_layer, self))

    def add_layers(self, layers):
        self.graphLayerHelper.lookup(layers)
        self.subGraphLayerHelper.lookup(layers)

        for layer in layers:
            if hasattr(layer, 'customProperty') \
                    and layer.customProperty("section_id") is not None \
                    and layer.customProperty("section_id") == self.__section.section.id :
                source_layer = projected_layer_to_original(layer, "polygon_projected_layer")
                if source_layer is not None:
                    l = PolygonLayerProjection(source_layer, layer, self)
                    self.__section.section.register_projection_layer(l)
                    l.apply(self.__section.section, True)

    def __add_layer(self):
        # popup selection widget
        CreateLayerWidget(self.__logger).exec_()

    def __import_csv(self):
        data_layer = self.mapCanvas.currentLayer()
        if data_layer is None:
            return

        dialog = QProgressDialog("Importing features", "Cancel", 0, data_layer.featureCount(), self)
        self.importer = ConvertDataLayer(data_layer, dialog)
        dialog.finished.connect(self.__reset_import)
        dialog.finished.connect(self.__reset_import)
        self.importer.tick()

    def __reset_import(self, value):
        logging.warning('finished', value)
        self.importer = None


    def __toggle_edit_graph(self, checked):
        if checked:
            self.edit_graph_tool.activate();
            self.previousTool = self.__section.canvas.mapTool()
            self.__section.canvas.setMapTool(self.edit_graph_tool)
        else:
            self.edit_graph_tool.deactivate();
            self.__section.canvas.setMapTool(self.previousTool)

class Plugin():
    def __init__(self, iface):
        FORMAT = '\033[30;100m%(created)-13s\033[0m \033[33m%(filename)-12s\033[0m:\033[34m%(lineno)4d\033[0m %(levelname)8s %(message)s' if sys.platform.find('linux')>= 0 else '%(created)13s %(filename)-12s:%(lineno)4d %(message)s'
        lvl = logging.DEBUG if sys.platform.find('linux')>= 0 else logging.CRITICAL
        logging.basicConfig(format=FORMAT, level=lvl)

        self.__iface = iface
        self.rendering_3d_intialized = False

    def cleanup_data(self):
        if self.graphLayerHelper.layer() is None:
            return

        self.graphLayerHelper.layer().beginEditCommand('edges geom')
        # Store invalid graph elements for removal
        edge_removed = []
        for edge in self.graphLayerHelper.layer().getFeatures():
            try:
                lid = edge.attribute("layer")
                layer = QgsMapLayerRegistry.instance().mapLayer(lid)
                featA = layer.getFeatures(QgsFeatureRequest(edge.attribute("start"))).next()
                featB = layer.getFeatures(QgsFeatureRequest(edge.attribute("end"))).next()

                # update geometry
                self.graphLayerHelper.layer().dataProvider().changeGeometryValues({edge.id(): QgsGeometry.fromWkt(GraphEditTool.segmentGeometry(featA, featB).wkt)})

            except Exception as e:
                logging.error(e)
                # invalid data -> removing
                edge_removed += [ edge.id() ]

        self.graphLayerHelper.layer().endEditCommand()

        if edge_removed:
            res = QMessageBox().information(self.toolbar, 'Graph cleanup', 'Will remove {} graph edge(s)'.format(len(edge_removed)), QMessageBox.Ok | QMessageBox.Cancel)

            if res == QMessageBox.Ok:
                self.graphLayerHelper.layer().beginEditCommand('edges cleanup')
                self.graphLayerHelper.layer().dataProvider().deleteFeatures(edge_removed)
                self.graphLayerHelper.layer().endEditCommand()

    def graph_layer_tagged(self, graph):
        self.edit_graph_tool.set_graph_layer(graph)

    def __update_3d_combo(self, layers):
        rpix = QPixmap(100,100)
        rpix.fill(QColor("red"))
        bpix = QPixmap(100,100)
        bpix.fill(QColor("blue"))

        red = QIcon(rpix)
        blue = QIcon(bpix)

        for combo in self.viewer3d_combo:
            for layer in layers:
                if not layer.customProperty('section_id') is None:
                    continue
                if layer == self.graphLayerHelper.layer() or layer == self.subGraphLayerHelper.layer():
                    continue
                if not layer.isSpatial():
                    continue

                combo.addItem(red if self.viewer3d_combo.index(combo) == 0 else blue, layer.name(), layer.id())


    def layer_visibility_changed(self, node):
        if self.toolbar.viewer3d.layers_vertices is None:
            return

        for lid in self.toolbar.viewer3d.layers_vertices:
            self.toolbar.viewer3d.layers_vertices[lid]['visible'] = self.__iface.legendInterface().isLayerVisible(QgsMapLayerRegistry.instance().mapLayers()[lid])

        self.toolbar.viewer3d.updateGL()

    def export_volume(self):
        pass
        section_layers = []
        for combo in self.viewer3d_combo:
            lid = combo.itemData(combo.currentIndex())
            section_layers += [QgsMapLayerRegistry.instance().mapLayer(lid)]

        if len(section_layers) < 2:
            return

        volumes, vertices = self.toolbar.buildVolume(self.graphLayerHelper.layer(), section_layers)

        # drawing = dxf.drawing('/tmp/test.dxf')

        for vol in volumes:
            for tri in vol:
                idx = len(vertices)
                v = [ vertices[tri[i]] for i in range(0, 3) ]
                drawing.add(dxf.face3d([tuple(v[0]), tuple(v[1]), tuple(v[2])], flags=1))

        drawing.save()
        print vertices

    def display_polygons_volumes_3d(self, update_active_section_only = True):
        if self.initialize_3d_rendering():
            update_active_section_only = False

        section_layers = []
        for combo in self.viewer3d_combo:
            lid = combo.itemData(combo.currentIndex())
            section_layers += [QgsMapLayerRegistry.instance().mapLayer(lid)]

        self.toolbar.draw_active_section_3d(section_layers)
        if not update_active_section_only:
            self.toolbar.draw_polygons_3d(section_layers)
            self.toolbar.draw_volume(section_layers)

        self.toolbar.redraw_3d_view(float(self.viewer3d_scale_z.text()))


    def initialize_3d_rendering(self):
        section_layers = []
        for combo in self.viewer3d_combo:
            lid = combo.itemData(combo.currentIndex())
            if not lid is None:
                section_layers += [QgsMapLayerRegistry.instance().mapLayer(lid)]

        if len(section_layers) != 2:
            return False

        if not self.rendering_3d_intialized:
            self.rendering_3d_intialized = True

            # hmmmm
            layers_vertices = {}
            for layer in QgsMapLayerRegistry.instance().mapLayers().values():
                # only draw projected layers
                if not layer.customProperty('section_id') is None:
                    continue
                if layer == self.graphLayerHelper.layer():
                    continue
                if layer == self.subGraphLayerHelper.layer():
                    continue
                if not layer.isSpatial():
                    continue
                if QgsWKBTypes.geometryType(int(layer.wkbType())) != QgsWKBTypes.LineGeometry:
                    continue
                if not isinstance(layer.rendererV2(), QgsSingleSymbolRendererV2):
                    continue
                if layer in section_layers:
                    continue

                layer_vertices = []
                for feature in layer.getFeatures():
                    wkt = feature.geometry().exportToWkt()
                    if wkt.find('Z') < 0:
                        break
                    v = loads(wkt.replace('Z', ' Z'))

                    layer_vertices += [ list(v.coords[0]), list(v.coords[1]) ]

                if len(layer_vertices) > 0:
                    layers_vertices[layer.id()] = { 'v': np.array(layer_vertices), 'c': layer.rendererV2().symbol().color().getRgbF(), 'visible': self.__iface.legendInterface().isLayerVisible(layer)}

            self.toolbar.viewer3d.define_generatrices_vertices(layers_vertices)

            self.display_polygons_volumes_3d(False)
            return True

        return False

    def on_graph_modified(self):
        logging.info('on_graph_modified')
        self.viewer3d.polygons_vertices = []
        # update 3d view
        self.display_polygons_volumes_3d(False)
        self.__section_main.canvas.refresh()
        self.__iface.mapCanvas().refresh()

    def initGui(self):
        self.__section_main = MainWindow(self.__iface, 'section')
        self.__dock = QDockWidget('Section')
        self.__dock.setWidget(self.__section_main)

        # self.__legend_dock = QDockWidget('Section Legend')
        # self.__legend_dock.setWidget(self.__section_main.tree_view)

        self.viewer3d = Viewer3D()

        self.graphLayerHelper = GraphLayerHelper("graph_layer")
        self.subGraphLayerHelper = GraphLayerHelper("sub_graph_layer")

        self.toolbar = DataToolbar(self.__iface, self.__section_main, self.viewer3d, self.graphLayerHelper, self.subGraphLayerHelper)
        self.edit_graph_tool = GraphEditTool(self.__section_main.canvas)
        self.select_graph_tool = SelectionTool(self.__section_main.canvas)

        self.__section_main.toolbar.line_clicked.connect(self.edit_graph_tool._reset)
        self.__section_main.toolbar.line_clicked.connect(self.display_polygons_volumes_3d)
        self.edit_graph_tool.graph_modified.connect(self.on_graph_modified)
        self.graphLayerHelper.graph_layer_tagged.connect(self.graph_layer_tagged)

        self.__iface.layerTreeView().layerTreeModel().rootGroup().visibilityChanged.connect(self.layer_visibility_changed)


        self.toolbar.addAction('Clean graph').triggered.connect(self.cleanup_data)

        # in case we are reloading
        self.toolbar.add_layers(QgsMapLayerRegistry.instance().mapLayers().values())

        # self.__section_main.section.section_layer_modified.connect(self.__update_graphs_geometry)
        self.__iface.addToolBar(self.toolbar)
        self.viewer3d_dock = QDockWidget('3d View')
        self.viewer3d_window = QMainWindow(None)
        self.viewer3d_window.setWindowFlags(Qt.Widget)
        self.viewer3d_toolbar = QToolBar()
        self.viewer3d_window.addToolBar(Qt.TopToolBarArea, self.viewer3d_toolbar)
        self.viewer3d_window.setCentralWidget(self.viewer3d)
        self.viewer3d_dock.setWidget(self.viewer3d_window)
        self.viewer3d_scale_z = QLineEdit("3.0")
        self.viewer3d_scale_z.setMaximumWidth(50)
        self.viewer3d_scale_z.editingFinished.connect(lambda: self.toolbar.redraw_3d_view(float(self.viewer3d_scale_z.text())))

        self.viewer3d_combo = [QComboBox(), QComboBox()]
        for combo in self.viewer3d_combo:
            combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            combo.addItem('-', None)
            self.viewer3d_toolbar.addWidget(combo)

        self.viewer3d_toolbar.addWidget(self.viewer3d_scale_z)
        # self.viewer3d_toolbar.addAction(QgsApplication.getThemeIcon('/mActionDraw.svg'), 'refresh').triggered.connect(self.initialize_3d_rendering)

        self.viewer3d_toolbar.addAction(icon('6_export_volume.svg'), 'Export volume (graph)').triggered.connect(self.export_volume)

        QgsMapLayerRegistry.instance().layersAdded.connect(self.__update_3d_combo)
        self.__update_3d_combo(QgsMapLayerRegistry.instance().mapLayers().values())


        self.__iface.addDockWidget(Qt.BottomDockWidgetArea, self.viewer3d_dock)

        section_actions = self.__section_main.canvas.build_default_section_actions()
        section_actions += [
            None,
            { 'icon': icon('10_edit_graph.svg'), 'label': 'edit graph layer', 'tool': self.edit_graph_tool, 'precondition': lambda action: self.__toggle_edit_graph_precondition_check() },
            { 'icon': icon('12_add_graph.svg'), 'label': 'create subgraph', 'clicked': self.__create_subgraph, 'precondition': lambda action: self.__create_subgraph_precondition_check() },
            { 'icon': icon('11_add_generatrices.svg'), 'label': 'add generatrices', 'clicked': self.__add_generatrices, 'precondition': lambda action: self.__add_generatrices_precondition_check() },
            { 'icon': icon('13_maj_graph.svg'), 'label': 'update graphs geom', 'clicked': self.__update_graphs_geometry, 'precondition': lambda action: self.__update_graphs_geometry_precondition_check() },
            None,
            { 'label': 'reset subgraph|gen.', 'clicked': self.__reset_subgraph, 'precondition': lambda action: self.__reset_subgraph_precondition_check() },

        ]

        self.generatrice_distance = QLineEdit("25")
        self.generatrice_distance.setMaximumWidth(50)
        self.__section_main.toolbar.addWidget(QLabel("Generatrice dist.:"))
        self.__section_main.toolbar.addWidget(self.generatrice_distance)

        self.__section_main.canvas.add_section_actions_to_toolbar(section_actions, self.__section_main.toolbar)

        self.__iface.addDockWidget(Qt.BottomDockWidgetArea, self.__dock)
        # self.__iface.addDockWidget(Qt.LeftDockWidgetArea, self.__legend_dock)

    def unload(self):
        # self.__section_main.section.section_layer_modified.disconnect(self.__update_graphs_geometry)
        self.__iface.layerTreeView().layerTreeModel().rootGroup().visibilityChanged.disconnect(self.layer_visibility_changed)
        self.__section_main.toolbar.line_clicked.disconnect(self.edit_graph_tool._reset)
        self.__section_main.toolbar.line_clicked.disconnect(self.display_polygons_volumes_3d)
        QgsMapLayerRegistry.instance().layersAdded.disconnect(self.__update_3d_combo)

        self.__dock.setWidget(None)
        # self.__legend_dock.setWidget(None)
        self.__iface.removeDockWidget(self.__dock)
        # self.__iface.removeDockWidget(self.__legend_dock)
        self.__section_main.unload()
        self.toolbar.setParent(None)
        self.toolbar.cleanup()
        self.toolbar = None
        self.viewer3d_dock.setParent(None)
        self.__section_main = None

    def __reset_subgraph_precondition_check(self):
        if self.subGraphLayerHelper.layer() is None:
            return (False, 'Missing subgraph')
        if not self.__section_main.section.is_valid:
            return (False, "No active section")
        return (True, "")

    def __reset_subgraph(self):
        # remove everything in subgraph for this section
        subgraph = self.subGraphLayerHelper.layer()
        projected_subgraph = filter(lambda l: (not isinstance(l, PolygonLayerProjection)), self.__section_main.section.projections_of(subgraph.id()))[0].projected_layer

        to_remove = []
        for segment in projected_subgraph.getFeatures():
            logging.debug('FOUND SEGMENT {}'.format(segment.id()))
            to_remove += [projected_feature_to_original(subgraph, segment).id()]

        logging.debug('REMOVE: {}'.format(to_remove))
        if len(to_remove) > 0:
            subgraph.dataProvider().deleteFeatures(to_remove)
            self.__section_main.section.update_projections(subgraph.id())
            self.__section_main.section.request_canvas_redraw()


        layer = self.__iface.mapCanvas().currentLayer()
        if layer is None:
            return

        if layer.customProperty("section_id") is None:
            return

        # if active layer is a projection try to remove fake generatrice
        source = projected_layer_to_original(layer)

        fakes = fg_fake_generatrices(source, layer)
        to_remove = []
        for f in fakes:
            logging.debug('FOUND GENERATRICE {}'.format(f.id()))
            to_remove += [projected_feature_to_original(source, f).id()]

        logging.debug('REMOVE2: {}'.format(to_remove))
        if len(to_remove) > 0:
            source.dataProvider().deleteFeatures(to_remove)
            self.__section_main.section.update_projections(source.id())
            self.__section_main.section.request_canvas_redraw()



    def __update_graphs_geometry_precondition_check(self):
        if not self.__section_main.section.is_valid:
            return (False, "No active section")
        return (True, "")

    def __update_graphs_geometry(self):

        targets = [self.graphLayerHelper.layer(), self.subGraphLayerHelper.layer()]

        for target in targets:
            if target is None:
                continue

            attr = ['start', 'end'] if target.fields().fieldNameIndex('start') >= 0 else ['start:Integer64(10,0)', 'end:Integer64(10,0)']

            target.beginEditCommand('update segment geom')

            for segment in target.getFeatures():
                layer_id =  segment.attribute('layer')
                layer = QgsMapLayerRegistry.instance().mapLayer(layer_id)
                featA = layer.getFeatures(QgsFeatureRequest(segment.attribute(attr[0]))).next()
                featB = layer.getFeatures(QgsFeatureRequest(segment.attribute(attr[1]))).next()
                target.dataProvider().changeGeometryValues({segment.id(): QgsGeometry.fromWkt(GraphEditTool.segmentGeometry(featA, featB).wkt)})

            target.endEditCommand()
            target.updateExtents()

    # def __update_graphs_geometry(self, layer):
    #     if not self.__section_main.section.is_valid:
    #         return
    #     edit = layer.projected_layer.editBuffer()
    #     if edit is None:
    #         return
    #     print ">>>>>>> {} will commit changes".format(layer.projected_layer.id())

    #     targets = [self.graphLayerHelper.layer(), self.subGraphLayerHelper.layer()]

    #     for id_ in edit.changedGeometries():
    #         f = layer.projected_layer.getFeatures(QgsFeatureRequest(id_)).next()
    #         print f, f.id()
    #         print f.attributes()
    #         f.setFields(layer.projected_layer.fields(), False)
    #         print layer.projected_layer.fields().allAttributesList()
    #         print f.attributes()
    #         my_id = f.attribute('id') if layer.projected_layer.fields().fieldNameIndex('id') >= 0 else f.attribute('id:Integer64(10,0)')
    #         query = u"attribute($currentfeature, 'start') = {} OR attribute($currentfeature, 'end') = {}".format(my_id, my_id)

    #         for target in targets:
    #             if target is None:
    #                 continue
    #             target.beginEditCommand('update segment geom')

    #             # lookup every segment with start|end == i
    #             segments = target.getFeatures(QgsFeatureRequest().setFilterExpression(query))

    #             print 'ICI >'
    #             print 'query', query
    #             for segment in segments:
    #                 print target.id(), segment
    #                 featA = layer.getFeatures(QgsFeatureRequest(segment.attribute('start'))).next()
    #                 featB = layer.getFeatures(QgsFeatureRequest(segment.attribute('end'))).next()

    #                 layer.changeGeometry(segment.id(), QgsGeometry.fromWkt(GraphEditTool.segmentGeometry(featA, featB).wkt))
    #             print 'ICI <'

    #             target.endEditCommand()
    #             target.updateExtents()

    def __toggle_edit_graph_precondition_check(self):
        if not self.__section_main.section.is_valid:
            return (False, "No active section line")
        if self.graphLayerHelper.layer() is None:
            return (False, "No graph layer")
        layer = self.__iface.mapCanvas().currentLayer()
        if layer is None:
            self.edit_graph_tool._reset()
            return (False, "No active layer")
        if layer.customProperty("section_id") is None:
            self.edit_graph_tool._reset()
            return (False, "Active layer must be a projection")

        return (True, "")

    def __add_generatrices_precondition_check(self):
        layer = self.__iface.mapCanvas().currentLayer()

        if layer is None:
            return (False, "No active layer")
        if not self.__section_main.section.is_valid:
            return (False, "No active section line")
        source_layer = projected_layer_to_original(layer)
        if source_layer is None:
            return (False, "Active layer must be a projection")
        if self.graphLayerHelper.layer() is None and self.subGraphLayerHelper.layer() is None:
            return (False, "No (sub)graph layer")
        return (True, "")

    def __create_subgraph_precondition_check(self):
        if not self.__section_main.section.is_valid:
            return (False, "No active section line")
        graphLayer = self.graphLayerHelper.layer()
        if self.graphLayerHelper.layer() is None:
            return (False, "No graph layer")
        if self.subGraphLayerHelper.layer() is None:
            return (False, "No subgraph layer")
        proj = self.__iface.mapCanvas().currentLayer()
        if proj is None:
            return (False, "No active layer")
        if proj.customProperty("section_id") != self.__section_main.section.id:
            return (False, "Active layer isn't a projection of section")

        projected_graph = filter(lambda l: (not isinstance(l, PolygonLayerProjection)), self.__section_main.section.projections_of(graphLayer.id()))[0]
        if projected_graph is None:
            return (False, "Missing graph projection")

        # current layer = mineralised
        source_layer = projected_layer_to_original(proj)
        if source_layer is None:
            return (False, "Active layer isn't a projection of section")
        return (True, "")

    def __add_generatrices(self):
        try:
            # disable updates for 2 reasons:
            #  - perf
            #  - projected layer content won't change during update
            self.__section_main.section.disable()

            if not self.graphLayerHelper.layer() is None:
                logging.info('Add generatrices for graph')
                self.__add_generatrices_impl(self.graphLayerHelper.layer())

            if not self.subGraphLayerHelper.layer() is None:
                logging.info('Add generatrices for subgraph')
                self.__add_generatrices_impl(self.subGraphLayerHelper.layer())

        finally:
            self.__section_main.section.enable()
            if not self.graphLayerHelper.layer() is None:
                self.__section_main.section.update_projections(self.graphLayerHelper.layer().id())
            if not self.subGraphLayerHelper.layer() is None:
                self.__section_main.section.update_projections(self.subGraphLayerHelper.layer().id())

            layer = self.__iface.mapCanvas().currentLayer()
            source_layer = projected_layer_to_original(layer)
            self.__section_main.section.update_projections(source_layer.id())

            self.on_graph_modified()


    def __add_generatrices_impl(self, graph):
        layer = self.__iface.mapCanvas().currentLayer()

        logging.debug('Begin __add_generatrices_impl')

        if layer is None or not self.__section_main.section.is_valid:
            return

        source_layer = projected_layer_to_original(layer)
        if source_layer is None:
            return


        projected_graph = filter(lambda l: (not isinstance(l, PolygonLayerProjection)), self.__section_main.section.projections_of(graph.id()))[0].projected_layer

        ids = graph.uniqueValues(graph.fieldNameIndex('id'))
        my_id = (max(ids) if len(ids) > 0 else 0) + 1

        ids = source_layer.uniqueValues(source_layer.fieldNameIndex('id'))
        my_fake_id = (max(ids) if len(ids) > 0 else 0) + 1

        has_field_HoleID = layer.fields().fieldNameIndex("HoleID") >= 0
        has_field_mine = layer.fields().fieldNameIndex("mine") >= 0
        has_field_mine_str = layer.fields().fieldNameIndex("mine:Integer64(10,0)") >= 0

        # Compute fake generatrice translation
        distance = float(self.generatrice_distance.text())
        a = self.__section_main.section.unproject_point(distance, 0, 0)
        b = self.__section_main.section.unproject_point(0, 0, 0)
        translation_vec = tuple([a[i]-b[i] for i in range(0, 2)])

        query = QgsFeatureRequest().setFilterExpression (u'"layer" = "{0}"'.format(source_layer.id()))

        ## First get a list of projected features
        id_field = 'id' if layer.fields().fieldNameIndex('id') >= 0 else 'id:Integer64(10,0)'
        projected_generatrice_centroids = {}
        projected_fakes = []
        for feature in layer.getFeatures():
            feature.setFields(layer.fields(), False)
            projected_generatrice_centroids[feature.attribute(id_field)] = feature.geometry().centroid().asPoint()

        logging.debug('projected_generatrice_centroids = {}'.format(projected_generatrice_centroids.keys()))

        ## Then browse source features
        source_features = []
        for source_feature in source_layer.getFeatures(QgsFeatureRequest().setFilterExpression ( u'"id" IN {}'.format(str(tuple(projected_generatrice_centroids.keys()))))):
            source_features += [source_feature]
        logging.debug(source_features)

        connections, edges_id = build_graph_connections_list(projected_graph, source_layer.id(), [sf.id() for sf in source_features])

        graph.beginEditCommand('update edges')
        for i in range(0, len(source_features)):
            source_feature = source_features[i]
            source_feature.setFields(source_layer.fields(), False)

            # filter out fake generatrices
            if (has_field_HoleID and source_feature.attribute("HoleID") == "Fake") or (has_field_mine and source_feature.attribute("mine") == -1):
                continue

            feature_id = source_feature.attribute('id')

            # Get all connected edges for this feature
            connected_edges = edges_from_edges_id(projected_graph, edges_id[i], projected_generatrice_centroids[feature_id].x())
            logging.debug('connected {}|{}'.format(len(connected_edges['L']), len(connected_edges['R'])))

            # If this feature is connected on one side only -> add the missing generatrice on the other side
            if xor(len(connected_edges['L']) == 0, len(connected_edges['R']) == 0):
                missing_side = 1.0 if len(connected_edges['R']) == 0 else -1.0

                generatrice = fg_create(self.__section_main.section, source_layer, source_feature, my_fake_id, translation_vec, missing_side)
                # Read back feature to get proper id()
                fake_feature = fg_insert(source_layer, generatrice)
                # Add link in subgraph
                fg_connect(graph, source_feature, fake_feature, my_id, source_layer)

                my_fake_id = my_fake_id + 1
                my_id = my_id + 1
            elif len(connected_edges['L']) == 0 and len(connected_edges['R']) == 0 and source_feature.id() in source_layer.selectedFeaturesIds():
                for d in [-1.0, 1.0]:
                    generatrice = fg_create(self.__section_main.section, source_layer, source_feature, my_fake_id, translation_vec, d)
                    # Read back feature to get proper id()
                    fake_feature = fg_insert(source_layer, generatrice)
                    # Add link in subgraph
                    fg_connect(graph, source_feature, fake_feature, my_id, source_layer)
                    my_fake_id = my_fake_id + 1
                    my_id = my_id + 1

            # If this feature is connected to N (> 1) elements on 1 side -> add 1 fake generatrices
            if False:  # for side in connected_edges:

                raise 'update me'
                if len(connected_edges[side]) > 1:
                    missing_side = 1.0 if side == 'R' else -1.0
                    logging.debug('jambe pantalon {}'.format(missing_side))
                    # Hardcode 60cm fake generatrice distance
                    scale_factor = 0.6 / distance
                    generatrice = fg_create(self.__section_main.section, source_layer, source_feature, my_fake_id, [d * scale_factor for d in translation_vec], missing_side)
                    fake_feature = fg_insert(source_layer, generatrice)
                    fg_connect(graph, source_feature, fake_feature, my_id, source_layer)

                    logging.debug('added fake feature {}|{}'.format(fake_feature.id(), my_fake_id))
                    my_fake_id = my_fake_id + 1
                    my_id = my_id + 1


                    # Modify existing edges
                    for edge in connected_edges[side]:
                        attr = edge.attributes()

                        for field in range(0, len(graph_attr)):
                            index = edge.fieldNameIndex(graph_attr[field])

                            if attr[index] == source_feature.id():
                                index2 = edge.fieldNameIndex(graph_attr[1 - field])
                                other = attr[index2]

                                logging.debug('replace {} -> {}'.format(attr[index], fake_feature.id()))
                                fg_connect(graph, fake_feature, source_layer.getFeatures(QgsFeatureRequest(other)).next(), my_id, source_layer)

                        my_id = my_id + 1

                    logging.debug('Remove deprecated links {}'.format([projected_feature_to_original(graph, f).id() for f in connected_edges[side]]))
                    graph.dataProvider().deleteFeatures([projected_feature_to_original(graph, f).id() for f in connected_edges[side]])
        graph.endEditCommand()
        logging.debug('End __add_generatrices_impl')



    def __create_subgraph(self):
        graphLayer = self.graphLayerHelper.layer()
        subGraphLayer = self.subGraphLayerHelper.layer()
        proj = self.__iface.mapCanvas().currentLayer()

        if proj is None or graphLayer is None or subGraphLayer is None:
            return

        if not self.__section_main.section.is_valid:
            return

        if proj.customProperty("section_id") != self.__section_main.section.id:
            return

        projected_graph = filter(lambda l: (not isinstance(l, PolygonLayerProjection)), self.__section_main.section.projections_of(graphLayer.id()))[0]

        # current layer = mineralised
        source_layer = projected_layer_to_original(proj)

        logging.debug(source_layer)
        if source_layer is None or projected_graph is None:
            return

        features = []

        ids = subGraphLayer.uniqueValues(subGraphLayer.fieldNameIndex('id'))
        my_id = (max(ids) if len(ids) > 0 else 0) + 1



        # for each selected edge of the graph
        for edge in projected_graph.projected_layer.getFeatures():
            edge.setFields(graphLayer.fields(), False)
            layer = QgsMapLayerRegistry.instance().mapLayer(edge.attribute("layer"))
            start = layer.getFeatures(QgsFeatureRequest(edge.attribute("start"))).next()
            end = layer.getFeatures(QgsFeatureRequest(edge.attribute("end"))).next()


            # select all features of source_layer intersecting 'start'
            s = source_layer.getFeatures(QgsFeatureRequest(start.geometry().boundingBox()))
            # select all features of source_layer intersecting 'end'
            e = source_layer.getFeatures(QgsFeatureRequest(end.geometry().boundingBox()))

            for a in s:
                e = source_layer.getFeatures(QgsFeatureRequest(end.geometry().boundingBox()))
                for b in e:
                    req = QgsFeatureRequest().setFilterExpression (u'"start" = {0} AND "end" = {1}'.format(a.id(), b.id()))
                    # don't recreate an existing link
                    if len(list(graphLayer.getFeatures(req))) > 0:
                        continue

                    features += [ GraphEditTool.createSegmentEdge(a, b, my_id, subGraphLayer.fields(), source_layer.id()) ]
                    my_id = my_id + 1

        if len(features) > 0:
            subGraphLayer.beginEditCommand('subgraph creation')
            subGraphLayer.dataProvider().addFeatures(features)
            subGraphLayer.endEditCommand()
            subGraphLayer.updateExtents()


class ConvertDataLayer():
    def __init__(self, data_layer, dialog):
        self.dialog = dialog
        self.data_layer = data_layer
        self.new_layer = QgsVectorLayer(
            "LineString?&index=yes".format(
                data_layer.crs().authid()
                ), data_layer.name(), "memory")

        fields = [data_layer.fields().field(f) for f in range(data_layer.fields().count())]
        fields += [QgsField("id", QVariant.Int)]
        self.new_layer.dataProvider().addAttributes(fields)
        self.new_layer.updateFields()

        self.my_id = 0
        self.features = data_layer.getFeatures()
        QgsMapLayerRegistry.instance().addMapLayer(self.new_layer)


    def tick(self):
        logging.debug('TICK')
        features = []
        for f in self.features:
            p1 = (f.attribute('From X'), f.attribute('From Y'), f.attribute('From Z'))
            p2 = (f.attribute('To X'), f.attribute('To Y'), f.attribute('To Z'))
            geom = LineString([p1, p2])
            new_feature = QgsFeature()
            new_feature.setGeometry(QgsGeometry.fromWkt(geom.wkt.replace(' Z', 'Z')))

            attrs = f.attributes()
            attrs += [self.my_id]
            new_feature.setAttributes(attrs)
            self.my_id = self.my_id + 1
            features += [new_feature]

            self.dialog.setValue(self.my_id)

            if len(features) == 1000:
                break

        self.new_layer.beginEditCommand('layer creation')
        self.new_layer.dataProvider().addFeatures(features)
        self.new_layer.endEditCommand()
        self.new_layer.updateExtents()

        if self.dialog.wasCanceled():
            pass
        elif self.features.isClosed():
            pass
        else:
            self.timer = QTimer.singleShot(0, self.tick)
