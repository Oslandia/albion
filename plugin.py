# coding: utf-8

from builtins import str
from qgis.core import *
from qgis.gui import *

from qgis.PyQt.QtCore import QObject, Qt, QFileInfo, QUrl
from qgis.PyQt.QtWidgets import QComboBox, QShortcut, QToolBar, QMenu, QFileDialog, QInputDialog, QLineEdit, QMessageBox, QProgressBar, QApplication, QDockWidget
from qgis.PyQt.QtGui import QKeySequence, QIcon, QDesktopServices

import psycopg2
import os
import zipfile
import tempfile

from .project import ProgressBar, Project, find_in_dir
from .mineralization import MineralizationDialog

from .axis_layer import AxisLayer, AxisLayerType
from .viewer_3d.viewer_3d import Viewer3d
from .viewer_3d.viewer_controls import ViewerControls
from .log_strati import BoreHoleWindow

from .export_elementary_volume import ExportElementaryVolume

from shapely.geometry import LineString
import numpy
import math

import atexit

AXIS_LAYER_TYPE = AxisLayerType()
QgsApplication.pluginLayerRegistry().addPluginLayerType(AXIS_LAYER_TYPE)
atexit.register(
    QgsApplication.pluginLayerRegistry().removePluginLayerType, AxisLayer.LAYER_TYPE
)


def resource(name):
    """Return name with prepended `res` directory
    """
    return os.path.join(os.path.dirname(__file__), "res", name)


def icon(name):
    """Return a QIcon instance from the `res` directory
    """
    return QIcon(resource(name))


