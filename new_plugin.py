# coding: utf-8

import sys
import logging
import traceback

from qgis.core import (QgsVectorLayer,
                       QgsLayerTreeLayer,
                       QgsMapLayerRegistry,
                       QgsPluginLayerRegistry, 
                       QgsProject)

from PyQt4.QtCore import (Qt, QObject)
from PyQt4.QtGui import (QMenu, 
                         QToolBar, 
                         QInputDialog, 
                         QLineEdit, 
                         QFileDialog, 
                         QProgressBar,
                         QApplication)

import psycopg2 

from .graph import to_volume

from .graph_operations import (
    refresh_graph_layer_edges,
    find_generatrices_needing_a_fake_generatrice_in_section,
    compute_section_polygons_from_graph,
    compute_segment_geometry,
    is_fake_feature,
    does_edge_already_exist)
from .section_projection import (project_layer_as_linestring,
                                 project_layer_as_polygon)

from .global_toolbar import GlobalToolbar

from .utils import (icon,
                    create_projected_layer,
                    sort_id_along_implicit_centroids_line,
                    centroids_to_line_wkt,
                    length)


from .axis_layer import AxisLayer, AxisLayerType
from .action_state_helper import ActionStateHelper

from pglite import start_cluster, stop_cluster, init_cluster, check_cluster, cluster_params
import atexit
import os
import time

from .load import load_file

AXIS_LAYER_TYPE = AxisLayerType()
QgsPluginLayerRegistry.instance().addPluginLayerType(AXIS_LAYER_TYPE)


@atexit.register
def unload_axi_layer_type():
    QgsPluginLayerRegistry.instance().removePluginLayerType(
        AxisLayer.LAYER_TYPE)

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

        if not check_cluster():
            init_cluster()
        start_cluster()

    def initGui(self):
        self.__menu = QMenu("Albion")
        self.__menu.addAction('New &Project').triggered.connect(self.__new_project)
        self.__menu.addSeparator()
        self.__menu.addAction('Refresh Grid Cells')
        self.__menu.addSeparator()
        self.__menu.addAction('&Import Data').triggered.connect(self.__import_data)
        self.__menu.addAction('Compute &Mineralization')
        self.__menu.addSeparator()
        self.__menu.addAction('New &Graph').triggered.connect(self.__new_graph)
        self.__menu.addAction('&Clean Graph')
        self.__menu.addSeparator()
        self.__menu.addAction('&Export Project')
        self.__menu.addAction('Import Project')
        
        self.__iface.mainWindow().menuBar().addMenu(self.__menu)

        self.__toolbar = QToolBar('Albion')
        self.__iface.mainWindow().addToolBar(self.__toolbar)


    def unload(self):
        self.__menu and self.__menu.setParent(None)
        self.__toolbar and self.__toolbar.setParent(None)
        stop_cluster()

    def __new_project(self):

        # @todo open dialog to configure project name and srid
        project_name, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Project name",
                 "Project name (no space, no caps, ascii only):", QLineEdit.Normal,
                 'test_project')
        if not ok:
            return

        srid, ok = QInputDialog.getText(self.__iface.mainWindow(),
                "Project SRID",
                 "Project SRID EPSG:", QLineEdit.Normal,
                 '32632')

        if not ok:
            return

        self.__iface.newProject()

        srid = int(srid)

        self.__iface.messageBar().pushInfo('Albion:', "creating project...")
       
        QgsProject.instance().writeEntry("albion", "project_name", project_name)
        QgsProject.instance().writeEntry("albion", "srid", srid)
        conn_info = "dbname={} {}".format(project_name, cluster_params())
        QgsProject.instance().writeEntry("albion", "conn_info", conn_info)

        con = psycopg2.connect("dbname=postgres {}".format(cluster_params()))
        cur = con.cursor()
        con.set_isolation_level(0)
        cur.execute("select pg_terminate_backend(pg_stat_activity.pid) \
                    from pg_stat_activity \
                    where pg_stat_activity.datname = '{}'".format(project_name))
        cur.execute("drop database if exists {}".format(project_name))
        cur.execute("create database {}".format(project_name))
        con.commit()
        con.close()
        con = psycopg2.connect(conn_info)
        cur = con.cursor()
        cur.execute("create extension postgis")
        cur.execute("create extension \"uuid-ossp\"")
        for file_ in ('_albion.sql', 'albion.sql'):
            for statement in open(os.path.join(os.path.dirname(__file__), file_)).read().split('\n;\n')[:-1]:
                print(statement)
                cur.execute(statement.format(srid=srid))
        cur.execute("insert into albion.metadata(srid, snap_distance) select 32632, 2")
        con.commit()
        con.close()

        for layer_name in ['cell', 'grid', 'hole', 
                'intersection_without_hole', 'collar', 'small_edge', 'close_point']:
            print('add layer', layer_name)
            self.__iface.addVectorLayer('{} srid={} key="id" table="albion"."{}" (geom)'.format(conn_info, srid, layer_name), layer_name, 'postgres')
            #QgsMapLayerRegistry.instance().addMapLayer(layer)

        self.__iface.actionSaveProject().trigger()

    def __new_graph(self):
        pass

    def __import_data(self):
        if not QgsProject.instance().readEntry("albion", "conn_info", "")[0]:
            return
        dir_ = QFileDialog.getExistingDirectory(None,
                        u"Data directory",
                        "" )
        if not dir_:
            return

        con = psycopg2.connect(QgsProject.instance().readEntry("albion", "conn_info", "")[0])
        cur = con.cursor()

        progressMessageBar = self.__iface.messageBar().createMessage("Loading {}...".format(dir_))
        progress = QProgressBar()
        progress.setMaximum(6)
        progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        progressMessageBar.layout().addWidget(progress)
        self.__iface.messageBar().pushWidget(progressMessageBar, self.__iface.messageBar().INFO)
        progress.setValue(0)
        for filename in os.listdir(dir_):
            if filename.find('collar') != -1:
                #self.__iface.messageBar().pushInfo('Albion:', "loading {}".format(os.path.join(dir_, filename)))
                load_file(cur, os.path.join(dir_, filename))
                progress.setValue(1)

        for filename in os.listdir(dir_):
            if filename.find('devia') != -1:
                #self.__iface.messageBar().pushInfo('Albion:', "loading {}".format(os.path.join(dir_, filename)))
                load_file(cur, os.path.join(dir_, filename))
                progress.setValue(2)

        cur.execute("select albion.update_hole_geom()")
        progress.setValue(3)

        for filename in os.listdir(dir_):
            if filename.find('formation') != -1 or filename.find('resi') != -1 or filename.find('avp') != -1:
                #self.__iface.messageBar().pushInfo('Albion:', "loading {}".format(os.path.join(dir_, filename)))
                load_file(cur, os.path.join(dir_, filename))
                progress.setValue(progress.value() + 1)
        progress.setValue(6)
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


    #def __toggle_axis(self):
    #    if self.__axis_layer:
    #        pass
    #        QgsMapLayerRegistry.instance().removeMapLayer(self.__axis_layer.id())
    #        self.__axis_layer = None
    #    else:
    #        self.__axis_layer = AxisLayer(self.__iface.mapCanvas().mapSettings().destinationCrs())
    #        QgsMapLayerRegistry.instance().addMapLayer(self.__axis_layer)

