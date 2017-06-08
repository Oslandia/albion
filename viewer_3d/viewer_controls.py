# coding=UTF-8
import os
from qgis.core import *
from qgis.gui import *
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import uic
from functools import partial

class ViewerControls(QWidget):
    def __init__(self, viewer, iface=None, parent=None):
        super(ViewerControls, self).__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'viewer_3d_controls.ui'), self)

        self.__viewer = viewer

        self.__viewer.setZscale(self.zScaleSlider.value())

        self.__viewer.toggle_labels(self.labelsCheckBox.isChecked())
        self.__viewer.toggle_nodes(self.nodesCheckBox.isChecked())
        self.__viewer.toggle_edges(self.edgesCheckBox.isChecked())
        self.__viewer.toggle_ceils(self.ceilsCheckBox.isChecked())
        self.__viewer.toggle_walls(self.wallsCheckBox.isChecked())
        self.__viewer.toggle_sections(self.sectionsCheckBox.isChecked())
        self.__viewer.toggle_volumes(self.volumesCheckBox.isChecked())

        self.zScaleSlider.valueChanged.connect(self.__viewer.setZscale)

        self.labelsCheckBox.toggled.connect(self.__viewer.toggle_labels)
        self.nodesCheckBox.toggled.connect(self.__viewer.toggle_nodes)
        self.edgesCheckBox.toggled.connect(self.__viewer.toggle_edges)
        self.ceilsCheckBox.toggled.connect(self.__viewer.toggle_ceils)
        self.wallsCheckBox.toggled.connect(self.__viewer.toggle_walls)
        self.sectionsCheckBox.toggled.connect(self.__viewer.toggle_sections)
        self.volumesCheckBox.toggled.connect(self.__viewer.toggle_volumes)

        self.refreshButton.clicked.connect(self.__viewer.refresh_data)

        self.__iface = iface


