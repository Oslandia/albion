# coding: utf-8

import sys
import logging
import traceback
import codecs

from qgis.core import (QgsVectorLayer,
                       QgsLayerTreeLayer,
                       QgsMapLayerRegistry,
                       QgsPluginLayerRegistry, 
                       QgsProject,
                       QgsRectangle)

from qgis.gui import QgsMapToolEmitPoint

from PyQt4.QtCore import (Qt, QObject, QFileInfo)
from PyQt4.QtGui import (QMenu, 
                         QToolBar, 
                         QInputDialog, 
                         QLineEdit, 
                         QFileDialog, 
                         QProgressBar,
                         QComboBox,
                         QApplication,
                         QIcon,
                         QDockWidget,
                         QMessageBox)


import numpy
import psycopg2 
import tempfile
import zipfile
from subprocess import Popen, PIPE
from pglite import start_cluster, stop_cluster, init_cluster, check_cluster, cluster_params
import atexit
import os
import time
from dxfwrite import DXFEngine as dxf
from shapely import wkb
from shapely.geometry import LineString, Point
import math

from .axis_layer import AxisLayer, AxisLayerType
from .log_strati import BoreHoleWindow
from .viewer_3d.viewer_3d import Viewer3d
from .viewer_3d.viewer_controls import ViewerControls


AXIS_LAYER_TYPE = AxisLayerType()
QgsPluginLayerRegistry.instance().addPluginLayerType(AXIS_LAYER_TYPE)


@atexit.register
def unload_axi_layer_type():
    QgsPluginLayerRegistry.instance().removePluginLayerType(
        AxisLayer.LAYER_TYPE)

def icon(name):
    """Return a QIcon instance from the `res` directory
    """
    return QIcon(os.path.join(os.path.dirname(__file__), 'res', name))

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

