# coding = utf-8

from qgis.core import *

from PyQt4.QtCore import QObject, Qt
from PyQt4.QtGui import QComboBox, \
        QShortcut, QKeySequence, QToolBar, QIcon, QMenu, QFileDialog, QInputDialog, \
        QLineEdit, QMessageBox, QProgressBar, QApplication

import psycopg2
import os

from .project import ProgressBar, Project
from .mineralization import MineralizationDialog

from .axis_layer import AxisLayer, AxisLayerType

import atexit

AXIS_LAYER_TYPE = AxisLayerType()
QgsPluginLayerRegistry.instance().addPluginLayerType(AXIS_LAYER_TYPE)
atexit.register(QgsPluginLayerRegistry.instance().removePluginLayerType, AxisLayer.LAYER_TYPE)

def resource(name):
    """Return name with prepended `res` directory
    """
    return os.path.join(os.path.dirname(__file__), 'res', name)

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

    def initGui(self):

        for keyseq, slot in (
                (Qt.CTRL + Qt.ALT + Qt.Key_K, self.__create_group),
                (Qt.CTRL + Qt.ALT + Qt.Key_S, self.__select_next_group),
                (Qt.CTRL + Qt.ALT + Qt.Key_N, self.__next_section),
                (Qt.CTRL + Qt.ALT + Qt.Key_B, self.__previous_section)
                ):

            short = QShortcut(QKeySequence(keyseq), self.__iface.mainWindow())
            short.setContext(Qt.ApplicationShortcut)
            short.activated.connect(slot)
            self.__shortcuts.append(short)


        self.__menu = QMenu("Albion")
        self.__menu.addAction('New &Project').triggered.connect(self.__new_project)
        self.__menu.addAction('Upgrade Project').triggered.connect(self.__upgrade_project)
        self.__menu.addAction('&Import Data').triggered.connect(self.__import_data)
        self.__menu.addAction('Compute &Mineralization').triggered.connect(self.__compute_mineralization)
        self.__menu.addSeparator()
        self.__menu.addAction('New &Graph').triggered.connect(self.__new_graph)
        self.__menu.addAction('Delete Graph').triggered.connect(self.__delete_graph)
        self.__menu.addSeparator()
        self.__menu.addAction('&Export Project')#.triggered.connect(self.__export_projecGt)
        self.__menu.addAction('Import Project')#.triggered.connect(self.__import_project)
        self.__menu.addAction('Export sections')#.triggered.connect(self.__export_sections)
        self.__menu.addAction('Export volume')#.triggered.connect(self.__export_volume)
        self.__menu.addSeparator()
        self.__menu.addAction('Create cells').triggered.connect(self.__create_cells)
        self.__menu.addAction('Create sections').triggered.connect(self.__create_sections)
        self.__menu.addAction('Auto graph')#.triggered.connect(self.__auto_graph)
        self.__menu.addAction('Create volumes')#.triggered.connect(self.__create_volumes)
        self.__menu.addSeparator()
        self.__menu.addAction('Toggle axis').triggered.connect(self.__toggle_axis)
        self.__iface.mainWindow().menuBar().addMenu(self.__menu)

        self.__toolbar = QToolBar('Albion')
        self.__iface.addToolBar(self.__toolbar)

        self.__toolbar.addWidget(self.__current_graph)
        #self.__current_graph.currentIndexChanged.connect(self.__current_graph_changed)

        self.__toolbar.addWidget(self.__current_section)
        self.__current_section.currentIndexChanged[unicode].connect(self.__current_section_changed)

        self.__toolbar.addAction(icon('previous_line.svg'), 'previous section').triggered.connect(self.__previous_section)

        self.__toolbar.addAction(icon('next_line.svg'), 'next section').triggered.connect(self.__next_section)
        
        QgsProject.instance().readProject.connect(self.__qgis__project__loaded)
        self.__qgis__project__loaded() # case of reload

    def unload(self):
        for s in self.__shortcuts:
            s.setParent(None)
        self.__toolbar and self.__toolbar.setParent(None)
        self.__menu and self.__menu.setParent(None)
        
    def __getattr__(self, name):
        if name == "project":
            project_name = QgsProject.instance().readEntry("albion", "project_name", "")[0]
            return Project(project_name) if project_name else None
        else:
            raise AttributeError(name)

    def __next_section(self):
        print "next"
        if self.project is None:
            return
        self.project.next_section(self.__current_section.currentText())
        self.__refresh_layers('section')

    def __previous_section(self):
        print "previous"
        if self.project is None:
            return
        self.project.previous_section(self.__current_section.currentText())
        self.__refresh_layers('section')

    def __refresh_layers(self, name=None):
        for layer in self.__iface.mapCanvas().layers():
            if name is None or layer.name().find(name) != -1:
                layer.triggerRepaint()

    def __current_section_changed(self, section_id):
        layers = QgsMapLayerRegistry.instance().mapLayersByName(u"group_cell")
        if len(layers):
            layers[0].setSubsetString("section_id='{}'".format(section_id))
        self.__refresh_layers('section')

    def __select_next_group(self):
        print "select next group"
        if self.project and self.__iface.activeLayer() and self.__iface.activeLayer().name() == u"cell":
            self.__iface.activeLayer().removeSelection()
            self.__iface.activeLayer().selectByExpression(
                    "id in ({})".format(",".join(project.next_group_ids())))

    def __create_group(self):
        print "create group"
        if self.project and self.__iface.activeLayer() and self.__iface.activeLayer().name() == u"cell":
            if self.__iface.activeLayer().selectedFeatureCount():
                print "we have a selection"
                section = self.__current_section.currentText()
                self.project.create_group(section, 
                        [f['id'] for f in self.__iface.activeLayer().selectedFeatures()])
            self.__iface.activeLayer().removeSelection()
            self.__refresh_layers('group_cell')

    def __qgis__project__loaded(self):
        if self.project is None:
            return
        self.__current_graph.clear()
        self.__current_section.clear()
        self.__current_section.addItems(self.project.sections())
        self.__current_graph.addItems(self.project.graphs())

        layers = QgsMapLayerRegistry.instance().mapLayersByName('section.anchor')
        if len(layers):
            layers[0].editingStopped.connect(self.__update_section_list)

        #self.__viewer3d.widget().resetScene(self.project, self.__current_graph.currentText())

    def __update_section_list(self):
        self.__current_section.clear()
        self.__current_section.addItems(self.project.sections())
                
    def __upgrade_project(self):
        project_name, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Database name", "Database name:", QLineEdit.Normal, '')
        if not ok:
            return
        Project(project_name).update()

    def __new_project(self):

        # @todo open dialog to configure project name and srid
        fil = QFileDialog.getSaveFileName(None,
                u"New project name (no space, plain ascii)",
                QgsProject.instance().readEntry("albion", "last_dir", "")[0],
                "QGIS poject file (*.qgs)")
        if not fil:
            return
        fil = fil if len(fil)>4 and fil[-4:]=='.qgs' else fil+'.qgs'
        fil = fil.replace(' ','_')
        try:
            fil.decode('ascii')
        except UnicodeDecodeError:
            self.__iface.messageBar().pushError('Albion:', "project name may only contain asci character (no accent)")
            return

        srid, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Project SRID", "Project SRID EPSG:", QLineEdit.Normal, '32632')
        if not ok:
            return
        srid = int(srid)

        project_name = str(os.path.split(fil)[1][:-4])

       
        if Project.exists(project_name):
            if QMessageBox.Yes != QMessageBox(QMessageBox.Information, 
                    "Delete existing DB", "Database {} exits, to you want to delete it ?".format(project_name), 
                    QMessageBox.Yes|QMessageBox.No).exec_():
                return
            Project.delete(project_name)


        self.__iface.messageBar().pushInfo('Albion:', "creating project...")
        Project.create(project_name, srid)

        # load template
        open(fil, 'w').write(
            open(resource('template_project.qgs')).read().replace('template_project', project_name))
        self.__iface.newProject()
        QgsProject.instance().setFileName(fil)
        QgsProject.instance().read()
        QgsProject.instance().writeEntry("albion", "project_name", project_name)
        QgsProject.instance().writeEntry("albion", "srid", srid)
        QgsProject.instance().write()
        self.__qgis__project__loaded()

    def __import_data(self):
        if self.project is None:
            return
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        dir_ = QFileDialog.getExistingDirectory(None,
                        u"Data directory",
                        QgsProject.instance().readEntry("albion", "last_dir", "")[0])
        if not dir_:
            return
        QgsProject.instance().writeEntry("albion", "last_dir", dir_),

        progressMessageBar = self.__iface.messageBar().createMessage("Loading {}...".format(dir_))
        progress = QProgressBar()
        progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        progressMessageBar.layout().addWidget(progress)
        self.__iface.messageBar().pushWidget(progressMessageBar, self.__iface.messageBar().INFO)
        
        self.project.import_data(dir_, ProgressBar(progress))
        self.project.triangulate()

        self.__iface.messageBar().clearWidgets()

        collar = QgsMapLayerRegistry.instance().mapLayersByName('collar')[0]
        collar.reload()
        collar.updateExtents()
        self.__iface.setActiveLayer(collar)
        QApplication.instance().processEvents()
        while self.__iface.mapCanvas().isDrawing():
            QApplication.instance().processEvents()
        self.__iface.zoomToActiveLayer()

        self.__iface.actionSaveProject().trigger()
    
    def __new_graph(self):

        if self.project is None:
            return

        graph, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Graph", "Graph name:", QLineEdit.Normal, 'test_graph')

        if not ok:
            return
        
        parent, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Parent Graph", "Parent Graph name:", QLineEdit.Normal, '')

        if not ok:
            return

        self.project.new_graph(graph, parent)
        self.__current_graph.addItem(graph)
        self.__current_graph.setCurrentIndex(self.__current_graph.findText(graph))


    def __delete_graph(self):
        if self.project is None:
            return

        graph, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Graph", "Graph name:", QLineEdit.Normal, self.__current_graph.currentText())

        if not ok:
            return

        self.__current_graph.removeItem(self.__current_graph.findText(graph))

    def __toggle_axis(self):
        if self.__axis_layer:
            pass
            QgsMapLayerRegistry.instance().removeMapLayer(self.__axis_layer.id())
            self.__axis_layer = None
        else:
            self.__axis_layer = AxisLayer(self.__iface.mapCanvas().mapSettings().destinationCrs())
            QgsMapLayerRegistry.instance().addMapLayer(self.__axis_layer)
        self.__refresh_layers()

    def __create_cells(self):
        if self.project is None:
            return
        self.project.triangulate()
        self.__refresh_layers('cells')

    def __create_sections(self):
        if self.project is None:
            return
        self.project.create_sections()

    def __compute_mineralization(self):
        MineralizationDialog(self.project).exec_()

