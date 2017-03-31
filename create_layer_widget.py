# coding=utf-8

from qgis.core import *
from qgis.gui import *

from PyQt4 import uic
from PyQt4.QtCore import QVariant
from PyQt4.QtGui import QDialog

from shapely.wkt import loads
from shapely.geometry import LineString
from math import sqrt
import os
import logging
from .qgis_hal import (intersect_linestring_layer_with_wkt,
                       clone_feature_with_geometry_transform,
                       remove_all_features_from_layer,
                       insert_features_in_layer)

def substring_3d(linestring, from_, to_):
    "the linestring a shapely geometry, from_ and to_ are in length units"
    tot_len = 0
    sq = lambda x: x*x
    def interpolate(a, b, ratio):
        return (a[0] + ratio*(b[0] - a[0]), a[1] + ratio*(b[1] - a[1]), a[2] + ratio*(b[2] - a[2]))
    res = []
    for s, e in zip(linestring.coords[0:-1], linestring.coords[1:]):
        length = sqrt(sq(s[0]-e[0]) + sq(s[1]-e[1]) + sq(s[2]-e[2]))
        tot_len += length
        if tot_len > from_:
            if not len(res):
                #interpolate first
                res.append(interpolate(e, s, (tot_len - from_)/length))
            if tot_len >= to_:
                #interpolate last
                res.append(interpolate(e, s, (tot_len - to_)/length))
                break
            res.append(e)
    return LineString(res)


class CreateLayerWidget(QDialog):
    """create layer from a linestring layer and attributes
    from/to of another table/layer

    This is a join, but qgis join would not do because the source
    is a table (no geometry) and the function applied to the geometry is
    not available in qgis.
    """
    def __init__(self, logger, parent=None):
        QDialog.__init__(self, parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), "res/create_layer.ui"), self)
        self.__logger = logger
        for lid, layer in QgsMapLayerRegistry.instance().mapLayers().iteritems():
            logging.info('layer name: {}'.format(layer.name()))
            if layer.type() == QgsMapLayer.VectorLayer and layer.customProperty("projected_layer") is None:
                if layer.geometryType() == QGis.Line:
                    self.geometryLayer.addItem(layer.name(), layer.id())
                self.dataLayer.addItem(layer.name(), layer.id())

        if self.dataLayer.count():
            self.__set_data_layer(self.dataLayer.currentIndex())

        if self.geometryLayer.count():
            self.__set_geometry_layer(self.geometryLayer.currentIndex())

        self.dataLayer.currentIndexChanged.connect(self.__set_data_layer)
        self.geometryLayer.currentIndexChanged.connect(self.__set_geometry_layer)

    def __set_geometry_layer(self, idx):
        self.geomId.clear()
        lid = self.geometryLayer.itemData(idx)
        if lid is None:
            return
        layer = QgsMapLayerRegistry.instance().mapLayer(lid)
        fields = layer.fields()
        for f in range(fields.count()):
            self.geomId.addItem(fields.field(f).name(), f)

    def __set_data_layer(self, idx):
        self.fromColumn.clear()
        self.toColumn.clear()
        self.joinField.clear()
        lid = self.dataLayer.itemData(idx)
        if lid is None:
            return
        layer = QgsMapLayerRegistry.instance().mapLayer(lid)
        fields = layer.fields()
        from_, to_ = None, None
        for f in range(fields.count()):
            self.fromColumn.addItem(fields.field(f).name(), f)
            self.toColumn.addItem(fields.field(f).name(), f)
            self.joinField.addItem(fields.field(f).name(), f)
            if from_ is None and fields.field(f).name().find('from') != -1:
                from_ = f
            if to_ is None and fields.field(f).name().find('to') != -1:
                to_ = f
        if from_ is not None:
            self.fromColumn.setCurrentIndex(from_)
        if to_ is not None:
            self.toColumn.setCurrentIndex(to_)


    def accept(self):
        self.__logger.pushInfo("Info", "accepted")

        data_layer = QgsMapLayerRegistry.instance().mapLayer(
                self.dataLayer.itemData(self.dataLayer.currentIndex()))
        geom_layer = QgsMapLayerRegistry.instance().mapLayer(
                self.geometryLayer.itemData(self.geometryLayer.currentIndex()))
        geom_id = self.geomId.currentText()
        join_field = self.joinField.currentText()
        to_column = self.toColumn.currentText()
        from_column = self.fromColumn.currentText()
        logger.info('{} {} {} {} {} {}'.format(data_layer.name(), geom_layer.name(), geom_id, join_field, to_column, from_column))
        geometries = {feature[geom_id]: QgsGeometry(feature.geometry())
                for feature in geom_layer.getFeatures()}
        features = []
        my_id = 1
        for feature in data_layer.getFeatures():
            from_ = feature[from_column]
            to_ = feature[to_column]
            id_ = feature[join_field]
            geom = QgsGeometry.fromWkt(
                    substring_3d(
                        loads(QgsGeometry.exportToWkt(geometries[id_]).replace('Z', ' ')),
                        from_, to_).wkt)
            new_feature = QgsFeature()
            attrs = feature.attributes()
            attrs += [my_id]
            new_feature.setAttributes(attrs)
            new_feature.setGeometry(geom)
            features.append(new_feature)
            my_id += 1

        new_layer = QgsVectorLayer(
            "LineString?crs={}&index=yes".format(
                geom_layer.crs().authid()
                ), data_layer.name(), "memory")
        fields = [data_layer.fields().field(f) for f in range(data_layer.fields().count())]
        for f in fields:
            if f.name() == geom_id:
                f.setName(geom_layer.name())
        fields += [QgsField("link", QVariant.Int)]
        new_layer.dataProvider().addAttributes(fields)
        new_layer.updateFields()
        insert_features_in_layer(features, new_layer)
        QgsMapLayerRegistry.instance().addMapLayer(new_layer)

