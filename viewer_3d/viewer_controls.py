# coding=UTF-8
import os
#from qgis.core import *
#from qgis.gui import *
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
        self.__viewer.toggle_volumes(self.volumesCheckBox.isChecked())

        self.zScaleSlider.valueChanged.connect(self.__viewer.setZscale)

        self.labelsCheckBox.toggled.connect(self.__viewer.toggle_labels)
        self.nodesCheckBox.toggled.connect(self.__viewer.toggle_nodes)
        self.edgesCheckBox.toggled.connect(self.__viewer.toggle_edges)
        self.volumesCheckBox.toggled.connect(self.__viewer.toggle_volumes)
        self.errorCheckBox.toggled.connect(self.__viewer.toggle_errors)

        self.refreshButton.clicked.connect(self.__viewer.refresh_data)

        self.deleteButton.setCheckable(True)
        self.addButton.setCheckable(True)
        self.deleteButton.clicked.connect(partial(self.addButton.setChecked, False))
        self.addButton.clicked.connect(partial(self.deleteButton.setChecked, False))
        self.deleteButton.clicked.connect(self.__viewer.set_delete_tool)
        self.addButton.clicked.connect(self.__viewer.set_add_tool)

        self.__iface = iface