class Plugin(QObject):
    def __init__(self, iface):
        QObject.__init__(self, None)
        FORMAT = '\033[30;100m%(created)-13s\033[0m \033[33m%(filename)-12s\033[0m:\033[34m%(lineno)4d\033[0m %(levelname)8s %(message)s' if sys.platform.find('linux')>= 0 else '%(created)13s %(filename)-12s:%(lineno)4d %(message)s'
        lvl = logging.INFO if sys.platform.find('linux')>= 0 else logging.CRITICAL
        logging.basicConfig(format=FORMAT, level=lvl)

        self.__iface = iface
        self.__project = None
        self.__menu = None
        self.__toolbar = None
        self.__click_tool = None
        self.__previous_tool = None
        self.__select_current_section_action = None
        self.__line_extend_action = None
        self.__current_graph = QComboBox()
        self.__current_graph.setMinimumWidth(150)
        self.__axis_layer = None
        self.__section_extent = (0, 1000)
        self.__log_strati = None

        if not check_cluster():
            init_cluster()
        start_cluster()

    def initGui(self):
        self.__menu = QMenu("Albion")
        self.__menu.addAction('New &Project').triggered.connect(self.__new_project)
        self.__menu.addAction('Upgrade Project').triggered.connect(self.__upgrade_project)
        self.__menu.addAction('&Import Data').triggered.connect(self.__import_data)
        self.__menu.addAction('Compute &Mineralization')
        self.__menu.addSeparator()
        self.__menu.addAction('New &Graph').triggered.connect(self.__new_graph)
        self.__menu.addAction('Delete Graph').triggered.connect(self.__delete_graph)
        self.__menu.addSeparator()
        self.__menu.addAction('&Export Project').triggered.connect(self.__export_project)
        self.__menu.addAction('Import Project').triggered.connect(self.__import_project)
        self.__menu.addAction('Export sections').triggered.connect(self.__export_sections)
        self.__menu.addAction('Export volume').triggered.connect(self.__export_volume)
        self.__menu.addSeparator()
        self.__menu.addAction('Create cells').triggered.connect(self.__create_cells)
        self.__menu.addAction('Auto graph').triggered.connect(self.__auto_graph)
        self.__menu.addAction('Extend sections').triggered.connect(self.__extend_all_sections)
        self.__menu.addAction('Triangulate sections').triggered.connect(self.__triangulate_sections)
        self.__menu.addAction('Create volumes').triggered.connect(self.__create_volumes)
        self.__menu.addSeparator()
        self.__menu.addAction('Toggle axis').triggered.connect(self.__toggle_axis)
        
        self.__iface.mainWindow().menuBar().addMenu(self.__menu)

        self.__toolbar = QToolBar('Albion')
        self.__iface.mainWindow().addToolBar(self.__toolbar)
        self.__select_current_section_action = self.__toolbar.addAction(icon('select_line.svg'), 'select section')
        self.__select_current_section_action.setCheckable(True)
        self.__select_current_section_action.triggered.connect(self.__select_current_section)

        self.__toolbar.addAction(icon('previous_line.svg'), 'previous section').triggered.connect(self.__select_previous_section)
        self.__toolbar.addAction(icon('next_line.svg'), 'next section').triggered.connect(self.__select_next_section)
        self.__toolbar.addWidget(self.__current_graph)
        self.__toolbar.addAction(icon('auto_connect.svg'), 'auto connect').triggered.connect(self.__auto_connect)
        self.__toolbar.addAction(icon('auto_top_bottom.svg'), 'auto top and bottom').triggered.connect(self.__auto_top_bottom)
        self.__toolbar.addAction(icon('extend_graph.svg'), 'extend to interpolated sections').triggered.connect(self.__extend_to_interpolated)
        self.__toolbar.addAction(icon('extremities_graph.svg'), 'extend with taper').triggered.connect(self.__create_ends)
        self.__toolbar.addAction(icon('triangulate.svg'), 'triangulate section').triggered.connect(self.__triangulate_section)
        self.__toolbar.addAction(icon('volume.svg'), 'create voluem').triggered.connect(self.__create_volume)
        self.__toolbar.addAction(icon('log_strati.svg'), 'stratigraphic log').triggered.connect(self.__log_strati_clicked)
        self.__toolbar.addAction(icon('line_from_selected.svg'), 'grid from selected collar').triggered.connect(self.__create_grid_from_selection)
        self.__line_extend_action = self.__toolbar.addAction(icon('line_extend.svg'), 'extend grid')
        self.__line_extend_action.setCheckable(True)
        self.__line_extend_action.triggered.connect(self.__extend_grid)

        self.__current_graph.currentIndexChanged.connect(self.__current_graph_changed)

        self.__viewer3d = QDockWidget('3D')
        self.__viewer3d.setWidget(Viewer3d())
        self.__iface.addDockWidget(Qt.LeftDockWidgetArea, self.__viewer3d)
        self.__iface.mainWindow().tabifyDockWidget(
                self.__iface.mainWindow().findChild(QDockWidget, "Layers"),
                self.__viewer3d)

        self.__viewer3d_ctrl = QDockWidget('3D controls')
        self.__viewer3d_ctrl.setWidget(ViewerControls(self.__viewer3d.widget()))
        self.__iface.addDockWidget(Qt.LeftDockWidgetArea, self.__viewer3d_ctrl)
        self.__iface.mainWindow().tabifyDockWidget(
                self.__iface.mainWindow().findChild(QDockWidget, "Layers"),
                self.__viewer3d_ctrl)
        
        QgsProject.instance().readProject.connect(self.__qgis__project__loaded)
        self.__qgis__project__loaded() # case of reload

    def unload(self):
        self.__menu and self.__menu.setParent(None)
        self.__toolbar and self.__toolbar.setParent(None)
        self.__viewer3d and self.__viewer3d.setParent(None)
        self.__viewer3d_ctrl and self.__viewer3d_ctrl.setParent(None)
        stop_cluster()
        QgsProject.instance().readProject.disconnect(self.__qgis__project__loaded)

    def __current_graph_changed(self, idx):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        if self.__current_graph.currentText():
            cur.execute("update albion.metadata set current_graph='{}'".format(self.__current_graph.currentText()))
        else:
            cur.execute("update albion.metadata set current_graph=null")
        con.commit()
        con.close()

        self.__viewer3d.widget().resetScene(conn_info, self.__current_graph.currentText())

    def __qgis__project__loaded(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        self.__current_graph.clear()
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("select id from albion.graph")
        self.__current_graph.addItems([id_ for id_, in cur.fetchall()])
        con.close()

        self.__viewer3d.widget().resetScene(conn_info, self.__current_graph.currentText())

    def __upgrade_project(self):
        project_name, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Database name",
                 "Database name:", QLineEdit.Normal,
                 '')

        if not ok:
            return

        conn_info = "dbname={} {}".format(project_name, cluster_params())
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("select srid from _albion.metadata")
        srid, = cur.fetchone()
        cur.execute("drop schema if exists albion cascade")
        for statement in open(os.path.join(os.path.dirname(__file__), 'albion.sql')).read().split('\n;\n')[:-1]:
            cur.execute(statement.replace('$SRID', str(srid)))
            #print statement.replace('$SRID', str(srid))
        con.commit()
        con.close()

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
                "Project SRID",
                 "Project SRID EPSG:", QLineEdit.Normal,
                 '32632')
        if not ok:
            return
        srid = int(srid)

        project_name = str(os.path.split(fil)[1][:-4])

        self.__iface.messageBar().pushInfo('Albion:', "creating project...")
       
        conn_info = "dbname={} {}".format(project_name, cluster_params())

        con = psycopg2.connect("dbname=postgres {}".format(cluster_params()))
        cur = con.cursor()
        con.set_isolation_level(0)
        cur.execute("select pg_terminate_backend(pg_stat_activity.pid) \
                    from pg_stat_activity \
                    where pg_stat_activity.datname = '{}'".format(project_name))
        
        cur.execute("select count(1) from pg_catalog.pg_database where datname='{}'".format(project_name))
        if cur.fetchone()[0]:
            if QMessageBox.Yes != QMessageBox(QMessageBox.Information, "Delete existing DB", "Database {} exits, to you want to delete it ?".format(project_name), QMessageBox.Yes|QMessageBox.No).exec_():
                con.close()
                return

        cur.execute("drop database if exists {}".format(project_name))
        cur.execute("create database {}".format(project_name))
        con.commit()
        con.close()
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("create extension postgis")
        cur.execute("create extension plpython3u")
        for file_ in ('_albion.sql', 'albion.sql'):
            for statement in open(os.path.join(os.path.dirname(__file__), file_)).read().split('\n;\n')[:-1]:
                cur.execute(statement.replace('$SRID', str(srid)))
        con.commit()
        con.close()

        # load template
        open(fil, 'w').write(
            open(os.path.join(os.path.dirname(__file__), 'template_project.qgs')).read().replace('template_project', project_name)
            )
        self.__iface.newProject()
        QgsProject.instance().setFileName(fil)
        QgsProject.instance().read()
        QgsProject.instance().writeEntry("albion", "project_name", project_name)
        QgsProject.instance().writeEntry("albion", "srid", srid)
        QgsProject.instance().writeEntry("albion", "conn_info", conn_info)
        QgsProject.instance().write()
        self.__qgis__project__loaded()

    def __new_graph(self):

        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return

        graph, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Graph",
                 "Graph name:", QLineEdit.Normal,
                 'test_graph')

        if not ok:
            return
        
        parent, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Parent Graph",
                 "Parent Graph name:", QLineEdit.Normal,
                 '')

        if not ok:
            return

        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        srid = QgsProject.instance().readEntry("albion", "srid", "")[0]

        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("delete from albion.graph cascade where id='{}';".format(graph))
        if parent:
            cur.execute("insert into albion.graph(id, parent) values ('{}', '{}');".format(graph, parent))
        else:
            cur.execute("insert into albion.graph(id) values ('{}');".format(graph))
        con.commit()
        con.close()

        self.__current_graph.addItem(graph)
        self.__current_graph.setCurrentIndex(self.__current_graph.findText(graph))

    def __delete_graph(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return

        graph, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Graph",
                 "Graph name:", QLineEdit.Normal,
                 '')

        if not ok:
            return

        for id_ in QgsMapLayerRegistry.instance().mapLayers():
            if id_.find(graph) != -1:
                QgsMapLayerRegistry.instance().removeMapLayer(id_)

        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        srid = QgsProject.instance().readEntry("albion", "srid", "")[0]

        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("delete from albion.graph casacde where id='{}';".format(graph))
        con.commit()
        con.close()
        self.__current_graph.removeItem(self.__current_graph.findText(graph))
        self.__refresh_layers()

    def __find_in_dir(self, dir_, name):
        for filename in os.listdir(dir_):
            if filename.find(name) != -1:
                return os.path.join(dir_, filename)
        return ""


    def __import_data(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        dir_ = QFileDialog.getExistingDirectory(None,
                        u"Data directory",
                        QgsProject.instance().readEntry("albion", "last_dir", "")[0])
        if not dir_:
            return
        QgsProject.instance().writeEntry("albion", "last_dir", dir_),

        #@todo run the collar import, and then subprocess the rest to allow the user
        #      to edit the grid without waiting

        con = psycopg2.connect(QgsProject.instance().readEntry("albion", "conn_info", "")[0])
        cur = con.cursor()

        progressMessageBar = self.__iface.messageBar().createMessage("Loading {}...".format(dir_))
        progress = QProgressBar()
        progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        progressMessageBar.layout().addWidget(progress)
        self.__iface.messageBar().pushWidget(progressMessageBar, self.__iface.messageBar().INFO)
        progress.setMaximum(17)

        progress.setValue(0)

        cur.execute("""
            copy _albion.collar(id, x, y, z, date_, comments) from '{}' delimiter ';' csv header 
            """.format(self.__find_in_dir(dir_, 'collar')))
        
        progress.setValue(1)
        
        cur.execute("""
            update _albion.collar set geom=format('SRID=32632;POINTZ(%s %s %s)', x, y, z)::geometry
            """)

        cur.execute("""
            insert into _albion.hole(id, collar_id) select id, id from _albion.collar;
            """)

        progress.setValue(2)

        cur.execute("""
            copy _albion.deviation(hole_id, from_, dip, azimuth) from '{}' delimiter ';' csv header
            """.format(self.__find_in_dir(dir_, 'devia')))

        progress.setValue(3)

        if self.__find_in_dir(dir_, 'avp'):
            cur.execute("""
                copy _albion.radiometry(hole_id, from_, to_, gamma) from '{}' delimiter ';' csv header
                """.format(self.__find_in_dir(dir_, 'avp')))

        progress.setValue(4)

        if self.__find_in_dir(dir_, 'formation'):
            cur.execute("""
                copy _albion.formation(hole_id, from_, to_, code, comments) from '{}' delimiter ';' csv header
                """.format(self.__find_in_dir(dir_, 'formation')))

        progress.setValue(5)

        if self.__find_in_dir(dir_, 'lithology'):
            cur.execute("""
                copy _albion.lithology(hole_id, from_, to_, code, comments) from '{}' delimiter ';' csv header
                """.format(self.__find_in_dir(dir_, 'lithology')))

        progress.setValue(6)

        if self.__find_in_dir(dir_, 'facies'):
            cur.execute("""
                copy _albion.facies(hole_id, from_, to_, code, comments) from '{}' delimiter ';' csv header
                """.format(self.__find_in_dir(dir_, 'facies')))

        progress.setValue(7)

        if self.__find_in_dir(dir_, 'resi'):
            cur.execute("""
                copy _albion.resistivity(hole_id, from_, to_, rho) from '{}' delimiter ';' csv header
                """.format(self.__find_in_dir(dir_, 'resi')))

        progress.setValue(8)

        if self.__find_in_dir(dir_, 'mineralization'):
            cur.execute("""
                copy _albion.mineralization(hole_id, from_, to_, oc, accu, grade, comments) from '{}' delimiter ';' csv header
                """.format(self.__find_in_dir(dir_, 'mineralization')))

        progress.setValue(9)


        cur.execute("""
            with dep as (
                select hole_id, max(to_) as mx
                    from (
                        select hole_id, max(to_) as to_ from _albion.radiometry group by hole_id
                        union all
                        select hole_id, max(to_) as to_ from _albion.resistivity group by hole_id
                        union all
                        select hole_id, max(to_) as to_ from _albion.formation group by hole_id
                        union all
                        select hole_id, max(to_) as to_ from _albion.lithology group by hole_id
                        union all
                        select hole_id, max(to_) as to_ from _albion.facies group by hole_id
                        union all
                        select hole_id, max(to_) as to_ from _albion.mineralization group by hole_id
                            ) as t
                group by hole_id
            )
            update _albion.hole as h set depth_=d.mx
            from dep as d where h.id=d.hole_id
            """)

        progress.setValue(10)

        cur.execute("update albion.hole set geom=albion.hole_geom(id)")

        progress.setValue(11)

        cur.execute("update albion.resistivity set geom=albion.hole_piece(from_, to_, hole_id)")

        progress.setValue(12)

        cur.execute("update albion.formation set geom=albion.hole_piece(from_, to_, hole_id)")

        progress.setValue(13)

        cur.execute("update albion.radiometry set geom=albion.hole_piece(from_, to_, hole_id)")

        progress.setValue(14)

        cur.execute("update albion.lithology set geom=albion.hole_piece(from_, to_, hole_id)")

        progress.setValue(15)

        cur.execute("update albion.facies set geom=albion.hole_piece(from_, to_, hole_id)")

        progress.setValue(16)

        cur.execute("update albion.mineralization set geom=albion.hole_piece(from_, to_, hole_id)")

        progress.setValue(17)


        self.__iface.messageBar().clearWidgets()

        con.commit()
        con.close()

        collar = QgsMapLayerRegistry.instance().mapLayersByName('collar')[0]
        collar.reload()
        collar.updateExtents()
        self.__iface.setActiveLayer(collar)
        QApplication.instance().processEvents()
        while self.__iface.mapCanvas().isDrawing():
            QApplication.instance().processEvents()
        self.__iface.zoomFull()


        self.__iface.actionSaveProject().trigger()

    def __log_strati_clicked(self):
        #@todo switch behavior when in section view -> ortho
        self.__click_tool = QgsMapToolEmitPoint(self.__iface.mapCanvas())
        self.__iface.mapCanvas().setMapTool(self.__click_tool)
        self.__click_tool.canvasClicked.connect(self.__map_log_clicked)
        self.__select_current_section_action.setChecked(True)

    def __map_log_clicked(self, point, button):
        self.__select_current_section_action.setChecked(False)
        self.__click_tool.setParent(None)
        self.__click_tool = None

        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            self.__log_strati and self.__log_strati.setParent(None)
            self.__log_strati = None
            return

        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        srid = QgsProject.instance().readEntry("albion", "srid", "")[0]

        if self.__log_strati is None:
            self.__log_strati = QDockWidget('Stratigraphic Log')
            self.__log_strati.setWidget(BoreHoleWindow(conn_info))
            self.__iface.addDockWidget(Qt.LeftDockWidgetArea, self.__log_strati)
            self.__iface.mainWindow().tabifyDockWidget(
                    self.__iface.mainWindow().findChild(QDockWidget, "Layers"),
                    self.__log_strati)

        con = psycopg2.connect(conn_info)
        cur = con.cursor()

        cur.execute("""
            select id from albion.hole
            where st_dwithin(geom, 'SRID={srid} ;POINT({x} {y})'::geometry, 25)
            order by st_distance('SRID={srid} ;POINT({x} {y})'::geometry, geom)
            limit 1""".format(srid=srid, x=point.x(), y=point.y()))
        res = cur.fetchone()
        if not res:
            cur.execute("""
                select id from albion.hole_section
                where st_dwithin(geom, 'SRID={srid} ;POINT({x} {y})'::geometry, 25)
                order by st_distance('SRID={srid} ;POINT({x} {y})'::geometry, geom)
                limit 1""".format(srid=srid, x=point.x(), y=point.y()))
            res = cur.fetchone()

        if res:
            self.__log_strati.widget().scene.set_current_id(res[0])
            self.__log_strati.show()
            self.__log_strati.raise_()

        con.close()

    def __select_current_section(self):
        #@todo switch behavior when in section view -> ortho
        self.__click_tool = QgsMapToolEmitPoint(self.__iface.mapCanvas())
        self.__iface.mapCanvas().setMapTool(self.__click_tool)
        self.__click_tool.canvasClicked.connect(self.__map_clicked)
        self.__select_current_section_action.setChecked(True)

    def __map_clicked(self, point, button):
        print(point, button)
        self.__select_current_section_action.setChecked(False)
        self.__click_tool.setParent(None)
        self.__click_tool = None

        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        srid = QgsProject.instance().readEntry("albion", "srid", "")[0]

        con = psycopg2.connect(conn_info)
        cur = con.cursor()

        cur.execute("""
            select id from albion.grid 
            where st_dwithin(geom, 'SRID={srid} ;POINT({x} {y})'::geometry, 25)
            order by st_distance('SRID={srid} ;POINT({x} {y})'::geometry, geom)
            limit 1""".format(srid=srid, x=point.x(), y=point.y()))
        res = cur.fetchone()
        if res:
            # click on map, set current section and set extend to matck visible extend on map
            cur.execute("update albion.metadata set current_section='{}'".format(res[0]))
            cur.execute("select st_extent(geom) from albion.collar_section")
            rect = cur.fetchone()
            top = float(rect[0].replace('BOX(','').split(',')[0].split()[1])
            ext = self.__iface.mapCanvas().extent()
            aspect_ratio = (ext.yMaximum()-ext.yMinimum())/(ext.xMaximum()-ext.xMinimum())
            cur.execute("""
                select st_linelocatepoint(albion.current_section_geom(), 'SRID={}; POINT({} {})'::geometry)*st_length(albion.current_section_geom()),
                       st_linelocatepoint(albion.current_section_geom(), 'SRID={}; POINT({} {})'::geometry)*st_length(albion.current_section_geom())
                """.format(srid, ext.xMinimum(), ext.yMinimum(), srid, ext.xMaximum(), ext.yMaximum()))
            xMin, xMax = cur.fetchone()
            
            self.__iface.mapCanvas().setExtent(QgsRectangle(xMin, top*1.1-(xMax-xMin)*aspect_ratio, xMax, top+1.1))
        else:
            # if click on section, set the current section to the ortogonal on passing through this point
            # maintain the position of the clicked point on screen and the zoom level
            cur.execute("""
                select id, st_linelocatepoint(geom,  albion.from_section('SRID={srid}; POINT({x} {y})'::geometry, albion.current_section_geom()))*st_length(geom)
                from albion.grid 
                where st_dwithin(geom, albion.from_section('SRID={srid} ;POINT({x} {y})'::geometry, albion.current_section_geom()), 25)
                and id!=albion.current_section_id()
                order by st_distance(albion.from_section('SRID={srid} ;POINT({x} {y})'::geometry, albion.current_section_geom()), geom)
                limit 1""".format(srid=srid, x=point.x(), y=point.y()))
            res = cur.fetchone()
            print "switch to section", res
            if res:
                print "swithc to section", res[0]
                ext = self.__iface.mapCanvas().extent()
                left = point.x()-ext.xMinimum()
                right = ext.xMaximum()-point.x()
                cur.execute("update albion.metadata set current_section='{}'".format(res[0]))
                # recompute extend
                self.__iface.mapCanvas().setExtent(QgsRectangle(
                    res[1]-left, 
                    ext.yMinimum(), 
                    res[1]+right, 
                    ext.yMaximum()))
                
        con.commit()
        con.close()
        self.__refresh_layers()
        self.__viewer3d.widget().update()

    def __select_next_section(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        srid = QgsProject.instance().readEntry("albion", "srid", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        ext = self.__iface.mapCanvas().extent()
        cur.execute("""
            select st_linelocatepoint(geom, st_centroid(albion.current_section_geom()))*st_length(geom),
                st_linelocatepoint(albion.current_section_geom(), st_centroid(albion.current_section_geom()))*st_length(albion.current_section_geom())
            from albion.grid
            where id=albion.next_section()
            """)
        res = cur.fetchone()
        if res:
            self.__iface.mapCanvas().setExtent(QgsRectangle(
                ext.xMinimum() + (res[0] - res[1]), 
                ext.yMinimum(), 
                ext.xMaximum() + (res[0] - res[1]), 
                ext.yMaximum()))
        
        cur.execute("""update albion.metadata set current_section=albion.next_section()""")

        con.commit()
        con.close()
        self.__refresh_layers()
        self.__viewer3d.widget().update()

    def __select_previous_section(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        ext = self.__iface.mapCanvas().extent()
        cur.execute("""
            select st_linelocatepoint(geom, st_centroid(albion.current_section_geom()))*st_length(geom),
                st_linelocatepoint(albion.current_section_geom(), st_centroid(albion.current_section_geom()))*st_length(albion.current_section_geom())
            from albion.grid
            where id=albion.previous_section()
            """)
        res = cur.fetchone()
        if res:
            self.__iface.mapCanvas().setExtent(QgsRectangle(
                ext.xMinimum() + (res[0] - res[1]), 
                ext.yMinimum(), 
                ext.xMaximum() + (res[0] - res[1]), 
                ext.yMaximum()))
        
        cur.execute("""update albion.metadata set current_section=albion.previous_section()""")
        con.commit()
        con.close()
        self.__refresh_layers()
        self.__viewer3d.widget().update()

    def __auto_connect(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("select parent from albion.graph where id='{}'".format(self.__current_graph.currentText()))
        parent, = cur.fetchone()
        if parent:
            cur.execute("""
                    select albion.auto_connect('{}', albion.current_section_id(), '{}')
                    """.format(self.__current_graph.currentText(), parent))
        else:
            cur.execute("""
                    select albion.auto_connect('{}', albion.current_section_id())
                    """.format(self.__current_graph.currentText()))
        con.commit()
        con.close()
        self.__refresh_layers()

    def __auto_top_bottom(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]\
                or not self.__current_graph.currentText():
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("""
                select albion.auto_top_and_bottom('{}', albion.current_section_id())
                """.format(self.__current_graph.currentText()))
        con.commit()
        con.close()
        self.__refresh_layers()

    def __export_sections(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return

        fil = QFileDialog.getSaveFileName(None,
                u"Export section",
                QgsProject.instance().readEntry("albion", "last_dir", "")[0],
                "Section files (*.obj *.dxf)")
        if not fil:
            return
        QgsProject.instance().writeEntry("albion", "last_dir", os.path.dirname(fil)),

        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()

        if fil[-4:] == '.dxf':
            cur.execute("""
                select st_collectionhomogenize(st_collect(triangulation)) 
                from albion.section 
                where graph_id='{}'
                """.format(self.__current_graph.currentText()))
            drawing = dxf.drawing(fil)
            m = wkb.loads(cur.fetchone()[0], True)
            for p in m:
                r = p.exterior.coords
                drawing.add(dxf.face3d([tuple(r[0]), tuple(r[1]), tuple(r[2])], flags=1))
            drawing.save()
        elif fil[-4:] == '.obj':
            cur.execute("""
                select albion.to_obj(st_collectionhomogenize(st_collect(triangulation))) 
                from albion.section 
                where graph_id='{}'
                """.format(self.__current_graph.currentText()))
            open(fil, 'w').write(cur.fetchone()[0])
        con.close()

    def __export_volume(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return

        fil = QFileDialog.getSaveFileName(None,
                u"Export volume",
                QgsProject.instance().readEntry("albion", "last_dir", "")[0],
                "Volume files(*.obj *.dxf)")
        if not fil:
            return
        QgsProject.instance().writeEntry("albion", "last_dir", os.path.dirname(fil)),


        if fil[-4:] in ['.obj', '.dxf']:
            conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
            con = psycopg2.connect(conn_info)
            cur = con.cursor()

            print 'extension', fil[-4:]
            if fil[-4:] == '.obj':
                cur.execute("""
                    select albion.to_obj(st_collectionhomogenize(st_collect(triangulation))) 
                    from albion.volume
                    where graph_id='{}'
                    """.format(self.__current_graph.currentText()))
                open(fil, 'w').write(cur.fetchone()[0])

            elif fil[-4:] == '.dxf':
                cur.execute("""
                    select st_collectionhomogenize(st_collect(triangulation))
                    from albion.volume
                    where graph_id='{}'
                    """.format(self.__current_graph.currentText()))
                drawing = dxf.drawing(fil)
                m = wkb.loads(cur.fetchone()[0], True)
                for p in m:
                    r = p.exterior.coords
                    drawing.add(dxf.face3d([tuple(r[0]), tuple(r[1]), tuple(r[2])], flags=1))
                drawing.save()

            con.commit()
            con.close()
        else:
            self.__iface.messageBar().pushWarning('Albion', 'unsupported extension for volume export')


    def __auto_graph(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("select albion.auto_graph('{}')".format(self.__current_graph.currentText()))
        con.commit()
        con.close()
        self.__refresh_layers()

    def __extend_all_sections(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("select albion.extend_to_interpolated('{}', id) from albion.grid".format(self.__current_graph.currentText()))
        con.commit()
        con.close()
        self.__refresh_layers()

    def __extend_to_interpolated(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("select albion.extend_to_interpolated('{}', albion.current_section_id())".format(self.__current_graph.currentText()))
        con.commit()
        con.close()
        self.__refresh_layers()

    def __create_ends(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("select albion.create_ends('{}', albion.current_section_id())".format(self.__current_graph.currentText()))
        con.commit()
        con.close()
        self.__refresh_layers()

    def __refresh_layers(self):
        for layer in self.__iface.mapCanvas().layers():
            layer.triggerRepaint()
        

    def __toggle_axis(self):
        if self.__axis_layer:
            pass
            QgsMapLayerRegistry.instance().removeMapLayer(self.__axis_layer.id())
            self.__axis_layer = None
        else:
            self.__axis_layer = AxisLayer(self.__iface.mapCanvas().mapSettings().destinationCrs())
            QgsMapLayerRegistry.instance().addMapLayer(self.__axis_layer)


    def __export_project(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return

        fil = QFileDialog.getSaveFileName(None,
                u"Export project",
                QgsProject.instance().readEntry("albion", "last_dir", "")[0],
                "Data files(*.zip)")
        if not fil:
            return
        QgsProject.instance().writeEntry("albion", "last_dir", os.path.dirname(fil)),

        if os.path.exists(fil):
            os.remove(fil)
        with zipfile.ZipFile(fil, 'w') as project:
            conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
            param = dict([p.split('=') for p in conn_info.split()])
        
            dump = tempfile.mkstemp()[1]
            cmd = ['pg_dump', '-h', param['host'], '-p', param['port'], '-d', param['dbname']]
            print ' '.join(cmd)
            p = Popen(cmd, stdout=open(dump,'w'), stdin=PIPE, stderr=PIPE).communicate()
            project.write(dump, param['dbname']+'.dump')
            project.write(QgsProject.instance().fileName())
            
    def __import_project(self):
        fil = QFileDialog.getOpenFileName(None,
                u"Import project",
                QgsProject.instance().readEntry("albion", "last_dir", "")[0],
                "Data files(*.zip)")
        if not fil:
            return
        QgsProject.instance().writeEntry("albion", "last_dir", os.path.dirname(fil)),
        dir_ = tempfile.mkdtemp()
        with zipfile.ZipFile(fil, "r") as z:
            z.extractall(dir_)
            
        dump = self.__find_in_dir(dir_, '.dump')
        project_name = os.path.split(dump)[1][:-5]

        con = psycopg2.connect("dbname=postgres {}".format(cluster_params()))
        cur = con.cursor()
        con.set_isolation_level(0)
        cur.execute("select pg_terminate_backend(pg_stat_activity.pid) \
                    from pg_stat_activity \
                    where pg_stat_activity.datname = '{}'".format(project_name))
        cur.execute("drop database if exists {}".format(project_name))
        con.commit()
        con.close()

        param = dict([p.split('=') for p in cluster_params().split()])
        cmd = ['createdb', '-h', param['host'], '-p', param['port'], '-d', project_name]
        print ' '.join(cmd)
        p = Popen(cmd ).communicate()
        cmd = ['psql', '-h', param['host'], '-p', param['port'], '-d', project_name, '-f', dump]
        print ' '.join(cmd)
        p = Popen(cmd ).communicate()

        QgsProject.instance().read(QFileInfo(self.__find_in_dir(dir_, '.qgs')))


    def __triangulate_sections(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("""
            delete from albion.section 
            where graph_id=albion.current_graph() """)
        cur.execute("""
            insert into albion.section(id, triangulation, graph_id, grid_id)
            select 
                _albion.unique_id()::varchar,
                st_collectionhomogenize(st_collect(albion.triangulate_edge(top, bottom))),
                graph_id, grid_id
            from albion.edge
            where graph_id=albion.current_graph()
            group by graph_id, grid_id
            """.format(self.__current_graph.currentText()))
        con.commit()
        con.close()
        self.__viewer3d.widget().refresh_data()

    def __triangulate_section(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("""
            delete from albion.section 
            where graph_id=albion.current_graph()
            and grid_id=albion.current_section_id()""")
        cur.execute("""
            insert into albion.section(id, triangulation, graph_id, grid_id)
            select 
                _albion.unique_id()::varchar,
                st_collectionhomogenize(st_collect(albion.triangulate_edge(top, bottom))),
                graph_id, grid_id
            from albion.edge
            where graph_id=albion.current_graph()
            and grid_id=albion.current_section_id()
            group by graph_id, grid_id
            """.format(self.__current_graph.currentText()))
        con.commit()
        con.close()
        self.__viewer3d.widget().refresh_data()

    def __create_volumes(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0] \
                or not self.__current_graph.currentText():
            return
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("""
            delete from albion.volume 
            where graph_id=albion.current_graph()""")
        cur.execute("select id from albion.cell")
        ids = [cid for cid, in cur.fetchall()]
        progressMessageBar = self.__iface.messageBar().createMessage("Creating volumes...")
        progress = QProgressBar()
        progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        progressMessageBar.layout().addWidget(progress)
        self.__iface.messageBar().pushWidget(progressMessageBar, self.__iface.messageBar().INFO)
        progress.setMaximum(len(ids))

        progress.setValue(0)

        for ids_ in chunks(ids, 10):
            cur.execute("""
                with mesh as (
                    select albion.elementary_volume(albion.current_graph(), id) as geom,
                    albion.current_graph() as graph_id, id as cell_id
                    from albion.cell
                    where id in ({})
                )
                insert into albion.volume(id, triangulation, graph_id, cell_id)
                select 
                _albion.unique_id()::varchar, geom, graph_id, cell_id
                from mesh
                where geom is not null
                """.format(','.join(["'"+str(id_)+"'" for id_ in ids_])))
            progress.setValue(progress.value()+10)

        self.__iface.messageBar().clearWidgets()

        cur.execute("""
            with p as (
                select albion.close_volume(albion.current_graph()) as geom
            )
            insert into albion.volume(id, triangulation, graph_id)
            select 
            _albion.unique_id()::varchar, geom, albion.current_graph()
            from p
            where not st_isempty(geom)
            """)

        cur.execute("""
            with p as (
                select albion.isolated_node_volume(albion.current_graph()) as geom
            )
            insert into albion.volume(id, triangulation, graph_id)
            select 
            _albion.unique_id()::varchar, geom, albion.current_graph()
            from p 
            where not st_isempty(geom)
            """)

        con.commit()
        con.close()
        self.__viewer3d.widget().refresh_data()
        self.__refresh_layers()

    def __create_volume(self):
        self.__click_tool = QgsMapToolEmitPoint(self.__iface.mapCanvas())
        self.__iface.mapCanvas().setMapTool(self.__click_tool)
        self.__click_tool.canvasClicked.connect(self.__create_volume_clicked)
        self.__select_current_section_action.setChecked(True)

    def __create_volume_clicked(self, point, button):
        self.__select_current_section_action.setChecked(False)
        self.__click_tool.setParent(None)
        self.__click_tool = None

        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        srid = QgsProject.instance().readEntry("albion", "srid", "")[0]

        con = psycopg2.connect(conn_info)
        cur = con.cursor()

        cur.execute("""
            select id from albion.cell 
            where st_intersects(geom, 'SRID={srid} ;POINT({x} {y})'::geometry)
            limit 1""".format(srid=srid, x=point.x(), y=point.y()))
        res = cur.fetchone()
        if res:
            cur.execute("""
                delete from albion.volume 
                where graph_id=albion.current_graph() 
                and cell_id='{}'""".format(res[0]))
            cur.execute("""
                with mesh as (
                    select albion.elementary_volume(albion.current_graph(), '{cell_id}') as geom
                )
                insert into albion.volume(id, triangulation, graph_id, cell_id)
                select _albion.unique_id()::varchar, geom, albion.current_graph(), '{cell_id}'
                from mesh
                where geom is not null""".format(cell_id=res[0]))

        con.commit()
        con.close()
        self.__viewer3d.widget().refresh_data()
        self.__refresh_layers()

    def __create_cells(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        srid = QgsProject.instance().readEntry("albion", "srid", "")[0]

        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("select albion.refresh_cell()")
        con.commit()
        con.close()

        self.__refresh_layers()



    def __create_grid_from_selection(self):

        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return

        collar = QgsMapLayerRegistry.instance().mapLayersByName('collar')
        if not len(collar):
            return
        selection = collar[0].selectedFeatures()

        if len(selection) < 2:
            return

        def align(l):
            assert len(l) >= 2
            res = numpy.array(l[:2])
            for p in l[2:]:
                u, v = res[0] - res[1], p - res[1]
                if numpy.dot(u,v) < 0:
                    res[1] = p
                elif numpy.dot(u, u) < numpy.dot(v,v):
                    res[0] = p
            # align with ref direction
            sqrt2 = math.sqrt(2.)/2
            l =  l[numpy.argsort(numpy.dot(l-res[0], res[1]-res[0]))]
            d = numpy.array(l[-1] - l[0])
            dr = numpy.array([(0,1),(sqrt2, sqrt2),(1,0), (sqrt2, -sqrt2)])
            i = numpy.argmax(numpy.abs(dr.dot(d)))
            return l if (dr.dot(d))[i] > 0 else l[::-1]

        line = LineString(align(numpy.array([f.geometry().asPoint() for f in selection])))
        collar[0].removeSelection()

        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        srid = QgsProject.instance().readEntry("albion", "srid", "")[0]

        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("""
            insert into albion.grid(geom) values(st_setsrid('{}'::geometry, {}))
            """.format(line.wkb_hex, srid))
        con.commit()
        con.close()

        self.__refresh_layers()

    def __extend_grid(self):
        self.__click_tool = QgsMapToolEmitPoint(self.__iface.mapCanvas())
        self.__iface.mapCanvas().setMapTool(self.__click_tool)
        self.__click_tool.canvasClicked.connect(self.__extend_grid_clicked)
        self.__line_extend_action.setChecked(True)

    def __extend_grid_clicked(self, point, button):
        self.__click_tool.setParent(None)
        self.__click_tool = None
        self.__line_extend_action.setChecked(False)

        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        
        conn_info = QgsProject.instance().readEntry("albion", "conn_info", "")[0]
        srid = QgsProject.instance().readEntry("albion", "srid", "")[0]

        con = psycopg2.connect(conn_info)
        cur = con.cursor()

        cur.execute("""
            select id, geom, st_linelocatepoint(geom, 'SRID={srid} ;POINT({x} {y})'::geometry) 
            from albion.grid 
            where st_dwithin(geom, 'SRID={srid} ;POINT({x} {y})'::geometry, 50)
            order by st_distance(geom, 'SRID={srid} ;POINT({x} {y})'::geometry)
            limit 1""".format(srid=srid, x=point.x(), y=point.y()))
        res = cur.fetchone()
        if res:
            lid = res[0]
            line = wkb.loads(res[1], True)
            alpha = res[2]
            coords = numpy.array(line.coords)
            print alpha
            ext = LineString([coords[0], coords[0]-3*(coords[1]-coords[0])]) \
                  if alpha < .5 else \
                  LineString([coords[-1], coords[-1]+3*(coords[-1]-coords[-2])])

            cur.execute("""
                with intersected as (
                    select id, geom, st_intersection(geom, st_setsrid('{line}'::geometry, {srid})) as inter
                    from albion.grid
                    where st_intersects(geom, st_setsrid('{line}'::geometry, {srid}))
                    and st_geometrytype(st_intersection(geom, st_setsrid('{line}'::geometry, {srid}))) = 'ST_Point'
                )
                select id, inter
                from intersected
                where  st_linelocatepoint(st_setsrid('{line}'::geometry, {srid}), inter) > 1e-6
                order by st_linelocatepoint(st_setsrid('{line}'::geometry, {srid}), inter) asc
                limit 1
                """.format(srid=srid, line=ext.wkb_hex))
            res = cur.fetchone()
            if res:
                cur.execute("""
                    update albion.grid set geom=st_snap(geom, '{}'::geometry, albion.precision())
                    where id='{}'
                    """.format(res[1], res[0]))
                pt = wkb.loads(res[1], True)
                line = LineString(list(pt.coords)+list(line.coords)) \
                    if alpha < .5 else LineString(list(line.coords)+list(pt.coords))
            else:
                line =  LineString([coords[0]-(coords[1]-coords[0])]+list(line.coords)) \
                    if alpha < .5 else LineString(list(line.coords)+[coords[-1]+(coords[-1]-coords[-2])])

            cur.execute("""
                update albion.grid set geom=st_setsrid('{line}'::geometry, {srid})
                where id='{lid}'
                """.format(line=line.wkb_hex, srid=srid, lid=lid))
                    

        con.commit()
        con.close()
        self.__viewer3d.widget().refresh_data()
        self.__refresh_layers()

