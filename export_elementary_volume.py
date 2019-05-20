import os

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QApplication
from qgis.PyQt.QtGui import QCursor

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

        closed_only = self.mClosedVolume.isChecked()

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
            outdir = self.mOutputDir.text()

            if self.mFormat.currentText() == "OBJ":
                self.project.export_elementary_volume_obj(
                    self.graph, cell, outdir, True
                )
            else:  # DXF
                self.project.export_elementary_volume_dxf(
                    self.graph, cell, outdir, True
                )

            if not closed_only:
                if self.mFormat.currentText() == "OBJ":
                    self.project.export_elementary_volume_obj(
                        self.graph, cell, outdir, False
                    )
                else:  # DXF
                    self.project.export_elementary_volume_dxf(
                        self.graph, cell, outdir, False
                    )

        QApplication.restoreOverrideCursor()
