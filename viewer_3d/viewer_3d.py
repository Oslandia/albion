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


class SectionPolygons():
    def __init__(self):
        # list of polygons (polygon = list of vertices)
        self.define_raw_polygons(None)

    def define_raw_polygons(self, p):
        self.raw_polygons = p
        self.np_vertices = []
        self.indices = []

    def update(self, center):
        self.indices = []
        vertices = []

        if self.raw_polygons is None or len(self.raw_polygons) == 0:
            return

        for polygon in self.raw_polygons:
            count = len(vertices)
            if count > 0:
                # degenerate next triangle
                # [0, 1, 2] => [0, 1, 2, 2, 3]
                self.indices += [count - 1, count]

            for i in range(0, len(polygon)):
                self.indices += [count + i]

            vertices += polygon

        self.np_vertices = np.array(vertices) - center


class Generatrices():
    def __init__(self):
        self.layers_visibility = {}
        self.layers_color = {}
        self.layers_vertices = {}
        self.np_vertices = {}

    def define_layer_vertices(self, layer_id, vertices):
        self.layers_vertices[layer_id] = vertices
        if layer_id not in self.layers_visibility:
            self.layers_visibility[layer_id] = True
        if layer_id not in self.layers_color:
            self.layers_color[layer_id] = [0, 0, 0, 0]

    def set_layer_visibility(self, layer_id, visible):
        self.layers_visibility[layer_id] = visible

    def set_layer_color(self, layer_id, color):
        self.layers_color[layer_id] = color

    def is_layer_visible(self, layer_id):
        return self.layers_visibility[layer_id]

    def update(self, center):
        self.np_vertices = {}
        for layer_id in self.layers_vertices:
            self.np_vertices[layer_id] = np.array(
                self.layers_vertices[layer_id]) - center


class Data():
    def __init__(self):
        self.sections_polygons = [SectionPolygons(), SectionPolygons()]
        self.generatrices = Generatrices()

    # define 1 section polygons
    def set_section_polygons(self, idx, polygons):
        self.sections_polygons[idx].define_raw_polygons(polygons)

    def has_section_polygons(self, idx):
        return len(self.sections_polygons[idx].indices) > 0

    def section_indices(self, idx):
        return self.sections_polygons[idx].indices

    def section_vertices(self, idx):
        return self.sections_polygons[idx].np_vertices

    def update(self, center):
        self.sections_polygons[0].update(center)
        self.sections_polygons[1].update(center)

        self.generatrices.update(center)


class Viewer3D(QtOpenGL.QGLWidget):
    def __init__(self, parent=None):
        self.parent = parent
        QtOpenGL.QGLWidget.__init__(self, parent)
        self.camera = Camera()
        self.scale_z = 3.0
        self.center = [0, 0, 0]
        self.section_vertices = None

        self.enabled = False
        self.data = Data()

    def enable(self, center=None):
        if center:
            self.center = center
            logging.info('Enabled {}'.format(center))
        self.enabled = True

    # GL boiler-plate
    def initializeGL(self):
        self.qglClearColor(QColor(250, 250,  250))
        self.vertices = None

    def resizeGL(self, width, height):
        height = max(height, 1)
        GL.glViewport(0, 0, width, height)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        self.aspect = width / float(height)

        GLU.gluPerspective(45.0, self.aspect, 0.1, 1000.0)

    # input-handling
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

    # Data:
    #   - polygons
    def set_section_polygons(self, idx, polygons):
        self.data.set_section_polygons(idx, polygons)

    #   - generatrices
    def define_generatrices_vertices(self, layer_id, layers_vertices):
        self.data.generatrices.define_layer_vertices(layer_id, layers_vertices)

    def set_generatrices_visibility(self, layer_id, visible):
        self.data.generatrices.set_layer_visibility(layer_id, visible)

    def set_generatrices_color(self, layer_id, color):
        self.data.generatrices.set_layer_color(layer_id, color)

    def define_section_vertices(self, section_vertices):
        self.section_vertices = np.array(section_vertices)

    def updateVolume(self, vertices, volumes):
        if len(volumes) == 0:
            self.vertices = None
            return

        self.vertices = []

        indices = []
        for vol in volumes:
            for tri in vol:
                idx = len(self.vertices)
                self.vertices += [vertices[tri[i]] for i in range(0, 3)]
                indices += [[idx, idx+1, idx+2]]

        self.vertices = np.array(self.vertices)
        self.indices = np.array(indices)
        self.normals = self.computeNormals(self.vertices, self.indices)

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

    # Draw code
    def paintGL(self):
        if not self.enabled:
            return

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

        self.data.update(self.center)

        for layer_id in self.data.generatrices.np_vertices:
            # GL state
            GL.glLineWidth(2)

            if self.data.generatrices.is_layer_visible(layer_id):
                vertices = self.data.generatrices.np_vertices[layer_id]
                GL.glVertexPointerf(vertices)
                GL.glColor4fv(self.data.generatrices.layers_color[layer_id])
                GL.glDrawArrays(GL.GL_LINES, 0, len(vertices))

            # Restore GL state
            GL.glLineWidth(1)

        if not (self.vertices is None):
            GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
            GL.glPolygonOffset(-2, -2)

            GL.glVertexPointerf(self.vertices - self.center)
            GL.glNormalPointerf(self.normals)

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

        for idx in [0, 1]:
            # constants
            colors = [[1, 0, 0, 1], [0, 0, 1, 1]]

            # GL state
            GL.glDisable(GL.GL_LIGHTING)
            # GL.glPolygonMode(GL.GL_FRONT_AND_BACK, GL.GL_LINE)

            if self.data.has_section_polygons(idx):
                GL.glColor4fv(colors[idx])
                GL.glVertexPointerf(self.data.section_vertices(idx))
                GL.glDrawElementsui(GL.GL_TRIANGLE_STRIP,
                                    self.data.section_indices(idx))

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
