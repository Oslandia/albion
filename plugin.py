# coding=utf-8
from qgis.core import *
from qgis.gui import *

from PyQt4.QtCore import Qt, QObject
from PyQt4.QtGui import (QDockWidget,
                         QColor,
                         QToolBar,
                         QIcon,
                         QMainWindow,
                         QProgressDialog,
                         QPixmap,
                         QFileDialog,
                         QLineEdit,
                         QLabel,
                         QMessageBox,
                         QComboBox)

import sys
import numpy as np

from .main_window import MainWindow
from shapely.wkt import loads

from .graph_edit_tool import GraphEditTool

from .viewer_3d.viewer_3d import Viewer3D

from .fake_generatrice import create as fg_create
from .fake_generatrice import insert as fg_insert
from .fake_generatrice import connect as fg_connect
from .fake_generatrice import fake_generatrices as fg_fake_generatrices

from .qgis_hal import (get_feature_by_id,
                       get_layer_selected_ids,
                       get_layer_unique_attribute,
                       get_layer_by_id,
                       get_id,
                       get_name,
                       get_all_layers,
                       get_all_layer_features,
                       feature_to_shapely_wkt,
                       get_feature_attribute_values,
                       projected_layer_to_original,
                       projected_feature_to_original,
                       get_layers_with_properties,
                       root_layer_group_from_iface,
                       is_a_projected_layer,
                       get_feature_centroid,
                       create_new_feature,
                       insert_features_in_layer)

from .graph import to_volume

from .graph_operations import (
    refresh_graph_layer_edges,
    find_generatrices_needing_a_fake_generatrice_in_section,
    compute_section_polygons_from_graph)
from .section_projection import (project_layer_as_linestring,
                                 project_layer_as_polygon)

from .global_toolbar import GlobalToolbar

from .utils import (max_value,
                    icon,
                    create_projected_layer,
                    unproject_point,
                    sort_id_along_implicit_centroids_line,
                    centroids_to_line_wkt)

import logging
import traceback
# from dxfwrite import DXFEngine as dxf


def compute_sections_polygons_from_graph(graph_layer,
                                         sections_layer,
                                         section_width):
    result = []

    for feature in get_all_layer_features(sections_layer):
        try:
            logging.info('   - {}: {}'.format(
                get_name(sections_layer), get_id(feature)))
            line = loads(feature_to_shapely_wkt(feature))

            # build a temporary layer to hold graph_layer features projections
            graph_projection = create_projected_layer(graph_layer, 'dummy')
            project_layer_as_linestring(line, 1.0, section_width,
                                        graph_layer, graph_projection)

            result += compute_section_polygons_from_graph(
                graph_layer, graph_projection, line, section_width)
        except Exception as e:
            logging.error('err {}. Feature: {}/{}'.format(
                e, get_id(sections_layer), get_id(feature)))
            traceback.print_exc()

    return result


