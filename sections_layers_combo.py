# coding=utf-8
from PyQt4.QtGui import (QPixmap,
                         QColor,
                         QIcon,
                         QComboBox)
from .qgis_hal import get_name


class SectionsLayersCombo():
    def __init__(self):
        self.combos = [QComboBox(), QComboBox()]
        for c in self.combos:
            c.addItem('-', None)
            c.setMinimumContentsLength(10)
            c.setSizeAdjustPolicy(QComboBox.AdjustToContents)

    def add_to_toolbar(self, toolbar):
        for c in self.combos:
            toolbar.addWidget(c)

    def update_layers(self, layers):
        self.graph_layers = []

        rpix = QPixmap(100, 100)
        rpix.fill(QColor("red"))
        bpix = QPixmap(100, 100)
        bpix.fill(QColor("blue"))

        red = QIcon(rpix)
        blue = QIcon(bpix)

        for combo in self.combos:
            combo.clear()
            for layer in layers:
                if layer.customProperty('section_id') is not None or \
                   layer.customProperty('graph'):
                    continue
                if not layer.isSpatial():
                    continue
                if get_name(layer).find('section') < 0:
                    continue

                combo.addItem(
                    red if self.combos.index(combo) == 0
                    else blue, layer.name(), layer.id())

    def active_layers_id(self):
        lid1 = self.combos[0].itemData(self.combos[0].currentIndex())
        lid2 = self.combos[1].itemData(self.combos[1].currentIndex())
        return lid1, lid2
