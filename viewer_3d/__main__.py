
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtCore import *
import sys
from ..project import Project
from .viewer_3d import ViewerWindow

app = QApplication(sys.argv)

QCoreApplication.setOrganizationName("QGIS")
QCoreApplication.setApplicationName("QGIS2")

project = Project(sys.argv[1]) if len(sys.argv)>=2 else None
win = ViewerWindow(project)
if len(sys.argv) > 2:
    win.viewer.set_graph(sys.argv[2])

win.show()

sys.exit(app.exec_())

