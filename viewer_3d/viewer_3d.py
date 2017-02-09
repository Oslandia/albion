import sys
from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4 import QtOpenGL
from OpenGL import GLU
from OpenGL.GL import *

from PyQt4.QtGui import QVector3D, QMatrix4x4
from PyQt4.QtCore import Qt

from numpy import array
import numpy as np

import math
import random

import re, logging


class Camera():
    def __init__(self):
        self.matrix = QMatrix4x4()
        self.position = QVector3D(100, 50, 0)
        self.rotX = 0
        self.rotY = 90
        self.scale_z = 3.0

    def worldMatrix(self, include_translation = True):
        m = QMatrix4x4()
        # Z up
        m.rotate(90, 0, 0, 1)

        m2 = QMatrix4x4()
        m2.rotate(self.rotX, 0, 0, 1)
        m3 = QMatrix4x4()
        m3.rotate(self.rotY, 0, 1, 0)

        m = (m2 * (m3 * m))
        if include_translation:
            s = QMatrix4x4()
            s.scale(1, 1, 1.0 / self.scale_z)
            m = s * m

            m[(0, 3)] = self.position.x()
            m[(1, 3)] = self.position.y()
            m[(2, 3)] = self.position.z()

        return m

    def move(self, delta_x, delta_y, delta_z, buttons, modifiers):
        # user is dragging
        move_speed = min(250, max(10, self.position.length() * 0.5))

        pan = False
        if int(buttons) & Qt.LeftButton and int(modifiers) & Qt.ShiftModifier:
            pan = True
        elif int(buttons) & Qt.MiddleButton:
            pan = True

        if pan:
            translation = QVector3D(delta_x * move_speed, 0, delta_z * move_speed)
            translation = self.worldMatrix(False) * translation
            translation.setZ(translation.z() + delta_y * move_speed)
            self.position += translation
        elif int(modifiers) & Qt.ControlModifier:
            pass
        else:
            self.rotX += -delta_x*50
            self.rotY += delta_y*50


