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
        self.zScaleSlider.valueChanged.connect(self.__viewer.setZscale)
        self.labelsCheckBox.toggled.connect(self.__viewer.toggle_labels)
        self.holesCheckBox.toggled.connect(self.__viewer.toggle_holes)
        self.refreshButton.clicked.connect(self.__viewer.refresh_data)

        self.__iface = iface

