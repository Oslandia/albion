from qgis.core import *
from .main_window import MainWindow
from .axis_layer import AxisLayer, AxisLayerType

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QDockWidget, QAction


class Plugin():
    def __init__(self, iface):
        self.__iface = iface
        self.__sections = []
        self.axis_layer_type = AxisLayerType()
        QgsPluginLayerRegistry.instance().addPluginLayerType(self.axis_layer_type)

    def initGui(self):
        self.action = QAction('Add section', None)
        self.__iface.addToolBarIcon(self.action)
        self.action.triggered.connect(self._add_section)

        # Reload existing section
        self.__iface.layerTreeView().layerTreeModel().rootGroup().addedChildren.connect(self._legend_added_child)
        g = self.__iface.layerTreeView().layerTreeModel().rootGroup()
        self._legend_added_child(g, 0, len(g.children()))

    def unload(self):
        for section in self.__sections:
            self.__iface.removeDockWidget(section['dock'])
            section['main'].unload()

        self.action.triggered.disconnect()
        self.__iface.removeToolBarIcon(self.action)
        self.__sections = None
        QgsPluginLayerRegistry.instance().removePluginLayerType(AxisLayer.LAYER_TYPE)

    def _legend_added_child(self, node, f, to):
        new_children = node.children()[f:to+1]
        for node in new_children:
            if node.nodeType() == QgsLayerTreeNode.NodeGroup and node.customProperty('section_id'):
                id_ = node.customProperty('section_id')
                section = filter(lambda s: s['id'] == id_, self.__sections)

                if len(section) == 0:
                    self.add_section(id_)


    def _add_section(self):
        self.add_section('section{}'.format(len(self.__sections) + 1))

    def add_section(self, id_):
        main = MainWindow(self.__iface, id_)
        dock = QDockWidget(id_)
        dock.setWidget(main)
        main.add_default_section_buttons()
        self.__iface.addDockWidget(Qt.BottomDockWidgetArea, dock)

        self.__sections += [ { 'id': id_, 'main': main, 'dock': dock }]
