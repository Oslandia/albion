# coding: utf-8

import logging

from qgis.core import (QGis,
                       QgsField,
                       QgsMapLayerRegistry,
                       QgsFeature)

from PyQt4.QtCore import QVariant, QTimer

from shapely.geometry import LineString

from .qgis_hal import (insert_features_in_layer,
                       create_memory_layer,
                       copy_layer_attributes_to_layer,
                       qgeom_from_wkt)


class ConvertDataLayer():
    def __init__(self, data_layer, dialog):
        self.dialog = dialog
        self.data_layer = data_layer
        self.new_layer = create_memory_layer(
            QGis.Line,
            data_layer.crs(),
            data_layer.name())

        copy_layer_attributes_to_layer(data_layer,
                                       self.new_layer,
                                       [QgsField('link', QVariant.Int)])

        self.my_id = 0
        self.features = data_layer.getFeatures()
        QgsMapLayerRegistry.instance().addMapLayer(self.new_layer)

    def tick(self):
        logging.debug('TICK')
        features = []
        for f in self.features:
            p1 = (f.attribute('From X'),
                  f.attribute('From Y'),
                  f.attribute('From Z'))
            p2 = (f.attribute('To X'),
                  f.attribute('To Y'),
                  f.attribute('To Z'))
            geom = LineString([p1, p2])
            new_feature = QgsFeature()
            new_feature.setGeometry(qgeom_from_wkt(geom.wkt.replace(' Z', 'Z')))

            attrs = f.attributes()
            attrs += [self.my_id]
            new_feature.setAttributes(attrs)
            self.my_id = self.my_id + 1
            features += [new_feature]

            self.dialog.setValue(self.my_id)

            if len(features) == 1000:
                break

        insert_features_in_layer(features, self.new_layer)

        if self.dialog.wasCanceled():
            pass
        elif self.features.isClosed():
            pass
        else:
            self.timer = QTimer.singleShot(0, self.tick)