class Viewer3D(QtOpenGL.QGLWidget):
    def __init__(self, parent=None):
        self.parent = parent
        QtOpenGL.QGLWidget.__init__(self, parent)
        self.camera = Camera()
        self.polygons_vertices = []
        self.scale_z = 3.0
        self.colors = []
        self.polygons_colors = []
        self.layers_vertices = None
        self.center = [0, 0, 0]
        self.section_vertices = None

    def initializeGL(self):
        self.qglClearColor(QtGui.QColor(150, 150,  150))
        self.vertices = None
        self.graph_vertices = None

    def resizeGL(self, width, height):
        if height == 0: height = 1

        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        self.aspect = width / float(height)

        GLU.gluPerspective(45.0, self.aspect, 0.1, 1000.0)


    def mouseMoveEvent(self, event):
        delta_x = float(event.x() - self.oldx)/self.width()
        delta_y = float(self.oldy - event.y())/self.height()
        self.camera.move(delta_x, delta_y, 0, event.buttons(), event.modifiers())
        self.oldx = event.x()
        self.oldy = event.y()
        self.update()

    def mousePressEvent(self, event):
        self.oldx = event.x()
        self.oldy = event.y()

    def wheelEvent(self, event):
        self.camera.move(0, 0, 0.1 if event.delta() < 0 else -0.1 , Qt.LeftButton, Qt.ShiftModifier)
        self.update()

    def define_generatrices_vertices(self, layers_vertices):
        self.layers_vertices = layers_vertices

    def define_section_vertices(self, section_vertices):
        self.section_vertices = np.array(section_vertices)

    def updateVolume(self, vertices, volumes):

        if len(volumes) == 0:
            self.vertices = None
            return


        self.vertices = []
        self.colors = []
        for v in vertices:
            self.colors += [ self._color() ]

        indices = []
        for vol in volumes:
            for tri in vol:
                idx = len(self.vertices)
                self.vertices += [ vertices[tri[i]] for i in range(0, 3) ]
                indices += [[idx, idx+1, idx+2]]

        self.vertices = np.array(self.vertices)

        self.indices = np.array(indices)

        self.normals = self.computeNormals(self.vertices, self.indices)

        self._updateCenterExtent(self.vertices)


    def updateGraph(self, graph_vertices, graph_indices, highlights):
        if graph_vertices is None or len(graph_vertices) == 0:
            self.graph_vertices = None
        else:
            was_empty = self.graph_vertices is None
            self.graph_vertices = np.array(graph_vertices)
            self.graph_indices = graph_indices

            self.graph_colors = [ [1, 0, 0, 1] if i in highlights else [0, 0, 1, 1] for i in range(0, len(graph_vertices)) ]
            # self.graph_colors = [ [1, 0, 0, 1] if (i % 2) == 0 else [0, 0, 1, 1] for i in range(0, len(graph_vertices)) ]

            if was_empty:
                self._updateCenterExtent(self.graph_vertices)

    def _color(self, t = None):
        a = [0.5, 0.5, 0.5]
        b = [0.5, 0.5, 0.5]
        c = [1.0, 1.0, 1.0]
        d = [0.00, 0.10, 0.20]

        def formula(i, t): return a[i] + b[i] * math.cos(2 * 3.14 * (c[i] * t + d[i]))

        if t is None:
            t = random.random()
        return [formula(0, t), formula(1, t), formula(2, t), 0.3]


    def _updateCenterExtent(self, vertices):
        self.center = [
            np.mean(vertices[:, 0]),
            np.mean(vertices[:, 1]),
            np.mean(vertices[:, 2])
        ]

        extent = (np.min(vertices[:,0]),
                       np.min(vertices[:,1]),
                       np.max(vertices[:,0]),
                       np.max(vertices[:,1])
                       )

        ext_y = extent[3] - extent[1]


    def computeNormals(self, vtx, idx):

        nrml = np.zeros(vtx.shape, np.float32)

        # compute normal per triangle
        triN = np.cross(
            vtx[idx[:,1]] - vtx[idx[:,0]],
            vtx[idx[:,2]] - vtx[idx[:,0]])

        # sum normals at vtx
        nrml[idx[:,0]] += triN[:]
        nrml[idx[:,1]] += triN[:]
        nrml[idx[:,2]] += triN[:]

        # compute norms
        nrmlNorm = np.sqrt(nrml[:,0]*nrml[:,0]+nrml[:,1]*nrml[:,1]+nrml[:,2]*nrml[:,2])

        return nrml/nrmlNorm.reshape(-1,1)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glEnable(GL_DEPTH_TEST)
        glBlendFunc (GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);


        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()

        eye = self.camera.position

        dist = eye.length()
        GLU.gluPerspective(45.0, self.aspect, 0.01, 10000) #*dist)


        glMatrixMode(GL_MODELVIEW)
        self.camera.scale_z = self.scale_z

        m = self.camera.worldMatrix()

        modelview, r = m.inverted()

        glLoadMatrixf(modelview.data())
        # glLoadIdentity()

        #GLU.gluLookAt(eye.x(), eye.y(), eye.z(),
        #               0, 0, 0,
        #               0, 0, 1)
        #glScalef(1.0, 1.0, self.scale_z)

        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
        glLightfv(GL_LIGHT0, GL_POSITION, [eye.x(), eye.y(), eye.z(), 0])

        glEnableClientState(GL_VERTEX_ARRAY)

        if not (self.layers_vertices is None):
            glLineWidth(1)
            for lid in self.layers_vertices:
                if not self.layers_vertices[lid]['visible']:
                    continue
                layer = self.layers_vertices[lid]['v']
                glVertexPointerf(layer - self.center)
                glColor4fv(list(self.layers_vertices[lid]['c']))
                glDrawArrays(GL_LINES, 0, len(layer))
            glLineWidth(1)

        if not (self.vertices is None):
            glVertexPointerf(self.vertices - self.center)
            glNormalPointerf(self.normals)

            glEnable ( GL_COLOR_MATERIAL ) ;
            # draw wireframe
            glColor4f(0,0.6,0,1)
            glLineWidth(3)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            glDrawElementsui(GL_TRIANGLES, self.indices)

            # draw lighted
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

            glEnable(GL_LIGHTING)
            glEnableClientState(GL_NORMAL_ARRAY)

            glColorMaterial ( GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE ) ;
            glEnable ( GL_COLOR_MATERIAL ) ;

            glColor4f(0, 1, 0, 1)
            glVertexPointerf(self.vertices - self.center)
            glNormalPointerf(self.normals)
            glDrawElementsui(GL_TRIANGLES, self.indices)

            glDisable(GL_COLOR_MATERIAL)
            glDisableClientState(GL_NORMAL_ARRAY)


        # gen 1 color per polygon
        if len(self.colors) < len(self.polygons_vertices):
            self.colors = []
            spacing = 1.0 / len(self.polygons_vertices)
            for i in range(0, len(self.polygons_vertices)):
                self.colors += [self._color(i * spacing)]

        if len(self.polygons_vertices) > 0:
            glDisable(GL_LIGHTING)
            # glEnableClientState(GL_COLOR_ARRAY)

            # glDisable(GL_DEPTH_TEST)

            for polygon in self.polygons_vertices:
                p = np.array(polygon)
                glVertexPointerf(p - self.center)
                indices = [i for i in range(0, len(p))]

                # draw poly
                glColor4fv(self.polygons_colors[self.polygons_vertices.index(polygon)])
                glDrawElementsui(GL_TRIANGLE_STRIP, indices)


                glColor4f(0.9,0.8,0.1,1)
                # draw generatrices
                glDrawElementsui(GL_LINES, indices)


            for polygon in self.polygons_vertices:
                p = np.array(polygon)
                glVertexPointerf(p - self.center)
                indice_lines = []
                for i in range(0, len(p), 2):
                    indice_lines += [i]
                for i in range(len(p)-1, 0, -2):
                    indice_lines += [i]

                indice_lines += [0]

                glLineWidth(2)

                glColor4f(1.0,1.0,1.1,1)
                # draw generatrices
                glDrawElementsui(GL_LINE_STRIP, indice_lines)

        if not (self.section_vertices is None):
            glDisable ( GL_COLOR_MATERIAL ) ;
            glDisable(GL_LIGHTING)
            glEnable (GL_BLEND);
            glColor4fv([1, 1, 0, 0.2])
            glVertexPointerf(self.section_vertices - self.center)
            glDrawArrays(GL_TRIANGLE_STRIP, 0, len(self.section_vertices))
            glDisable (GL_BLEND);
            glEnable ( GL_COLOR_MATERIAL ) ;

        if not (self.graph_vertices is None):
            pass
            glDisable(GL_LIGHTING)
            # glDisable(GL_DEPTH_TEST)
            glEnableClientState(GL_COLOR_ARRAY)


            glVertexPointerf(self.graph_vertices - self.center)
            glColorPointerf(self.graph_colors)
            glLineWidth(1)
            glDrawElementsui(GL_LINES, self.graph_indices) #[i for i in range(0, len(self.graph_vertices))])
            glPointSize(4)
            # glDrawElementsui(GL_POINTS, [i for i in range(0, len(self.graph_vertices))])
            glDisableClientState(GL_COLOR_ARRAY)

