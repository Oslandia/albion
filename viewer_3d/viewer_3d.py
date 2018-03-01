# -*- coding: UTF-8 -*-

#from qgis.core import *


from OpenGL.GL import *
from OpenGL.GL import shaders

from OpenGL import GLU

from PyQt4.QtOpenGL import QGLWidget, QGLPixelBuffer, QGLFormat
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import uic

import os
import re
import numpy

from .camera import Camera
from .scene import Scene
from .viewer_controls import ViewerControls

class Viewer3d(QGLWidget):

    def __init__(self, project=None, parent=None):
        super(Viewer3d, self).__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.scene = None
        self.__default_param = {
                "label": False,
                "node": False,
                "end": False,
                "edge": False,
                "volume": False,
                "error": False,
                "section": False,
                "z_scale": 1,
                "graph_id": None,
                "transparency": 0.
                }
        
        self.__param = self.__default_param
        self.__project = project
        self.resetScene(project)
        self.setMouseTracking(True)

        self.tool = None
        self.oldx = 0
        self.oldy = 0
        self.previous_pick = None

    def refresh_data(self):
        if self.scene and self.__project.has_collar:
            self.resetScene(self.__project, False)
            for layer in ['node', 'edge', 'volume', 'section', 'error', 'end']:
                self.scene.update(layer)
            self.update()

    def resetScene(self, project, resetCamera=True):
        if project and project.has_collar:
            self.scene = Scene(project, self.__param, self.bindTexture, self)
            if resetCamera:
                at = self.scene.center
                ext_y = self.scene.extent[3] - self.scene.extent[1]
                eye = at + QVector3D(0, -1.5*ext_y , 0.5*ext_y)
                self.camera = Camera(eye, at)

            if self.__param['graph_id']:
                for layer in ['node', 'edge', 'volume', 'section', 'error', 'end']:
                    self.scene.update(layer)
            self.update()
        else:
            self.scene and self.scene.setParent(None)
            self.scene = None
            self.camera = Camera(QVector3D(10, 10, -10), QVector3D(0, 0, 0))
        self.__project = project

    def set_xy_pov(self):
        at = self.scene.center
        ext_y = self.scene.extent[3] - self.scene.extent[1]
        eye = at + QVector3D(0, 0, 1.5*ext_y)
        up = QVector3D(0, 1, 0)
        self.camera.reset(Camera(eye, at, up))
        

    def setTransparencyPercent(self, value):
        self.__param["transparency"]=value/100.
        self.update()

    def setZscale(self, value):
        self.__param["z_scale"]=value
        self.update()

    def toggle_labels(self, state):
        self.__param["label"] = state
        self.update()

    def toggle_nodes(self, state):
        self.__param["node"] = state
        self.update()

    def toggle_ends(self, state):
        self.__param["end"] = state
        self.update()

    def toggle_edges(self, state):
        self.__param["edge"] = state
        self.update()

    def toggle_volumes(self, state):
        self.__param["volume"] = state
        self.update()

    def toggle_errors(self, state):
        self.__param["error"] = state
        self.update()


    def set_delete_tool(self, state):
        if state:
            self.tool = 'delete'
        else:
            self.tool = None

    def set_add_tool(self, state):
        if state:
            self.tool = 'add'
        else:
            self.tool = None

    def set_graph(self, graph_id):
        self.__param["graph_id"] = graph_id
        self.refresh_data()

    def resizeGL(self, width, height):
        height = 1 if not height else height
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        GLU.gluPerspective(45.0, float(width) / height, 100, 100000)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self, context=None, camera=None, pick_layer=None):
        context = context or self
        if pick_layer:
            glClearColor(1., 1., 1., 1.)
        else:
            glClearColor(.7, .7, .7, 1.)

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
            if pick_layer:
                self.scene.pickrendergl(pick_layer)
            else:
                self.scene.rendergl(leftv, upv, c.eye, context.height(), context)
        else:
            # Draw 3 Cube faces (multiple quads)
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
     
            glNormal3f(0, 0, 1)
            glVertex3f( 1.0, 1.0, 1.0)
            glNormal3f(0, 0, 1)
            glVertex3f(-1.0, 1.0, 1.0)
            glNormal3f(0, 0, 1)
            glVertex3f(-1.0,-1.0, 1.0)
            glNormal3f(0, 0, 1)
            glVertex3f( 1.0,-1.0, 1.0)
     
            glNormal3f(1, 0, 0)
            glVertex3f( 1.0, 1.0,-1.0) 
            glNormal3f(1, 0, 0)
            glVertex3f( 1.0, 1.0, 1.0)
            glNormal3f(1, 0, 0)
            glVertex3f( 1.0,-1.0, 1.0)
            glNormal3f(1, 0, 0)
            glVertex3f( 1.0,-1.0,-1.0)

            glEnd()
            
    def highlight(self, x, y):
        if x <=1 or y <=1 or x>=self.width()-1 or y>=self.height()-1:
            return None

        if self.tool == "delete":
            self.paintGL(pick_layer="edge")
            return self.scene.highlight("edge", numpy.frombuffer(
                glReadPixels(x, self.height() - y, 
                        1, 1, GL_RGBA, GL_UNSIGNED_BYTE), numpy.uint8, 4))
        elif self.tool == "add":
            self.paintGL(pick_layer="node")
            return self.scene.highlight("node", numpy.frombuffer(
                glReadPixels(x, self.height() - y, 
                        1, 1, GL_RGBA, GL_UNSIGNED_BYTE), numpy.uint8, 4))
        return None

    def mouseMoveEvent(self, event):
        delta_x = float(event.x() - self.oldx)/self.width()
        delta_y = float(self.oldy - event.y())/self.height()
        self.camera.move(delta_x, delta_y, event.buttons(), event.modifiers())
        self.oldx = event.x()
        self.oldy = event.y()
        
        self.highlight(event.x(), event.y())

        self.update()

    def mousePressEvent(self, event):
        self.oldx = event.x()
        self.oldy = event.y()

        highlighted = self.highlight(event.x(), event.y())
        if highlighted:
            if self.tool == "delete":
                if QMessageBox.Ok == QMessageBox.question(self, "Delete one edge", "Do you want to delete selectd edge ?", QMessageBox.Ok|QMessageBox.Cancel):
                    self.scene.delete_highlighted("edge")
                    self.scene.update("edge")
                    self.update()
            if self.tool == "add":
                if self.previous_pick:
                    self.scene.add_edge(self.previous_pick, highlighted)
                    self.previous_pick = None
                    self.scene.update("edge")
                    self.update()
                else:
                    self.previous_pick = highlighted
        else:
            self.previous_pick = None

    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.camera.reset()
            self.update()

class ViewerWindow(QMainWindow):
    def __init__(self, project=None, parent=None):
        super(ViewerWindow, self).__init__(parent)
        self.resize(900,400)
        self.viewer = Viewer3d(project, self)
        self.viewer.show()
        self.setCentralWidget(self.viewer)
        self.controls = self.addToolBar("Albion 3D toolbar")
        self.controls.addWidget(ViewerControls(self.viewer, self))
