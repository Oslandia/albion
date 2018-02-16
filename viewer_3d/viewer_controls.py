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
        self.__viewer.setTransparencyPercent(self.transparencySlider.value())

        menu = QMenu()
        for l, c, t in [
                ('labels', self.__viewer.toggle_labels, False),
                ('nodes', self.__viewer.toggle_nodes, True),
                ('edges', self.__viewer.toggle_edges, True),
                ('ends', self.__viewer.toggle_ends, True),
                ('volumes', self.__viewer.toggle_volumes, False),
                ('errors', self.__viewer.toggle_errors, False),
                ]:
            a = menu.addAction(l)
            a.setCheckable(True)
            a.triggered.connect(c)
            a.setChecked(t)
            c(t)

        self.layerButton.setMenu(menu)

        self.zScaleSlider.valueChanged.connect(self.__viewer.setZscale)
        self.transparencySlider.valueChanged.connect(self.__viewer.setTransparencyPercent)

        self.refreshButton.clicked.connect(self.__viewer.refresh_data)

        self.xyButton.clicked.connect(self.__viewer.set_xy_pov)

        self.deleteButton.setCheckable(True)
        self.addButton.setCheckable(True)
        self.deleteButton.clicked.connect(partial(self.addButton.setChecked, False))
        self.addButton.clicked.connect(partial(self.deleteButton.setChecked, False))
        self.deleteButton.clicked.connect(self.__viewer.set_delete_tool)
        self.addButton.clicked.connect(self.__viewer.set_add_tool)

        self.__iface = iface

