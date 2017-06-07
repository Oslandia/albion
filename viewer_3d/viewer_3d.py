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
from math import sqrt, ceil, log

from .camera import Camera
from .scene import Scene
from .viewer_controls import ViewerControls

class Viewer3d(QGLWidget):

    def __init__(self, conn_info=None, graph=None, parent=None):
        super(Viewer3d, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.scene = None
        self.resetScene(conn_info, graph)

    def resetScene(self, conn_info, graph_id):
        if conn_info:
            self.scene = Scene(conn_info, graph_id, self.bindTexture, self)
            at = self.scene.center
            ext_y = self.scene.extent[3] - self.scene.extent[1]
            eye = at + QVector3D(0, -1.5*ext_y , 0.5*ext_y)
            self.camera = Camera(eye, at)
            self.scene.changed.connect(self.update)
            self.initializeGL()

        else:
            self.scene and self.scene.setParent(None)
            self.scene = None
            self.camera = Camera(QVector3D(10, 10, -10), QVector3D(0, 0, 0))

    def initializeGL(self):
        if self.scene:
            self.scene.initializeGL()

    def toggle_holes(self, state):
        if self.scene:
            self.scene.toggle_holes(state)

    def toggle_labels(self, state):
        if self.scene:
            self.scene.toggle_labels(state)

    def setZscale(self, value):
        if self.scene:
            self.scene.setZscale(value)

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
        #glLightfv(GL_LIGHT0, GL_AMBIENT, [.2, .2, .2, 1.]) 


        GLU.gluLookAt(c.eye.x(), c.eye.y(), c.eye.z(),
                      c.at.x(), c.at.y(), c.at.z(),
                      c.up.x(), c.up.y(), c.up.z())

        leftv = QVector3D.crossProduct(c.up, c.at-c.eye).normalized()
        upv = QVector3D.crossProduct(c.at-c.eye, leftv).normalized()

        to = (c.at - c.eye).normalized()
        #lightpos = numpy.require([c.at.x(), c.at.y(), c.at.z(), 1], numpy.float32, 'C')
        #glLightfv(GL_LIGHT0, GL_POSITION, lightpos)

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
            


        #glLightf(GL_LIGHT0, GL_CONSTANT_ATTENUATION, 2.0)

    def image(self, size):
        if not self.scene:
            return
        # we want all the scene in image, regardless of aspect ratio
        zoom_out = max(float(self.width())/size.width(), float(self.height())/size.height())
        camera = Camera(self.camera.eye, self.camera.at, self.camera.up)
        #camera.eye = camera.at + (camera.eye-camera.at)*zoom_out
        w, h = size.width(), size.height()
        roundupSz = QSize(pow(2, ceil(log(w)/log(2))),
                          pow(2, ceil(log(h)/log(2))))
        fmt = QGLFormat()
        #fmt.setAlpha(True)
        context = QGLPixelBuffer(roundupSz, fmt)
        context.makeCurrent()
        self.scene.initializeGL(context.bindTexture)
        self.scene.requireShaderRecompile()
        self.paintGL(context, camera)
        img = context.toImage()
        context.doneCurrent()

        return img.copy( .5*(roundupSz.width()-w), 
                         .5*(roundupSz.height()-h), 
                         w, h) 

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
