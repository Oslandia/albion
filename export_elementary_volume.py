import os

from PyQt4 import uic
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QDialog, QFileDialog, QApplication, QCursor

from qgis.core import QgsFeatureRequest


FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "export_elementary_volume.ui")
)


class ExportElementaryVolume(QDialog, FORM_CLASS):
    def __init__(self, layer, project, graph, parent=None):
        super(ExportElementaryVolume, self).__init__(parent)
        self.setupUi(self)

        self.cell_layer = layer
        self.project = project
        self.graph = graph

        self.mSelect.clicked.connect(self.__select)
        self.mButtonBox.accepted.connect(self.__export)

    def __select(self):
        dlg = QFileDialog()
        dlg.setFileMode(QFileDialog.Directory)

        filenames = []
        if dlg.exec_():
            filenames = dlg.selectedFiles()

        if filenames:
            filename = filenames[0]
            self.mOutputDir.setText(filename)

    def __export(self):

        fids = self.cell_layer.allFeatureIds()
        if self.mSelection.isChecked():
            fids = self.cell_layer.selectedFeaturesIds()

        closed = self.mClosedVolume.isChecked()

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        QApplication.processEvents()
        for fid in fids:
            request = QgsFeatureRequest(fid)

            ft = None
            for feature in self.cell_layer.getFeatures(request):
                ft = feature

            if not ft:
                return

            cell = ft["id"]
            cell_dir = os.path.join(self.mOutputDir.text(), "{}".format(cell))
            os.makedirs(cell_dir)

            if self.mFormat.currentText() == "OBJ":
                self.project.export_elementary_volume_obj(
                    self.graph, cell, cell_dir, closed
                )
            else:  # DXF
                self.project.export_elementary_volume_dxf(
                    self.graph, cell, cell_dir, closed
                )

        QApplication.restoreOverrideCursor()
