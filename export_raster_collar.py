from qgis.utils import iface
from qgis.core import Qgis
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt import uic
import os

class ExportRasterCollarDialog(QDialog):
    def __init__(self, project, parent=None):
        QDialog.__init__(self, parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'export_raster_collar.ui'), self)
        self.__project = project

    def accept(self):
        self.__project.create_raster_from_collar(self.useDepth.isChecked(),
                                     self.outDir.filePath(),
                                     self.xspacing.value(),
                                     self.yspacing.value())
        iface.messageBar().pushMessage("Export raster completed",
                                       """<a href="file:///{dir}">{dir}</a>""".format(dir=self.outDir.filePath()),
                                       level=Qgis.Info, duration=5)
        self.close()