class Plugin(QObject):
    def __init__(self, iface):
        QObject.__init__(self, None)
        FORMAT = '\033[30;100m%(created)-13s\033[0m \033[33m%(filename)-12s\033[0m:\033[34m%(lineno)4d\033[0m %(levelname)8s %(message)s' if sys.platform.find('linux')>= 0 else '%(created)13s %(filename)-12s:%(lineno)4d %(message)s'
        lvl = logging.INFO if sys.platform.find('linux')>= 0 else logging.CRITICAL
        logging.basicConfig(format=FORMAT, level=lvl)

        self.__iface = iface
        self.rendering_3d_intialized = False

    # Signal Handling
    #################
    #   - user selected a new active graph layer
    def __current_graph_layer_changed(self, graph):
        self.edit_graph_tool.set_graph_layer(graph)

    #   - layer visibility was changed (in treeview)
    def __layer_visibility_changed(self, node):
        if isinstance(node, QgsLayerTreeLayer):
            lid = get_id(node.layer())
            self.viewer3d.set_generatrices_visibility(
                lid, self.__iface.legendInterface().isLayerVisible(
                    get_layer_by_id(lid)))

        self.viewer3d.updateGL()

    #   - graph layer was mofified (e.g: user added a feature)
    def __on_graph_modified(self):
        logging.info('__on_graph_modified')
        self.viewer3d.polygons_vertices = []
        # update 3d view
        self.display_polygons_volumes_3d(False)
        self.__section_main.canvas.refresh()
        self.__iface.mapCanvas().refresh()

    #   - new layers were loaded or added
    def __layers_added(self, layers):
        all_layers = get_all_layers()
        self.toolbar.graphLayerHelper.update_layers(all_layers)
        self.toolbar.sections_layers_combo.update_layers()
        for layer in layers:
            layer.editCommandEnded.connect(self.__update_projection_if_needed)

    #   - layers were removed
    def __layers_will_be_removed(self, layer_ids):
        for layer_id in layer_ids:
            get_layer_by_id(layer_id).editCommandEnded.\
                disconnect(self.__update_projection_if_needed)

    def __update_projection_if_needed(self):
        layer = self.sender()
        logging.info('__update_projection_if_needed {}'.format(get_id(layer)))

        matching = get_layers_with_properties(
            {'section_id': self.__section_main.section.id,
             'projected_layer':  get_id(layer)})

        for l in matching:
            project_layer_as_linestring(
                self.__section_main.section.line,
                self.__section_main.section.z_scale,
                self.__section_main.section.width,
                layer, l)

        matching = get_layers_with_properties(
            {'section_id': self.__section_main.section.id,
             'polygon_projected_layer': get_id(layer)})

        for l in matching:
            project_layer_as_polygon(
                self.__section_main.section.line,
                self.__section_main.section.z_scale,
                self.__section_main.section.width,
                layer, l)

    def __redraw_3d_view(self):
        self.viewer3d.scale_z = float(self.viewer3d_scale_z.text())
        self.viewer3d.updateGL()

    # Buttons (actions) handling
    ############################
    #   - refresh graph geometries
    def cleanup_data(self):
        refresh_graph_layer_edges(self.toolbar.graphLayerHelper.active_layer())

    #   - create a section line from active selection
    def __create_line_from_selection(self):
        layer = self.__iface.mapCanvas().currentLayer()
        if layer is None:
            return

        # browse layers, and stop at the first one with selected features
        for l in get_all_layers():

            if is_a_projected_layer(l):
                continue

            selection = get_layer_selected_ids(l)
            if len(selection) == 0:
                continue

            if len(selection) < 2:
                return

            # get centroids of each
            features = {}
            for i in selection:
                feature = get_feature_by_id(l, i)
                centroid = get_feature_centroid(feature)

                features[i] = centroid

            print features
            sorted_ids = sort_id_along_implicit_centroids_line(features)

            print sorted_ids
            wkt = centroids_to_line_wkt([features[i] for i in sorted_ids])

            print wkt

            feat = create_new_feature(layer, wkt, {'r': 1})
            insert_features_in_layer([feat], layer)


    #   - export volume to dxf
    def export_volume(self):
        pass
        # section_layers = []
        # for combo in self.viewer3d_combo:
        #    lid = combo.itemData(combo.currentIndex())
        #    section_layers += [QgsMapLayerRegistry.instance().mapLayer(lid)]
        # if len(section_layers) < 2:
        #    return
        # volumes, vertices = self.toolbar.build_volume(
        #    self.graphLayerHelper.active_layer(), section_layers)
        # drawing = dxf.drawing('/tmp/test.dxf')
        # for vol in volumes:
        #    for tri in vol:
        #        v = [ vertices[tri[i]] for i in range(0, 3) ]
        #        drawing.add(
        #            dxf.face3d(
        #                [tuple(v[0]), tuple(v[1]), tuple(v[2])], flags=1))
        # drawing.save()

    #   - reset subgraph. TODO: modify to clean active graph
    def __reset_subgraph_precondition_check(self):
        return False, "Nope"
        if self.subGraphLayerHelper.layer() is None:
            return (False, 'Missing subgraph')
        if not self.__section_main.section.is_valid:
            return (False, "No active section")
        return (True, "")

    def __reset_subgraph(self):
        # remove everything in subgraph for this section
        pass
        subgraph = self.subGraphLayerHelper.layer()
        projected_subgraph = filter(lambda l: (not isinstance(l, PolygonLayerProjection)), self.__section_main.section.projections_of(subgraph.id()))[0].projected_layer

        to_remove = []
        for segment in projected_subgraph.getFeatures():
            logging.debug('FOUND SEGMENT {}'.format(segment.id()))
            to_remove += [
                projected_feature_to_original(subgraph, segment).id()]

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

    def draw_active_section_3d(self):
        if self.__section_main.section.is_valid:
            # draw section line
            section_vertices = []
            for c in self.__section_main.section.line.coords:
                section_vertices += [[c[0], c[1], 250], [c[0], c[1], 500]]
            self.viewer3d.define_section_vertices(section_vertices)

    def build_volume(self, polygons):
        def same_vertex(v1, v2):
            return v1[0] == v2[0] and v1[1] == v2[1] and v1[2] == v2[2]

        def index_of(generatrice):
            for i in range(0, len(nodes)):
                if same_vertex(generatrice[0], nodes[i][0]) and \
                   same_vertex(generatrice[1], nodes[i][1]):
                    return i
            return -1

        nodes = []
        edges = []

        total = 0

        print 'Marche po ?? {}'.format(len(polygons))
        for polygon in polygons:
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

    def update_polygons_3d(self, section_layers, scale_z=1.0):
        graph_layer = self.toolbar.graphLayerHelper.active_layer()

        if graph_layer is None:
            return []

        def centroid(l):
            return [0.5*(l.coords[0][i]+l.coords[1][i]) for i in range(0, 3)]

        if True: # len(self.viewer3d.polygons_vertices) == 0:
            logging.info('Rebuild polygons!')
            self.polygons = []

            section_width = float(
                self.__section_main.toolbar.buffer_width.text())

            for layer in section_layers:
                if layer is not None:
                    v = compute_sections_polygons_from_graph(
                        graph_layer,
                        layer,
                        section_width)

                    self.viewer3d.set_section_polygons(
                        section_layers.index(layer), v)

                    self.polygons += v
                else:
                    self.viewer3d.set_section_polygons(
                        section_layers.index(layer), None)

        return self.polygons

    def display_polygons_volumes_3d_full(self, update_active_section_only=True):
        self.display_polygons_volumes_3d(False)

    def display_polygons_volumes_3d(self, update_active_section_only=True):
        logging.info('display_polygons_volumes_3d!!!')
        if self.initialize_3d_rendering():
            update_active_section_only = False

        section_layers = []
        for lid in self.toolbar.sections_layers_combo.active_layers_id():
            if lid is None:
                return
            section_layers += [get_layer_by_id(lid)]

        self.draw_active_section_3d()

        if not update_active_section_only:
            polygons = self.update_polygons_3d(section_layers)
            volumes, vertices = self.build_volume(polygons)

            self.viewer3d.updateVolume(vertices, volumes)
            self.viewer3d.updateGL()

        self.__redraw_3d_view()

    def initialize_3d_rendering(self):
        section_layers_id = \
            self.toolbar.sections_layers_combo.active_layers_id()
        if section_layers_id[0] == None:
            return

        if self.rendering_3d_intialized:
            return False

        ext = self.__iface.mapCanvas().extent()
        center = [ext.center().x(), ext.center().y(), ext.height()]
        self.viewer3d.enable(center)

        section_layers_id = \
            self.toolbar.sections_layers_combo.active_layers_id()
        self.rendering_3d_intialized = True

        # hmmmm
        layers_vertices = {}
        for layer in get_all_layers():
            # only draw projected layers
            if layer.customProperty('section_id') is not None:
                continue
            if layer.customProperty('graph'):
                continue
            if not layer.isSpatial():
                continue
            if QgsWKBTypes.geometryType(int(layer.wkbType())) != QgsWKBTypes.LineGeometry:
                continue
            if not isinstance(layer.rendererV2(), QgsSingleSymbolRendererV2):
                continue
            if get_id(layer) in section_layers_id:
                continue

            layer_vertices = []
            for feature in layer.getFeatures():
                wkt = feature.geometry().exportToWkt()
                if wkt.find('Z') < 0:
                    break
                v = loads(wkt.replace('Z', ' Z'))

                layer_vertices += [list(v.coords[0]), list(v.coords[1])]

            if len(layer_vertices) > 0:
                self.viewer3d.define_generatrices_vertices(get_id(layer), layer_vertices)
                self.viewer3d.set_generatrices_visibility(get_id(layer), self.__iface.legendInterface().isLayerVisible(
                            layer))
                self.viewer3d.set_generatrices_color(get_id(layer), list(layer.rendererV2().symbol().color().getRgbF()))

        self.display_polygons_volumes_3d(False)
        return True

    def initGui(self):
        self.__section_main = MainWindow(self.__iface, 'section')
        self.__dock = QDockWidget('Section')
        self.__dock.setWidget(self.__section_main)
        self.edit_graph_tool = GraphEditTool(self.__section_main.canvas)

        # Plugin-wide options
        self.toolbar = GlobalToolbar(self.__iface, self.__section_main)
        self.__export_volume_action = self.toolbar.addAction(icon('6_export_volume.svg'), 'Export volume (graph)')
        self.__iface.addToolBar(self.toolbar)

        # 3D viewer widget
        self.viewer3d = Viewer3D()
        self.viewer3d_dock = QDockWidget('3d View')
        self.viewer3d_window = QMainWindow(None)
        self.viewer3d_window.setWindowFlags(Qt.Widget)
        self.viewer3d_toolbar = QToolBar()
        self.viewer3d_window.addToolBar(Qt.TopToolBarArea,
                                        self.viewer3d_toolbar)
        self.viewer3d_window.setCentralWidget(self.viewer3d)
        self.viewer3d_dock.setWidget(self.viewer3d_window)
        self.viewer3d_scale_z = QLineEdit("3.0")
        self.viewer3d_scale_z.setMaximumWidth(50)
        self.viewer3d_toolbar.addWidget(self.viewer3d_scale_z)
        self.__iface.addDockWidget(Qt.BottomDockWidgetArea, self.viewer3d_dock)

        # Add buttons to section toolbar
        section_actions = self.__section_main.canvas.build_default_section_actions()
        section_actions += [
            None,
            { 'icon': icon('10_edit_graph.svg'), 'label': 'edit graph layer', 'tool': self.edit_graph_tool, 'precondition': lambda action: self.__toggle_edit_graph_precondition_check() },
            # { 'icon': icon('12_add_graph.svg'), 'label': 'create subgraph', 'clicked': self.__create_subgraph, 'precondition': lambda action: self.__create_subgraph_precondition_check() },
            { 'icon': icon('11_add_generatrices.svg'), 'label': 'add generatrices', 'clicked': self.__add_generatrices, 'precondition': lambda action: self.__add_generatrices_precondition_check() },
            { 'icon': icon('13_maj_graph.svg'), 'label': 'update graphs geom', 'clicked': self.__update_graphs_geometry, 'precondition': lambda action: self.__update_graphs_geometry_precondition_check() },
            None,
            { 'label': 'reset subgraph|gen.', 'clicked': self.__reset_subgraph, 'precondition': lambda action: self.__reset_subgraph_precondition_check() },

        ]
        self.generatrice_distance = QLineEdit("25")
        self.generatrice_distance.setMaximumWidth(50)
        self.__section_main.toolbar.addWidget(QLabel("Generatrice dist.:"))
        self.__section_main.toolbar.addWidget(self.generatrice_distance)
        self.__section_main.canvas.add_section_actions_to_toolbar(
            section_actions, self.__section_main.toolbar)
        self.__clean_graph_action = self.toolbar.addAction('Clean graph')
        self.__create_line_from_selection_action = self.toolbar.addAction(
            'Create line from selection')
        self.__iface.addDockWidget(Qt.BottomDockWidgetArea, self.__dock)

        # Signal connections
        self.__section_main.toolbar.line_clicked.\
            connect(self.edit_graph_tool._reset)
        self.__section_main.toolbar.line_clicked.\
            connect(self.display_polygons_volumes_3d)
        self.edit_graph_tool.graph_modified.\
            connect(self.__on_graph_modified)
        self.toolbar.graphLayerHelper.current_graph_layer_changed.\
            connect(self.__current_graph_layer_changed)
        root_layer_group_from_iface(self.__iface).visibilityChanged.\
            connect(self.__layer_visibility_changed)
        self.__clean_graph_action.triggered.\
            connect(self.cleanup_data)
        self.__export_volume_action.triggered.\
            connect(self.export_volume)
        self.viewer3d_scale_z.editingFinished.\
            connect(self.__redraw_3d_view)
        self.toolbar.sections_layers_combo.combo.currentIndexChanged.\
            connect(self.display_polygons_volumes_3d_full)
        self.__create_line_from_selection_action.triggered.\
            connect(self.__create_line_from_selection)

        QgsMapLayerRegistry.instance().layersAdded.connect(self.__layers_added)
        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect(self.__layers_will_be_removed)

        # In case we're reloading
        self.__layers_added(get_all_layers())

    def unload(self):
        self.__section_main.toolbar.line_clicked.disconnect(self.edit_graph_tool._reset)
        self.__section_main.toolbar.line_clicked.disconnect(self.display_polygons_volumes_3d)
        self.edit_graph_tool.graph_modified.disconnect(self.__on_graph_modified)
        self.toolbar.graphLayerHelper.current_graph_layer_changed.disconnect(self.__current_graph_layer_changed)
        root_layer_group_from_iface(self.__iface).visibilityChanged.disconnect(self.__layer_visibility_changed)
        self.__clean_graph_action.triggered.disconnect(self.cleanup_data)
        self.__export_volume_action.triggered.disconnect(self.export_volume)
        self.viewer3d_scale_z.editingFinished.disconnect(self.__redraw_3d_view)
        QgsMapLayerRegistry.instance().layersAdded.disconnect(self.__layers_added)
        QgsMapLayerRegistry.instance().layersWillBeRemoved.disconnect(self.__layers_will_be_removed)

        self.__dock.setWidget(None)
        self.__iface.removeDockWidget(self.__dock)
        self.__section_main.unload()
        self.toolbar.setParent(None)
        self.toolbar.cleanup()
        self.toolbar = None
        self.viewer3d_dock.setParent(None)
        self.__section_main = None

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
                layer_id, featA_id, featB_id = get_feature_attribute_values(
                    target, segment, 'layer', *attr)
                layer = get_layer_by_id(layer_id)
                featA = get_feature_by_id(layer, featA_id)
                featB = get_feature_by_id(layer, featB_id)
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
    #         my_id = f.attribute('link') if layer.projected_layer.fields().fieldNameIndex('link') >= 0 else f.attribute('link:Integer64(10,0)')
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
        if self.toolbar.graphLayerHelper.active_layer() is None:
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
        if self.toolbar.graphLayerHelper.active_layer() is None:
            return (False, "No graph layer")
        return (True, "")

    def __create_subgraph_precondition_check(self):
        return

        if not self.__section_main.section.is_valid:
            return (False, "No active section line")
        graph_layer = self.toolbar.graphLayerHelper.active_layer()
        if graph_layer is None:
            return (False, "No graph layer")
        if self.subGraphLayerHelper.layer() is None:
            return (False, "No subgraph layer")
        proj = self.__iface.mapCanvas().currentLayer()
        if proj is None:
            return (False, "No active layer")
        if proj.customProperty("section_id") != self.__section_main.section.id:
            return (False, "Active layer isn't a projection of section")

        projected_graph = filter(lambda l: (not isinstance(l, PolygonLayerProjection)), self.__section_main.section.projections_of(graph_layer.id()))[0]
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

            self.__add_generatrices_impl(self.toolbar.graphLayerHelper.active_layer())
        finally:
            self.__section_main.section.enable()
            #self.__section_main.section.update_projections(
            #    get_id(self.toolbar.graphLayerHelper.active_layer()))

            # layer = self.__iface.mapCanvas().currentLayer()
            # source_layer = projected_layer_to_original(layer)
            # self.__section_main.section.update_projections(source_layer.id())

            self.__on_graph_modified()

    def __add_generatrices_impl(self, graph):
        layer = self.__iface.mapCanvas().currentLayer()

        if layer is None or not self.__section_main.section.is_valid:
            return

        source_layer = projected_layer_to_original(layer)
        if source_layer is None:
            return

        missing_left, missing_right = \
            find_generatrices_needing_a_fake_generatrice_in_section(
                self.__section_main.section.line,
                graph,
                source_layer,
                layer)

        logging.info('MISSING {} {}'.format(missing_left, missing_right))

        if len(missing_left) is 0 and len(missing_right) is 0:
            return

        next_edge_link = (
            max_value(get_layer_unique_attribute(graph, 'link'), 0) + 1)

        next_generatrice_link = (
            max_value(get_layer_unique_attribute(source_layer, 'link'), 0) + 1)

        # Compute fake generatrice translation
        distance = float(self.generatrice_distance.text())
        a = unproject_point(self.__section_main.section.line, self.__section_main.section.z_scale, distance, 0, 0)
        b = unproject_point(self.__section_main.section.line, self.__section_main.section.z_scale, 0, 0, 0)
        translation_vec = tuple([a[i]-b[i] for i in range(0, 2)])

        graph.beginEditCommand('update edges')

        for feat_id in missing_left + missing_right:
            sides = []
            if feat_id in missing_left:
                sides += [-1]
            if feat_id in missing_right:
                sides += [+1]

            if len(sides) == 2:
                # this is a non-connected generatrices
                # only add fakes if selected
                if feat_id not in get_layer_selected_ids(source_layer):
                    continue

            # logging.info("CONSIDERING {} -> {}".format(feat_id, sides))
            feature = get_feature_by_id(source_layer, feat_id)

            for side in sides:
                generatrice = fg_create(
                    self.__section_main.section,
                    source_layer,
                    feature,
                    next_generatrice_link,
                    translation_vec,
                    side)

                # logging.info('INSERT')
                # Read back feature to get proper id()
                fake_feature = fg_insert(source_layer, generatrice)

                try:
                    # Add link in graph
                    fg_connect(graph,
                               feature,
                               fake_feature,
                               next_edge_link,
                               source_layer)
                except Exception as e:
                    logging.error(e)
                    # TODO: delete generatric

                next_generatrice_link = next_generatrice_link + 1
                next_edge_link = next_edge_link + 1

        graph.endEditCommand()
        logging.debug('End __add_generatrices_impl')
