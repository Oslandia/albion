# coding: utf-8

import os
import sys
import unittest

from qgis.core import (QGis, QgsField, QgsApplication, QgsMapLayerRegistry,
                       QgsMapLayer, QgsVectorLayer)

from PyQt4.QtCore import QVariant


from albion.plugin import Plugin
from albion.qgis_hal import copy_layer_attributes_to_layer, create_memory_layer


_HOME = os.path.expanduser("~")
_PLUGINS_DIR = os.path.join(_HOME, '.qgis2', 'python', 'plugins')
_HERE = os.path.abspath(os.path.dirname(__file__))
_DATA_DIR = os.path.join(_HERE, 'data')
_DATAFILE = os.path.join(_DATA_DIR, 'DATA_anonym.txt')
URI = _DATAFILE + "?type=csv&delimiter=;&geomType=none"

sys.path.insert(0, _PLUGINS_DIR)


class TestGridCreationFromCSV(unittest.TestCase):
    def setUp(self):
        self.app = QgsApplication([], True)
        QgsApplication.initQgis()
        if not os.path.isfile(_DATAFILE):
            raise ValueError("Test file '%s' not found" % _DATAFILE)
        self.layer = QgsVectorLayer(URI, "data_text", "delimitedtext")

    def tearDown(self):
        self.app.quit()

    def test_copy_attributes_from_delimited_text(self):
        new_layer = create_memory_layer(QGis.Line, self.layer.crs(), self.layer.name())
        copy_layer_attributes_to_layer(self.layer,
                                       new_layer,
                                       [QgsField('link', QVariant.Int)])
        self.assertEqual(13, new_layer.fields().count())
        # TODO: test the creation of a vector layer from this delimited text layer


if __name__ == '__main__':
    unittest.main()
