# -*- coding: UTF-8 -*-

from OpenGL.GL import *
from OpenGL.GL import shaders

from OpenGL import GLU

from PyQt4.QtOpenGL import QGLWidget, QGLPixelBuffer, QGLFormat
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import uic

from qgis.gui import *
from qgis.core import *

import os
import re
import numpy

from .camera import Camera
from .scene import Scene
from .viewer_controls import ViewerControls

class Viewer3d(QGLWidget):

    def __init__(self, conn_info=None, graph=None, parent=None):
        super(Viewer3d, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.scene = None
        self.resetScene(conn_info, graph)
        self.__param = {
                "label": False,
                "node": False,
                "edge": False,
                "top": False,
                "bottom": False,
                "section": False,
                "volume": False,
                "z_scale": 1
                }

    def refresh_data(self):
        if self.scene:
            self.resetScene(self.scene.conn_info, self.scene.graph_id, False)
            self.update()

    def resetScene(self, conn_info, graph_id, resetCamera=True):
        if conn_info and graph_id:
            self.scene = Scene(conn_info, graph_id, self.__param, self.bindTexture, self)
            if resetCamera:
                at = self.scene.center
                ext_y = self.scene.extent[3] - self.scene.extent[1]
                eye = at + QVector3D(0, -1.5*ext_y , 0.5*ext_y)
                self.camera = Camera(eye, at)

        else:
            self.scene and self.scene.setParent(None)
            self.scene = None
            self.camera = Camera(QVector3D(10, 10, -10), QVector3D(0, 0, 0))

    def setZscale(self, value):
        self.__param["z_scale"]=value
        self.update()

    def toggle_labels(self, state):
        self.__param["label"] = state
        self.update()

    def toggle_nodes(self, state):
        self.__param["node"] = state
        self.update()

    def toggle_edges(self, state):
        self.__param["edge"] = state
        self.update()

    def toggle_tops(self, state):
        self.__param["top"] = state
        self.update()

    def toggle_bottoms(self, state):
        self.__param["bottom"] = state
        self.update()

    def toggle_sections(self, state):
        self.__param["section"] = state
        self.update()

    def toggle_volumes(self, state):
        self.__param["volume"] = state
        self.update()

    def resizeGL(self, width, height):
        height = 1 if not height else height
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        GLU.gluPerspective(45.0, float(width) / height, 100, 100000)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self, context=None, camera=None):
        context = context or self
        glClearColor(.7, .7, .7, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        c = camera or self.camera
        dist = (c.at - c.eye).length()
        GLU.gluPerspective(45.0, float(context.width())/context.height(), 0.01*dist, 100*dist)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)

        GLU.gluLookAt(c.eye.x(), c.eye.y(), c.eye.z(),
                      c.at.x(), c.at.y(), c.at.z(),
                      c.up.x(), c.up.y(), c.up.z())

        leftv = QVector3D.crossProduct(c.up, c.at-c.eye).normalized()
        upv = QVector3D.crossProduct(c.at-c.eye, leftv).normalized()

        to = (c.at - c.eye).normalized()

        glLightfv(GL_LIGHT0, GL_POSITION, [c.eye.x(), c.eye.y(), c.eye.z(), 1])
        
        if self.scene:
            self.scene.rendergl(leftv, upv, c.eye, context.height(), context)
        else:
            # Draw Cube (multiple quads)
            glEnable(GL_DEPTH_TEST)
            glLightModelfv(GL_LIGHT_MODEL_TWO_SIDE, GL_TRUE)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
            glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT,  [1., 0., 0., 1.])
            glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE,  [1., 0., 0., 1.])
            glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, [1., 1., 1., 1.])
            glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 50)

            glBegin(GL_QUADS)
     
            glNormal3f(0, 1, 0)
            glVertex3f( 1.0, 1.0,-1.0)
            glNormal3f(0, 1, 0)
            glVertex3f(-1.0, 1.0,-1.0)
            glNormal3f(0, 1, 0)
            glVertex3f(-1.0, 1.0, 1.0)
            glNormal3f(0, 1, 0)
            glVertex3f( 1.0, 1.0, 1.0) 
     
            #glNormal3f(0, -1, 0)
            #glVertex3f( 1.0,-1.0, 1.0)
            #glNormal3f(0, -1, 0)
            #glVertex3f(-1.0,-1.0, 1.0)
            #glNormal3f(0, -1, 0)
            #glVertex3f(-1.0,-1.0,-1.0)
            #glNormal3f(0, -1, 0)
            #glVertex3f( 1.0,-1.0,-1.0) 
     
            glNormal3f(0, 0, 1)
            glVertex3f( 1.0, 1.0, 1.0)
            glNormal3f(0, 0, 1)
            glVertex3f(-1.0, 1.0, 1.0)
            glNormal3f(0, 0, 1)
            glVertex3f(-1.0,-1.0, 1.0)
            glNormal3f(0, 0, 1)
            glVertex3f( 1.0,-1.0, 1.0)
     
            #glNormal3f(0, 0, -1)
            #glVertex3f( 1.0,-1.0,-1.0)
            #glNormal3f(0, 0, -1)
            #glVertex3f(-1.0,-1.0,-1.0)
            #glNormal3f(0, 0, -1)
            #glVertex3f(-1.0, 1.0,-1.0)
            #glNormal3f(0, 0, -1)
            #glVertex3f( 1.0, 1.0,-1.0)
     
            #glNormal3f(-1, 0, 0)
            #glVertex3f(-1.0, 1.0, 1.0) 
            #glNormal3f(-1, 0, 0)
            #glVertex3f(-1.0, 1.0,-1.0)
            #glNormal3f(-1, 0, 0)
            #glVertex3f(-1.0,-1.0,-1.0) 
            #glNormal3f(-1, 0, 0)
            #glVertex3f(-1.0,-1.0, 1.0) 
     
            glNormal3f(1, 0, 0)
            glVertex3f( 1.0, 1.0,-1.0) 
            glNormal3f(1, 0, 0)
            glVertex3f( 1.0, 1.0, 1.0)
            glNormal3f(1, 0, 0)
            glVertex3f( 1.0,-1.0, 1.0)
            glNormal3f(1, 0, 0)
            glVertex3f( 1.0,-1.0,-1.0)

            glEnd()
            


    def mouseMoveEvent(self, event):
        delta_x = float(event.x() - self.oldx)/self.width()
        delta_y = float(self.oldy - event.y())/self.height()
        self.camera.move(delta_x, delta_y, event.buttons(), event.modifiers())
        self.oldx = event.x()
        self.oldy = event.y()
        self.update()

    def mousePressEvent(self, event):
        self.oldx = event.x()
        self.oldy = event.y()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.camera.reset()
            self.update()

class ViewerWindow(QMainWindow):
    def __init__(self, conn_info=None, parent=None):
        super(ViewerWindow, self).__init__(parent)
        self.resize(900,400)
        self.viewer = Viewer3d(conn_info, self)
        self.viewer.show()
        self.setCentralWidget(self.viewer)
        self.controls = QDockWidget(self)
        self.controls.setWidget(ViewerControls(self.viewer, self))
        self.addDockWidget(Qt.RightDockWidgetArea, self.controls)

if __name__ == "__main__":

    from PyQt4.QtGui import *
    from PyQt4.QtCore import *
    import sys

    app = QApplication(sys.argv)

    QCoreApplication.setOrganizationName("QGIS")
    QCoreApplication.setApplicationName("QGIS2")

    assert len(sys.argv) >= 2
    win = ViewerWindow()
    win.viewer.resetScene(sys.argv[1], 'tarat_u1' )
    win.show()

    sys.exit(app.exec_())
