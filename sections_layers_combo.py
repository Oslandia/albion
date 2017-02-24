# coding=utf-8
from PyQt4.QtCore import QObject
from PyQt4.QtGui import (QPixmap,
                         QColor,
                         QIcon,
                         QComboBox)
from .qgis_hal import get_name


class SectionsLayersCombo(QObject):
    def __init__(self, parent):
        QObject.__init__(self, parent)
        self.combos = [QComboBox(), QComboBox()]
        for c in self.combos:
            c.addItem('-', None)
            c.setMinimumContentsLength(10)
            c.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            c.currentIndexChanged.connect(self._oneComboIndexChanged)

    def _oneComboIndexChanged(self, index):
        if index == -1:
            return

        source = self.sender()
        other = self.combos[0] if source is self.combos[1] else self.combos[1]
        # make sure the other combo points to another layer
        if other.currentIndex() == index:
            count = other.count()
            if count <= 1:
                other.setCurrentIndex(-1)
            else:
                other.setCurrentIndex((index + 1) % count)

    def add_to_toolbar(self, toolbar):
        for c in self.combos:
            toolbar.addWidget(c)

    def update_layers(self, layers):
        rpix = QPixmap(100, 100)
        rpix.fill(QColor("red"))
        bpix = QPixmap(100, 100)
        bpix.fill(QColor("blue"))

        red = QIcon(rpix)
        blue = QIcon(bpix)

        for combo in self.combos:
            combo.clear()
            combo.addItem('-', None)

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
