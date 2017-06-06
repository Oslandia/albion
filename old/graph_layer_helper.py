from PyQt4.QtCore import pyqtSignal, QObject
from PyQt4.QtGui import QComboBox
from qgis.core import QGis, QgsVectorLayer

from .qgis_hal import get_id, get_name, get_layer_by_id
from .utils import icon


def is_layer_taggable_as_graph(layer):
    if layer.customProperty('section_id') is not None:
        return False
    if get_name(layer).find('graph') < 0:
        return False
    if not isinstance(layer, QgsVectorLayer) or \
       not (layer.geometryType() == QGis.Line) or \
       layer.fieldNameIndex('start') == -1 or \
       layer.fieldNameIndex('end') == -1 or \
       layer.fieldNameIndex('layer') == -1:
        return False

    return True


class GraphLayerHelper(QObject):
    current_graph_layer_changed = pyqtSignal(QgsVectorLayer)

    def __init__(self):
        QObject.__init__(self)

    def add_to_toolbar(self, toolbar, iface):
        self.iface = iface
        self.iface.currentLayerChanged.connect(self.__update_state)

        # add combo box
        self.combo = QComboBox()
        self.combo.setMinimumContentsLength(10)
        toolbar.addWidget(self.combo)
        self.combo.currentIndexChanged.connect(self.__currentIndexChanged)
        # add tag action
        self.action = toolbar.addAction(icon('3_tag_layer_graph.svg'),
                                        'mark as graph')
        self.action.setCheckable(True)
        self.action.triggered.connect(self.__on_click)

    def update_layers(self, layers):
        self.combo.clear()

        for layer in layers:
            if layer.customProperty('graph') and \
               layer.customProperty('section_id') is None:
                self.combo.addItem(get_name(layer), get_id(layer))

    def active_layer(self):
        layer_id = self.combo.itemData(self.combo.currentIndex())
        return get_layer_by_id(layer_id)

    def __update_state(self, new_active_layer):
        if new_active_layer is None or \
           not is_layer_taggable_as_graph(new_active_layer):
            self.action.setChecked(False)
            self.action.setEnabled(False)
        else:
            self.action.setEnabled(True)
            self.action.setChecked(
                self.combo.findData(get_id(new_active_layer)) >= 0)

    def __tag_layer(self, layer):
        layer.setCustomProperty('graph', True)
        self.combo.addItem(get_name(layer), get_id(layer))

    def __untag_layer(self, layer):
        layer.setCustomProperty('graph', False)
        self.combo.removeItem(
            self.combo.findData(get_id(layer)))

    def __on_click(self):
        layer = self.iface.mapCanvas().currentLayer()

        if layer is None:
            self.__update_state(None)
        elif not self.action.isChecked():
            self.__untag_layer(layer)
        else:
            self.__tag_layer(layer)

        self.__update_state(layer)

    def __currentIndexChanged(self):
        self.current_graph_layer_changed.emit(self.active_layer())
