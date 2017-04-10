# coding=utf-8
from PyQt4.QtCore import QObject
from PyQt4.QtGui import (QComboBox,
                         QInputDialog,
                         QFileDialog,
                         QMessageBox)
from .qgis_hal import (get_name,
                       create_memory_layer,
                       root_layer_group_from_iface)
from qgis.core import (QgsMapLayerRegistry,
                       QGis,
                       QgsLayerTree,
                       QgsVectorFileWriter,
                       QgsVectorLayer,
                       QgsWKBTypes,
                       QgsField)
from PyQt4.QtCore import QVariant
import os
import logging


class SectionsLayersCombo(QObject):
    def __init__(self, iface, parent=None):
        QObject.__init__(self, parent)

        self.iface = iface

        # combo selector
        self.combo = QComboBox()
        self.combo.addItem('-', None)
        self.combo.setMinimumContentsLength(10)
        self.combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)

    def __create_new_grid(self):
        s, ok = QInputDialog.getText(self.combo, 'Grid name',
                                     'Grid name')
        if ok and len(s) > 0:
            logging.info('self={}'.format(self))
            logging.info('self.iface={}'.format(self.iface))

            # ask folder
            folder = QFileDialog.getExistingDirectory(
                None,
                "Save grid layers to...")

            logging.info('FOLDER {}'.format(folder))
            if len(folder) == 0:
                return

            root = root_layer_group_from_iface(self.iface)
            grid = root.addGroup(
                s)
            grid.setCustomProperty('grid', True)

            crs = self.iface.mapCanvas().mapSettings().destinationCrs()

            # create 2 layers
            for i in [1, 2]:
                name = '{}_{}'.format(s, i)
                filename = os.path.join(folder, '{}.shp'.format(name))

                # create temp layer
                section = create_memory_layer(QGis.Line, crs, name)

                # warning: ogr layers with no attributes are considered
                # read-only by qgis
                section.dataProvider().addAttributes([QgsField('r', QVariant.Int)])
                section.updateFields()

                # write to disk
                encoding = u'UTF-8'
                cLayer = self.iface.mapCanvas().currentLayer()
                if cLayer:
                    encoding = cLayer.dataProvider().encoding()

                logging.info('WRITE {} with {}'.format(filename, encoding))
                QgsVectorFileWriter.writeAsVectorFormat(
                    section,
                    filename,
                    encoding,
                    crs,
                    overrideGeometryType=QgsWKBTypes.LineString,
                    includeZ=True)

                logging.info('SIGH')
                # open written layer
                vlayer = QgsVectorLayer(filename, name, 'ogr')
                logging.info(vlayer)
                if not vlayer:
                    QMessageBox.critical(
                        None, 'Error',
                        "Couldn't create '{}'".format(filename))
                else:
                    QgsMapLayerRegistry.instance().addMapLayer(vlayer, False)
                    grid.addLayer(vlayer)

    def add_to_toolbar(self, toolbar):
        toolbar.addAction('add_grid').triggered.connect(
                self.__create_new_grid)
        toolbar.addWidget(self.combo)

    def update_layers(self):
        self.combo.clear()
        self.combo.addItem('-', None)

        root = root_layer_group_from_iface(self.iface)
        for c in root.children():
            if QgsLayerTree.isGroup(c) and c.customProperty('grid'):
                self.combo.addItem(get_name(c), get_name(c))

    def active_layers_id(self):
        selected = self.combo.itemText(self.combo.currentIndex())

        root = root_layer_group_from_iface(self.iface)
        for c in root.children():
            if QgsLayerTree.isGroup(c) and get_name(c) == selected:
                result = c.findLayerIds()[0:2]
                return result

        return [None, None]