class Plugin(QObject):
    def __init__(self, iface):
        QObject.__init__(self)
        self.__iface = iface
        self.__shortcuts = []
        self.__current_section = QComboBox()
        self.__current_section.setMinimumWidth(150)
        self.__current_graph = QComboBox()
        self.__current_graph.setMinimumWidth(150)
        self.__toolbar = None
        self.__axis_layer = None
        self.__menu = None
        self.__log_strati = None

    def initGui(self):

        for keyseq, slot in (
            (Qt.CTRL + Qt.ALT + Qt.Key_K, self.__create_group),
            (Qt.CTRL + Qt.ALT + Qt.Key_S, self.__select_next_group),
            (Qt.CTRL + Qt.ALT + Qt.Key_N, self.__next_section),
            (Qt.CTRL + Qt.ALT + Qt.Key_B, self.__previous_section),
        ):

            short = QShortcut(QKeySequence(keyseq), self.__iface.mainWindow())
            short.setContext(Qt.ApplicationShortcut)
            short.activated.connect(slot)
            self.__shortcuts.append(short)

        self.__menu = QMenu("Albion")
        self.__menu.aboutToShow.connect(self.__create_menu_entries)
        self.__iface.mainWindow().menuBar().addMenu(self.__menu)

        self.__toolbar = QToolBar("Albion")
        self.__iface.addToolBar(self.__toolbar)

        self.__toolbar.addAction(
            icon("log_strati.svg"), "stratigraphic log"
        ).triggered.connect(self.__log_strati_clicked)

        self.__toolbar.addWidget(self.__current_graph)
        self.__current_graph.currentIndexChanged[str].connect(
            self.__current_graph_changed
        )

        self.__toolbar.addWidget(self.__current_section)
        self.__current_section.currentIndexChanged[str].connect(
            self.__current_section_changed
        )

        self.__toolbar.addAction(
            icon("previous_line.svg"), "previous section  (Ctrl+Alt+b)"
        ).triggered.connect(self.__previous_section)

        self.__toolbar.addAction(
            icon("next_line.svg"), "next section (Ctrl+Alt+n)"
        ).triggered.connect(self.__next_section)

        self.__toolbar.addAction(
            icon("line_from_selected.svg"), "create temporary section"
        ).triggered.connect(self.__section_from_selection)

        self.__viewer3d = QDockWidget("3D")
        self.__viewer3d.setWidget(Viewer3d())
        self.__iface.addDockWidget(Qt.LeftDockWidgetArea, self.__viewer3d)
        self.__iface.mainWindow().tabifyDockWidget(
            self.__iface.mainWindow().findChild(QDockWidget, "Layers"), self.__viewer3d
        )

        self.__viewer3d_ctrl = QToolBar("3D controls")
        self.__viewer3d_ctrl.addWidget(ViewerControls(self.__viewer3d.widget()))
        self.__iface.addToolBar(self.__viewer3d_ctrl)

        QgsProject.instance().readProject.connect(self.__qgis__project__loaded)
        self.__qgis__project__loaded()  # case of reload

    def unload(self):
        for s in self.__shortcuts:
            s.setParent(None)
        self.__toolbar and self.__toolbar.setParent(None)
        self.__menu and self.__menu.setParent(None)
        self.__viewer3d and self.__viewer3d.setParent(None)
        self.__viewer3d_ctrl and self.__viewer3d_ctrl.setParent(None)

    def __add_menu_entry(self, name, callback, enabled=True, help_str=""):
        act = self.__menu.addAction(name)
        if callback is not None:
            act.triggered.connect(callback)
            act.setEnabled(enabled)
            act.setToolTip(help_str)
        else:
            act.setEnabled(False)
            act.setToolTip("NOT INMPLEMENTED " + help_str)
        return act

    def __create_menu_entries(self):
        self.__menu.clear()
        self.__add_menu_entry("New &Project", self.__new_project)
        self.__add_menu_entry("Import Project", self.__import_project)
        self.__add_menu_entry("Upgrade Project", self.__upgrade_project)

        self.__menu.addSeparator()

        self.__add_menu_entry(
            "&Import Data",
            self.__import_data,
            self.project is not None,
            "Import data from directory",
        )

        self.__add_menu_entry(
            "&Import selected layer",
            self.__import_layer,
            self.project is not None,
            "Import data from layer.",
        )


        self.__menu.addSeparator()

        self.__add_menu_entry(
            "Create cells",
            self.__create_cells,
            self.project is not None and self.project.has_collar,
            "Create Delaunay triangulation of collar layer.",
        )

        self.__add_menu_entry(
            "Refresh all edges",
            self.__refresh_all_edge,
            self.project is not None and self.project.has_cell,
            "Refresh materialized view of all cell edges used by graph possible edges.",
        )

        self.__add_menu_entry(
            "Refresh sections",
            self.__refresh_sections,
            self.project is not None,
            "Refresh materialized views (can take some time).",
        )

        self.__menu.addSeparator()

        # self.__add_menu_entry(u'Create section views 0° and 90°', self.__create_section_view_0_90,
        #        False and self.project is not None and self.project.has_hole,
        #        "Create section views (i.e. cut directions) to work West-East and South-North for this project")
        # self.__add_menu_entry(u'Create section views -45° and 45°', None,
        #        False and self.project is not None and self.project.has_hole,
        #        "Create section views (i.e. cut directions) to work SE-NW and SW-NE for this project")
        #
        # self.__menu.addSeparator()

        self.__add_menu_entry(
            "Create sections",
            self.__create_sections,
            self.project is not None and self.project.has_group_cell,
            "Once cell groups have been defined, create section lines.",
        )

        self.__menu.addSeparator()

        self.__add_menu_entry(
            "Compute &Mineralization",
            self.__compute_mineralization,
            self.project is not None and self.project.has_radiometry,
            "",
        )
        self.__menu.addSeparator()
        self.__add_menu_entry(
            "New &Graph",
            self.__new_graph,
            self.project is not None,
            "Create a new grap.h",
        )
        self.__add_menu_entry(
            "Delete Graph", self.__delete_graph, self.project is not None
        )
        self.__add_menu_entry(
            "Add selection to graph nodes", self.__add_selection_to_graph_node, self.project is not None
        )
        self.__add_menu_entry(
            "Accept graph possible edges", self.__accept_possible_edge, self.project is not None
        )
        self.__menu.addSeparator()
        self.__add_menu_entry(
            "Create volumes",
            self.__create_volumes,
            self.project is not None and bool(self.__current_graph.currentText()),
            "Create volumes associated with current graph.",
        )
        self.__menu.addSeparator()
        self.__add_menu_entry(
            "Create terminations",
            self.__create_terminations,
            self.project is not None and bool(self.__current_graph.currentText()),
            "Create terminations associated with current graph.",
        )
        self.__menu.addSeparator()
        self.__add_menu_entry("Toggle axis", self.__toggle_axis)

        self.__menu.addSeparator()

        self.__add_menu_entry(
            "Export Project", self.__export_project, self.project is not None
        )
        self.__add_menu_entry(
            "Export Sections",
            None,
            self.project is not None and self.project.has_section,
            "Export triangulated section in .obj or .dxf format",
        )
        self.__add_menu_entry(
            "Export Volume",
            self.__export_volume,
            self.project is not None and bool(self.__current_graph.currentText()),
            "Export volume of current graph in .obj or .dxf format",
        )

        self.__add_menu_entry(
            "Export Elementary Volume",
            self.__export_elementary_volume,
            self.project is not None and bool(self.__current_graph.currentText()),
            "Export an elementary volume of current graph in .obj or .dxf format",
        )

        self.__menu.addSeparator()

        self.__menu.addAction("Help").triggered.connect(self.open_help)

    def __current_graph_changed(self, graph_id):
        if self.project is None:
            return
        self.__viewer3d.widget().set_graph(graph_id)

    def __getattr__(self, name):
        if name == "project":
            project_name = QgsProject.instance().readEntry(
                "albion", "project_name", ""
            )[0]
            return Project(project_name) if project_name else None
        else:
            raise AttributeError(name)

    def __refresh_all_edge(self):
        if self.project is None:
            return
        self.project.refresh_all_edge()

    def __refresh_sections(self):
        if self.project:
            self.project.refresh_sections()

    def __create_terminations(self):
        if self.project is None:
            return
        self.project.create_terminations(self.__current_graph.currentText())
        self.__viewer3d.widget().refresh_data()
        self.__refresh_layers("section")

    def __create_volumes(self):
        if self.project is None:
            return
        self.project.create_volumes(self.__current_graph.currentText())
        self.__viewer3d.widget().refresh_data()

    def __next_section(self):
        if self.project is None:
            return
        self.project.next_section(self.__current_section.currentText())
        self.__refresh_layers("section")
        self.__viewer3d.widget().scene.update("section")
        self.__viewer3d.widget().update()

    def __previous_section(self):
        if self.project is None:
            return
        self.project.previous_section(self.__current_section.currentText())
        self.__refresh_layers("section")
        self.__viewer3d.widget().scene.update("section")
        self.__viewer3d.widget().update()

    def __refresh_layers(self, name=None, updateExtent=False):
        for layer in self.__iface.mapCanvas().layers():
            if name is None or layer.name().find(name) != -1:
                layer.triggerRepaint()

    def __layer(self, name):
        lay = None

        for layer in self.__iface.mapCanvas().layers():
            if name is None or layer.name() == name:
                lay = layer

        return lay

    def __current_section_changed(self, section_id):
        layers = QgsProject.instance().mapLayersByName(u"group_cell")
        if len(layers):
            layers[0].setSubsetString("section_id='{}'".format(section_id))
        self.__refresh_layers("section")

    def __select_next_group(self):
        if (
            self.project
            and self.__iface.activeLayer()
            and self.__iface.activeLayer().name() == u"cell"
        ):
            self.__iface.activeLayer().removeSelection()
            self.__iface.activeLayer().selectByExpression(
                "id in ({})".format(",".join(project.next_group_ids()))
            )

    def __create_group(self):
        if (
            self.project
            and self.__iface.activeLayer()
            and self.__iface.activeLayer().name() == u"cell"
        ):
            if self.__iface.activeLayer().selectedFeatureCount():
                section = self.__current_section.currentText()
                self.project.create_group(
                    section,
                    [f["id"] for f in self.__iface.activeLayer().selectedFeatures()],
                )
            self.__iface.activeLayer().removeSelection()
            self.__refresh_layers("group_cell")

    def __qgis__project__loaded(self):
        if self.project is None:
            return
        self.__current_graph.clear()
        self.__current_section.clear()
        self.__current_section.addItems(self.project.sections())
        self.__current_graph.addItems(self.project.graphs())

        layers = QgsProject.instance().mapLayersByName("section.anchor")
        if len(layers):
            layers[0].editingStopped.connect(self.__update_section_list)

        self.__viewer3d.widget().resetScene(self.project)

        # We make sure that corresponding extents are valid when the project
        # is loaded
        cell = QgsProject.instance().mapLayersByName("cell")[0]
        cell.updateExtents()

        section_geom = QgsProject.instance().mapLayersByName("section.geom")
        if section_geom:
            section_geom[0].updateExtents()

    def __update_section_list(self):
        self.__current_section.clear()
        self.__current_section.addItems(self.project.sections())

    def __upgrade_project(self):
        project_name, ok = QInputDialog.getText(
            self.__iface.mainWindow(),
            "Database name",
            "Database name:",
            QLineEdit.Normal,
            "",
        )
        if not ok:
            return
        project = Project(project_name)
        project.update()
        QgsProject.instance().writeEntry("albion", "project_name", project.name)
        QgsProject.instance().writeEntry("albion", "srid", project.srid)
        self.__qgis__project__loaded()


    def __new_project(self):

        # @todo open dialog to configure project name and srid
        fil, __ = QFileDialog.getSaveFileName(
            None,
            u"New project name (no space, plain ascii)",
            QgsProject.instance().readEntry("albion", "last_dir", "")[0],
            "QGIS poject file (*.qgs)",
        )
        if not fil:
            return
        fil = fil if len(fil) > 4 and fil[-4:] == ".qgs" else fil + ".qgs"
        fil = fil.replace(" ", "_")
        if len(fil) != len(fil.encode()):
            self.__iface.messageBar().pushError(
                "Albion:", "project name may only contain asci character (no accent)"
            )
            return

        srid, ok = QInputDialog.getText(
            self.__iface.mainWindow(),
            "Project SRID",
            "Project SRID EPSG:",
            QLineEdit.Normal,
            "32632",
        )
        if not ok:
            return
        srid = int(srid)

        project_name = str(os.path.split(fil)[1][:-4])

        if Project.exists(project_name):
            if (
                QMessageBox.Yes
                != QMessageBox(
                    QMessageBox.Information,
                    "Delete existing DB",
                    "Database {} exits, to you want to delete it ?".format(
                        project_name
                    ),
                    QMessageBox.Yes | QMessageBox.No,
                ).exec_()
            ):
                return
            Project.delete(project_name)

        self.__iface.messageBar().pushInfo("Albion:", "creating project...")
        Project.create(project_name, srid)

        # load template
        open(fil, "w").write(
            open(resource("template_project.qgs"))
            .read()
            .replace("template_project", project_name)
        )
        self.__iface.newProject()
        QgsProject.instance().setFileName(fil)
        QgsProject.instance().read()
        QgsProject.instance().writeEntry("albion", "project_name", project_name)
        QgsProject.instance().writeEntry("albion", "srid", srid)
        QgsProject.instance().write()
        self.__qgis__project__loaded()

    def __import_data(self):
        assert(self.project)
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        dir_ = QFileDialog.getExistingDirectory(
            None,
            u"Data directory",
            QgsProject.instance().readEntry("albion", "last_dir", "")[0],
            QFileDialog.ShowDirsOnly | QFileDialog.DontUseNativeDialog
        )
        if not dir_:
            return
        QgsProject.instance().writeEntry("albion", "last_dir", dir_),

        progressMessageBar = self.__iface.messageBar().createMessage(
            "Loading {}...".format(dir_)
        )
        progress = QProgressBar()
        progress.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        progressMessageBar.layout().addWidget(progress)
        self.__iface.messageBar().pushWidget(progressMessageBar)

        self.project.import_data(dir_, ProgressBar(progress))
        self.project.triangulate()
        self.project.create_section_view_0_90(4)

        self.__iface.messageBar().clearWidgets()

        collar = QgsProject.instance().mapLayersByName("collar")[0]
        collar.reload()
        collar.updateExtents()
        self.__iface.setActiveLayer(collar)
        QApplication.instance().processEvents()
        while self.__iface.mapCanvas().isDrawing():
            QApplication.instance().processEvents()
        self.__iface.zoomToActiveLayer()

        self.__iface.actionSaveProject().trigger()

        self.__viewer3d.widget().resetScene(self.project)
        self.__current_section.clear()
        self.__current_section.addItems(self.project.sections())

    def __import_layer(self):
        assert(self.project)
        if self.__iface.activeLayer():
            for f in self.__iface.activeLayer().fields():
                print(f)
            


    def __new_graph(self):

        graph, ok = QInputDialog.getText(
            self.__iface.mainWindow(),
            "Graph",
            "Graph name:",
            QLineEdit.Normal,
            "test_graph",
        )

        if not ok:
            return

        parent, ok = QInputDialog.getText(
            self.__iface.mainWindow(),
            "Parent Graph",
            "Parent Graph name:",
            QLineEdit.Normal,
            "",
        )

        if not ok:
            return

        self.project.new_graph(graph, parent)
        self.__current_graph.addItem(graph)
        self.__current_graph.setCurrentIndex(self.__current_graph.findText(graph))

    def __delete_graph(self):

        graph, ok = QInputDialog.getText(
            self.__iface.mainWindow(),
            "Graph",
            "Graph name:",
            QLineEdit.Normal,
            self.__current_graph.currentText(),
        )

        if not ok:
            return

        self.__current_graph.removeItem(self.__current_graph.findText(graph))

    def __add_selection_to_graph_node(self):
        #TODO ADD DIALOG TO REMIND USER THE CURRENT GRAPH

        if (
            self.__iface.activeLayer()
            and self.__iface.activeLayer().selectedFeatures()
        ):
            selection = self.__iface.activeLayer().selectedFeatures()
            graph = self.__current_graph.currentText()
            self.project.add_to_graph_node(graph, selection)

        self.__refresh_layers()

    def __accept_possible_edge(self):
        assert(false)
        #TODO

    def __toggle_axis(self):
        if self.__axis_layer:
            pass
            QgsProject.instance().removeMapLayer(self.__axis_layer.id())
            self.__axis_layer = None
        else:
            self.__axis_layer = AxisLayer(
                self.__iface.mapCanvas().mapSettings().destinationCrs()
            )
            QgsProject.instance().addMapLayer(self.__axis_layer)
        self.__refresh_layers()

    def __create_cells(self):
        if self.project is None:
            return
        self.project.triangulate()
        self.__refresh_layers("cells")

    def __create_sections(self):
        if self.project is None:
            return
        self.project.create_sections()

    def __compute_mineralization(self):
        MineralizationDialog(self.project).exec_()

    def __export_volume(self):
        if self.project is None:
            return

        fil, __ = QFileDialog.getSaveFileName(
            None,
            u"Export volume for current graph",
            QgsProject.instance().readEntry("albion", "last_dir", "")[0],
            "File formats (*.dxf *.obj)",
        )
        if not fil:
            return

        QgsProject.instance().writeEntry("albion", "last_dir", os.path.dirname(fil))

        if fil[-4:] == ".obj":
            self.project.export_obj(self.__current_graph.currentText(), fil)
        elif fil[-4:] == ".dxf":
            self.project.export_dxf(self.__current_graph.currentText(), fil)
        else:
            self.__iface.messageBar().pushWarning(
                "Albion", "unsupported extension for volume export"
            )

    def __export_elementary_volume(self):
        if self.project is None:
            return

        layer = self.__layer("cell")
        if not layer:
            return

        graph = self.__current_graph.currentText()
        export_widget = ExportElementaryVolume(layer, self.project, graph)
        export_widget.show()
        export_widget.exec_()

    def __import_project(self):
        fil, __ = QFileDialog.getOpenFileName(
            None,
            u"Import project from file",
            QgsProject.instance().readEntry("albion", "last_dir", "")[0],
            "File formats (*.zip)",
        )
        if not fil:
            return

        QgsProject.instance().writeEntry("albion", "last_dir", os.path.dirname(fil)),

        if fil[-4:] != ".zip":
            self.__iface.messageBar().pushWarning(
                "Albion", "unsupported extension for import"
            )

        project_name = os.path.split(fil)[1][:-4]
        dir_ = tempfile.mkdtemp()
        with zipfile.ZipFile(fil, "r") as z:
            z.extractall(dir_)

        dump = find_in_dir(dir_, ".dump")
        prj = find_in_dir(dir_, ".qgs")

        self.__iface.messageBar().pushInfo(
            "Albion", "loading {} from {}".format(project_name, dump)
        )

        dbname = os.path.splitext(os.path.basename(dump))[0]

        if Project.exists(dbname):
            if (
                QMessageBox.Yes
                != QMessageBox(
                    QMessageBox.Information,
                    "Delete existing DB",
                    "Database {} exits, to you want to delete it ?".format(
                        dbname
                    ),
                    QMessageBox.Yes | QMessageBox.No,
                ).exec_()
            ):
                return
            Project.delete(dbname)

        project = Project.import_(dbname, dump)

        QgsProject.instance().read(QFileInfo(prj))

    def __export_project(self):
        if self.project is None:
            return

        fil, __ = QFileDialog.getSaveFileName(
            None,
            u"Export project",
            QgsProject.instance().readEntry("albion", "last_dir", "")[0],
            "Data files(*.zip)",
        )
        if not fil:
            return

        QgsProject.instance().writeEntry("albion", "last_dir", os.path.dirname(fil)),

        if os.path.exists(fil):
            os.remove(fil)

        with zipfile.ZipFile(fil, "w") as project:
            dump = tempfile.mkstemp()[1]
            self.project.export(dump)
            project.write(dump, self.project.name + ".dump")
            project.write(
                QgsProject.instance().fileName(),
                os.path.split(QgsProject.instance().fileName())[1],
            )

    def __create_section_view_0_90(self):
        if self.project is None:
            return
        self.project.create_section_view_0_90()

    def __log_strati_clicked(self):
        # @todo switch behavior when in section view -> ortho
        self.__click_tool = QgsMapToolEmitPoint(self.__iface.mapCanvas())
        self.__iface.mapCanvas().setMapTool(self.__click_tool)
        self.__click_tool.canvasClicked.connect(self.__map_log_clicked)

    def __map_log_clicked(self, point, button):
        self.__click_tool.setParent(None)
        self.__click_tool = None

        if self.project is None:
            self.__log_strati and self.__log_strati.setParent(None)
            self.__log_strati = None
            return

        if self.__log_strati is None:
            self.__log_strati = QDockWidget("Stratigraphic Log")
            self.__log_strati.setWidget(BoreHoleWindow(self.project))
            self.__iface.addDockWidget(Qt.LeftDockWidgetArea, self.__log_strati)
            self.__iface.mainWindow().tabifyDockWidget(
                self.__iface.mainWindow().findChild(QDockWidget, "Layers"),
                self.__log_strati,
            )

        res = self.project.closest_hole_id(point.x(), point.y())
        if res:
            self.__log_strati.widget().scene.set_current_id(res)
            self.__log_strati.show()
            self.__log_strati.raise_()

    def __section_from_selection(self):
        if self.project is None:
            return

        if (
            self.__iface.activeLayer()
            and self.__iface.activeLayer().name() == u"collar"
            and self.__iface.activeLayer().selectedFeatures()
        ):
            collar = self.__iface.activeLayer()
            selection = collar.selectedFeatures()

            if len(selection) < 2:
                return

            def align(l):
                assert len(l) >= 2
                res = numpy.array(l[:2])
                for p in l[2:]:
                    u, v = res[0] - res[1], p - res[1]
                    if numpy.dot(u, v) < 0:
                        res[1] = p
                    elif numpy.dot(u, u) < numpy.dot(v, v):
                        res[0] = p
                # align with ref direction
                sqrt2 = math.sqrt(2.0) / 2
                l = l[numpy.argsort(numpy.dot(l - res[0], res[1] - res[0]))]
                d = numpy.array(l[-1] - l[0])
                dr = numpy.array([(0, 1), (sqrt2, sqrt2), (1, 0), (sqrt2, -sqrt2)])
                i = numpy.argmax(numpy.abs(dr.dot(d)))
                return l if (dr.dot(d))[i] > 0 else l[::-1]

            line = LineString(
                align(numpy.array([f.geometry().asPoint() for f in selection]))
            )
            collar.removeSelection()
            self.project.set_section_geom(self.__current_section.currentText(), line)
            self.__refresh_layers("section")
            self.__viewer3d.widget().scene.update("section")
            self.__viewer3d.widget().update()

    def open_help(self):
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                os.path.join(
                    os.path.dirname(__file__), "doc", "build", "html", "index.html"
                )
            )
        )
