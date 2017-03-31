# coding=utf-8

from PyQt4.QtGui import QColor
from PyQt4 import QtOpenGL
from OpenGL import GLU
from OpenGL import GL

from PyQt4.QtGui import QVector3D, QMatrix4x4
from PyQt4.QtCore import Qt

import numpy as np

import math
import random

import logging


class Camera():
    def __init__(self):
        self.matrix = QMatrix4x4()
        self.position = QVector3D(0, -1500, 500)
        self.rotX = -90
        self.rotY = 40
        self.scale_z = 3.0

    def worldMatrix(self, include_translation=True):
        m = QMatrix4x4()
        # Z up
        m.rotate(90, 0, 0, 1)

        m2 = QMatrix4x4()
        m2.rotate(self.rotX, 0, 0, 1)
        m3 = QMatrix4x4()
        m3.rotate(self.rotY, 0, 1, 0)
        s = QMatrix4x4()
        s.scale(1, 1, 1.0 / self.scale_z)

        m = s * (m2 * (m3 * m))
        if include_translation:
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
            translation = QVector3D(delta_x * move_speed, delta_y * move_speed,
                                    delta_z * move_speed)
            logging.debug(translation)
            translation = self.worldMatrix(False) * translation
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
        self.qglClearColor(QColor(250, 250,  250))
        self.vertices = None
        self.graph_vertices = None

    def resizeGL(self, width, height):
        height = max(height, 1)
        GL.glViewport(0, 0, width, height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        self.aspect = width / float(height)

        GLU.gluPerspective(45.0, self.aspect, 0.1, 1000.0)

    def mouseMoveEvent(self, event):
        delta_x = float(event.x() - self.oldx)/self.width()
        delta_y = float(self.oldy - event.y())/self.height()
        self.camera.move(
            delta_x, delta_y, 0, event.buttons(), event.modifiers())
        self.oldx = event.x()
        self.oldy = event.y()
        self.update()

    def mousePressEvent(self, event):
        self.oldx = event.x()
        self.oldy = event.y()

    def wheelEvent(self, event):
        self.camera.move(0, 0, 0.1 if event.delta() < 0 else -0.1,
                         Qt.LeftButton,
                         Qt.ShiftModifier)
        self.update()

    def define_generatrices_vertices(self, layers_vertices):
        self.layers_vertices = layers_vertices

        centers = []
        for l in layers_vertices:
            centers += [self._computeCenter(self.layers_vertices[l]['v'])]

        print centers
        centers = np.array(centers)
        self.center = [
            np.mean(centers[:, 0]),
            np.mean(centers[:, 1]),
            np.mean(centers[:, 2])
        ]
        logging.error(self.center)

    def define_section_vertices(self, section_vertices):
        self.section_vertices = np.array(section_vertices)

    def updateVolume(self, vertices, volumes):
        if len(volumes) == 0:
            self.vertices = None
            return

        self.vertices = []
        self.colors = []
        for v in vertices:
            self.colors += [self._color()]

        indices = []
        for vol in volumes:
            for tri in vol:
                idx = len(self.vertices)
                self.vertices += [vertices[tri[i]] for i in range(0, 3)]
                indices += [[idx, idx+1, idx+2]]

        self.vertices = np.array(self.vertices)
        self.indices = np.array(indices)
        self.normals = self.computeNormals(self.vertices, self.indices)

    def updateGraph(self, graph_vertices, graph_indices, highlights):
        if graph_vertices is None or len(graph_vertices) == 0:
            self.graph_vertices = None
        else:
            self.graph_vertices = np.array(graph_vertices)
            self.graph_indices = graph_indices

            self.graph_colors = [
                [1, 0, 0, 1] if i in highlights else
                [0, 0, 1, 1] for i in range(0, len(graph_vertices))]

    def _color(self, t=None):
        a = [0.5, 0.5, 0.5]
        b = [0.5, 0.5, 0.5]
        c = [1.0, 1.0, 1.0]
        d = [0.00, 0.10, 0.20]

        def formula(i, t):
            return a[i] + b[i] * math.cos(2 * 3.14 * (c[i] * t + d[i]))

        if t is None:
            t = random.random()
        return [formula(0, t), formula(1, t), formula(2, t), 0.3]

    def _computeCenter(self, vertices):
        return [
            np.mean(vertices[:, 0]),
            np.mean(vertices[:, 1]),
            np.mean(vertices[:, 2])
        ]

    def computeNormals(self, vtx, idx):
        nrml = np.zeros(vtx.shape, np.float32)

        # compute normal per triangle
        triN = np.cross(
            vtx[idx[:, 1]] - vtx[idx[:, 0]],
            vtx[idx[:, 2]] - vtx[idx[:, 0]])
        # sum normals at vtx
        nrml[idx[:, 0]] += triN[:]
        nrml[idx[:, 1]] += triN[:]
        nrml[idx[:, 2]] += triN[:]
        # compute norms
        nrmlNorm = np.sqrt(
            nrml[:, 0] * nrml[:, 0] +
            nrml[:, 1] * nrml[:, 1] +
            nrml[:, 2] * nrml[:, 2])
        return nrml/nrmlNorm.reshape(-1, 1)

    def paintGL(self):
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()

        eye = self.camera.position

        GLU.gluPerspective(45.0, self.aspect, 0.01, 10000)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        self.camera.scale_z = self.scale_z

        m = self.camera.worldMatrix()

        modelview, r = m.inverted()

        GL.glLoadMatrixf(modelview.data())

        GL.glEnable(GL.GL_LIGHT0)
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
        GL.glLightfv(
            GL.GL_LIGHT0, GL.GL_POSITION, [eye.x(), eye.y(), eye.z(), 0])

        GL.glEnableClientState(GL.GL_VERTEX_ARRAY)

        if not (self.layers_vertices is None):
            GL.glLineWidth(2)
            for lid in self.layers_vertices:
                if not self.layers_vertices[lid]['visible']:
                    continue
                layer = self.layers_vertices[lid]['v']
                GL.glVertexPointerf(layer - self.center)
                GL.glColor4fv(list(self.layers_vertices[lid]['c']))
                GL.glDrawArrays(GL.GL_LINES, 0, len(layer))
            GL.glLineWidth(1)

        if not (self.vertices is None):
            GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
            GL.glPolygonOffset(-2, -2)

            GL.glVertexPointerf(self.vertices - self.center)
            GL.glNormalPointerf(self.normals)

            # GL.glEnable(GL.GL_COLOR_MATERIAL)
            # draw wireframe
            # GL.glColor4f(0, 0.6, 0, 1)
            # GL.glLineWidth(3)
            # GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)
            # GL.glDrawElementsui(GL.GL_TRIANGLES, self.indices)

            # draw lighted
            GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_FILL)

            GL.glEnable(GL.GL_LIGHTING)
            GL.glEnableClientState(GL.GL_NORMAL_ARRAY)

            GL.glColorMaterial(GL.GL_FRONT_AND_BACK, GL.GL_AMBIENT_AND_DIFFUSE)
            GL.glEnable(GL.GL_COLOR_MATERIAL)

            GL.glColor4f(0, 1, 0, 1)
            GL.glDrawElementsui(GL.GL_TRIANGLES, self.indices)

            GL.glDisable(GL.GL_COLOR_MATERIAL)
            GL.glDisableClientState(GL.GL_NORMAL_ARRAY)
            GL.glDisable(GL.GL_POLYGON_OFFSET_FILL)

        # gen 1 color per polygon
        if len(self.colors) < len(self.polygons_vertices):
            self.colors = []
            spacing = 1.0 / len(self.polygons_vertices)
            for i in range(0, len(self.polygons_vertices)):
                self.colors += [self._color(i * spacing)]

        if len(self.polygons_vertices) > 0:
            GL.glDisable(GL.GL_LIGHTING)

            for polygon in self.polygons_vertices:
                p = np.array(polygon)
                GL.glVertexPointerf(p - self.center)
                indices = [i for i in range(0, len(p))]

                # draw poly
                GL.glColor4fv(
                    self.polygons_colors[self.polygons_vertices.index(
                        polygon)])
                GL.glDrawElementsui(GL.GL_TRIANGLE_STRIP, indices)

                GL.glColor4f(0.9, 0.8, 0.1, 1)
                # draw generatrices
                GL.glDrawElementsui(GL.GL_LINES, indices)

            for polygon in self.polygons_vertices:
                p = np.array(polygon)
                GL.glVertexPointerf(p - self.center)
                indice_lines = []
                for i in range(0, len(p), 2):
                    indice_lines += [i]
                for i in range(len(p)-1, 0, -2):
                    indice_lines += [i]

                indice_lines += [0]

                GL.glLineWidth(2)

                GL.glColor4f(1.0, 1.0, 1.1, 1)
                # draw generatrices
                GL.glDrawElementsui(GL.GL_LINE_STRIP, indice_lines)

        if not (self.section_vertices is None):
            GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
            GL.glPolygonOffset(5, 5)
            GL.glDisable(GL.GL_COLOR_MATERIAL)
            GL.glDisable(GL.GL_LIGHTING)
            GL.glEnable(GL.GL_BLEND)
            GL.glColor4fv([0.6, 0.2, 0.2, 0.7])
            GL.glVertexPointerf(self.section_vertices - self.center)
            GL.glDrawArrays(
                GL.GL_TRIANGLE_STRIP, 0, len(self.section_vertices))
            GL.glDisable(GL.GL_BLEND)
            GL.glEnable(GL.GL_COLOR_MATERIAL)
            GL.glPolygonOffset(0, 0)
            GL.glDisable(GL.GL_POLYGON_OFFSET_FILL)

        if not (self.graph_vertices is None):
            pass
            GL.glDisable(GL.GL_LIGHTING)
            # glDisable(GL_DEPTH_TEST)
            GL.glEnableClientState(GL.GL_COLOR_ARRAY)
            GL.glVertexPointerf(self.graph_vertices - self.center)
            GL.glColorPointerf(self.graph_colors)
            GL.glLineWidth(1)
            GL.glDrawElementsui(GL.GL_LINES, self.graph_indices)
            GL.glPointSize(4)
            GL.glDisableClientState(GL.GL_COLOR_ARRAY)
