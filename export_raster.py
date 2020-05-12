from qgis.utils import iface
from qgis.core import Qgis
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt import uic
import os

class ExportRasterDialog(QDialog):
    def __init__(self, project, parent=None):
        QDialog.__init__(self, parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'export_raster.ui'), self)
        self.__project = project
        self.populateFormation()

    def populateFormation(self):
        with self.__project.connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                        SELECT DISTINCT comments, code
                        FROM albion.formation
                        ORDER BY comments
                        """)
            for i in cur.fetchall():
                self.formation.addItem(i[0], i[1])

    def accept(self):
        self.__project.export_raster(self.formation.currentData(),
                                     self.level.currentText(),
                                     self.outDir.filePath(),
                                     self.xspacing.value(),
                                     self.yspacing.value())
        iface.messageBar().pushMessage("Export raster completed",
                                       """<a href="file:///{dir}">{dir}</a>""".format(dir=self.outDir.filePath()),
                                       level=Qgis.Info, duration=5)
        self.close()
