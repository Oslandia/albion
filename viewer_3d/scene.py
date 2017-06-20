# -*- coding: UTF-8 -*-

import numpy
from OpenGL.GL import *
from OpenGL.GL import shaders

from PyQt4.QtGui import *
from PyQt4.QtCore import *

from .utility import computeNormals
import psycopg2
from shapely import wkb

class Scene(QObject):
    
    def __del__(self):
        self.__con.close()

    def __init__(self, conn_info, graph_id, param, texture_binder, parent=None):
        super(Scene, self).__init__(parent)
        self.__zScale = 1. # must be one here
        self.__textureBinder = texture_binder
        self.__old_param = {
                "label": False,
                "node": False,
                "edge": False,
                "top": False,
                "bottom": False,
                "section": False,
                "volume": False,
                "z_scale": 1
                }
        self.__param = param

        self.graph_id = graph_id
        self.conn_info = conn_info

        self.__con = psycopg2.connect(self.conn_info)
        self.__cur = self.__con.cursor()
        self.__cur.execute("""
            select st_3dextent(geom)
            from albion.collar
            """)

        ext = self.__cur.fetchone()[0].replace('BOX3D(','').replace(')','').split(',')
        ext = [[float(c) for c in ext[0].split()],[float(c) for c in ext[1].split()]]
        self.extent = (ext[0][0], ext[0][1], ext[1][0], ext[1][1])

        self.center = QVector3D(
                .5*(ext[0][0]+ext[1][0]), 
                .5*(ext[0][1]+ext[1][1]),
                .5*(ext[0][2]+ext[1][2]))

        self.vtx = {
                "node":None,
                "edge":None,
                "top":None,
                "bottom":None,
                "section":None,
                "volume":None}
        self.idx = {
                "node":None,
                "edge":None,
                "top":None,
                "bottom":None,
                "section":None,
                "volume":None}
        self.nrml = {
                "section":None,
                "volume":None}

        self.__labels = []


    def rendergl(self, leftv, upv, eye, height, context):

        glEnable(GL_DEPTH_TEST)
        glLightModelfv(GL_LIGHT_MODEL_TWO_SIDE, GL_TRUE)
        glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT,  [1., 1., 1., 1.])
        glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE,  [1., 1., 1., 1.])
        glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, [1., 1., 1., 1.])
        glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 50)

        glEnableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glEnableClientState(GL_NORMAL_ARRAY)

        if self.__param["z_scale"] != self.__old_param["z_scale"]:
            self.setZscale(self.__param["z_scale"])

        for layer in ['section', 'volume']:
            if self.__param[layer]:
                if self.__param[layer] != self.__old_param[layer]:
                    self.__update(layer)
                if len(self.vtx[layer]):
                    glVertexPointerf(self.vtx[layer])
                    glNormalPointerf(self.nrml[layer])
                    glDrawElementsui(GL_TRIANGLES, self.idx[layer])

        glDisableClientState(GL_NORMAL_ARRAY)
        color = {'node':[0.,0.,0.,1.], 
                  'edge':[0.,1.,0.,1.],
                  'top':[0.,1.,1.,1.],
                  'bottom':[1.,0.,0.,1.]
                  }
        glLineWidth(1)
        for layer in ['node', 'edge', 'top', 'bottom']:
            if self.__param[layer]:
                if self.__param[layer] != self.__old_param[layer]:
                    self.__update(layer)
                glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT,  color[layer])
                glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION,  color[layer])
                glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE,  color[layer])
                if len(self.vtx[layer]):
                    glVertexPointerf(self.vtx[layer])
                    glDrawElementsui(GL_LINES, self.idx[layer])
        
        # current section, highlight nodes
        self.__cur.execute("""
            select coalesce(st_collect(n.geom), 'GEOMETRYCOLLECTION EMPTY'::geometry)
            from albion.node as n join albion.hole as h on h.id=n.hole_id, albion.grid as s
            where n.graph_id='{}'
            and s.id = albion.current_section_id()
            and h.geom && s.geom
            and st_intersects(st_startpoint(h.geom), s.geom)
            """.format(self.graph_id)
            )
        lines = wkb.loads(self.__cur.fetchone()[0], True)
        vtx = []
        idx = []
        for line in lines:
            idx += [(i, i+1) for i in range(len(vtx), len(vtx)+len(line.coords)-1)]
            vtx += list(line.coords)
        vtx = numpy.array(vtx, dtype=numpy.float32)
        if len(vtx):
            vtx[:,2] *= self.__zScale
        idx = numpy.array(idx, dtype=numpy.int32)
        glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT,  [1., 1., 0., 1.])
        glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE,  [1., 1., 0., 1.])
        glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION,  [1., 1., 0., 1.])
        glDisable(GL_DEPTH_TEST)
        glLineWidth(4)
        glPointSize(4)
        if len(vtx):
            glVertexPointerf(vtx)
            glDrawElementsui(GL_LINES, idx)
            glDrawArrays(GL_POINTS, 0, len(vtx))


        glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION,  [0., 0., 0., 1.])

        # render labels
        if self.__param['label']:
            if self.__param['label'] != self.__old_param['label']:
                self.__update('label')
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glDisableClientState(GL_VERTEX_ARRAY)
            glDisableClientState(GL_NORMAL_ARRAY)
            glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            glDisable(GL_LIGHTING)
            glDisable(GL_COLOR_MATERIAL)
            glDisable(GL_LIGHT0)
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_TEXTURE_2D)
            for scatter in self.__labels:
                pt = scatter['point']
                point = QVector3D(pt[0], pt[1], pt[2])
                glColor4f(0, 0, 0, 1)
                glPointSize(4)
                glBegin(GL_POINTS)
                glVertex3f(point.x(), point.y(), point.z())
                glEnd()

            glEnable(GL_TEXTURE_2D)
            for scatter in self.__labels:
                pt = scatter['point']
                point = QVector3D(pt[0], pt[1], pt[2])
                dist = .8*(point-eye).length()/height
                w = dist*scatter['image'].width()
                h = dist*scatter['image'].height()
                glBindTexture(GL_TEXTURE_2D, scatter['texture'])
                glColor4f(1, 1, 1, 1);
                glBegin(GL_QUADS)
                glNormal3f(0, 0, 1)
                glTexCoord2f(0, 0)
                glVertex3f(point.x(), point.y(), point.z())
                point -= leftv*w
                glNormal3f(0, 0, 1)
                glTexCoord2f(1, 0)
                glVertex3f(point.x(), point.y(), point.z())
                point += upv*h
                glNormal3f(0, 0, 1)
                glTexCoord2f(1, 1)
                glVertex3f(point.x(), point.y(), point.z())
                point += leftv*w
                glNormal3f(0, 0, 1)
                glTexCoord2f(0, 1)
                glVertex3f(point.x(), point.y(), point.z())
                glEnd()
            glDisable(GL_TEXTURE_2D)

    def __update(self, layer):

        if layer=='label':
            self.__labels = []
            self.__cur.execute("""
                select hole_id, st_x(geom), st_y(geom), st_z(geom)
                from (select hole_id, st_startpoint(geom) as geom from albion.node where graph_id='{}' ) as t
                """.format(self.graph_id))
            for id_, x, y, z in self.__cur.fetchall():
                scene = QGraphicsScene()
                scene.setSceneRect(scene.itemsBoundingRect())
                scene.addText(id_)#, QFont('Arial', 32))
                image = QImage(scene.sceneRect().size().toSize(), QImage.Format_ARGB32)
                image.fill(Qt.transparent)
                painter = QPainter(image)
                image.save('/tmp/test.png')
                scene.render(painter)
                del painter
                scat = {'point': [x,y,self.__zScale], 'image': image}
                scat['texture'] = self.__textureBinder(scat['image'])
                self.__labels.append(scat)

        elif layer=='node':
            self.__cur.execute("""
                select coalesce(st_collect(geom), 'GEOMETRYCOLLECTION EMPTY'::geometry) from albion.node where graph_id='{}'
                """.format(self.graph_id))
            lines = wkb.loads(self.__cur.fetchone()[0], True)
            vtx = []
            idx = []
            for line in lines:
                idx += [(i, i+1) for i in range(len(vtx), len(vtx)+len(line.coords)-1)]
                vtx += list(line.coords)
            self.vtx[layer] = numpy.array(vtx, dtype=numpy.float32)
            if len(vtx):
                self.vtx[layer][:,2] *= self.__zScale
            self.idx[layer] = numpy.array(idx, dtype=numpy.int32)

        elif layer=='edge':
            self.__cur.execute("""
                select coalesce(st_collect(geom), 'GEOMETRYCOLLECTION EMPTY'::geometry) from albion.edge where graph_id='{}'
                """.format(self.graph_id))
            lines = wkb.loads(self.__cur.fetchone()[0], True)
            vtx = []
            idx = []
            for line in lines:
                idx += [(i, i+1) for i in range(len(vtx), len(vtx)+len(line.coords)-1)]
                vtx += list(line.coords)
            self.vtx[layer] = numpy.array(vtx, dtype=numpy.float32)
            if len(vtx):
                self.vtx[layer][:,2] *= self.__zScale
            self.idx[layer] = numpy.array(idx, dtype=numpy.int32)
        
        elif layer=='top':
            self.__cur.execute("""
                select coalesce(st_collect(top), 'GEOMETRYCOLLECTION EMPTY'::geometry) from albion.edge where graph_id='{}'
                """.format(self.graph_id))
            lines = wkb.loads(self.__cur.fetchone()[0], True)
            vtx = []
            idx = []
            for line in lines:
                idx += [(i, i+1) for i in range(len(vtx), len(vtx)+len(line.coords)-1)]
                vtx += list(line.coords)
            self.vtx[layer] = numpy.array(vtx, dtype=numpy.float32)
            if len(vtx):
                self.vtx[layer][:,2] *= self.__zScale
            self.idx[layer] = numpy.array(idx, dtype=numpy.int32)

        elif layer=='bottom':
            self.__cur.execute("""
                select coalesce(st_collect(bottom), 'GEOMETRYCOLLECTION EMPTY'::geometry) from albion.edge where graph_id='{}'
                """.format(self.graph_id))
            lines = wkb.loads(self.__cur.fetchone()[0], True)
            vtx = []
            idx = []
            for line in lines:
                idx += [(i, i+1) for i in range(len(vtx), len(vtx)+len(line.coords)-1)]
                vtx += list(line.coords)
            self.vtx[layer] = numpy.array(vtx, dtype=numpy.float32)
            if len(vtx):
                self.vtx[layer][:,2] *= self.__zScale
            self.idx[layer] = numpy.array(idx, dtype=numpy.int32)

        elif layer=='section':
            self.__cur.execute("""
                select coalesce(st_collectionhomogenize(st_collect(triangulation)), 'GEOMETRYCOLLECTION EMPTY'::geometry)
                from albion.section where graph_id='{}'
                """.format(self.graph_id))
            geom = wkb.loads(self.__cur.fetchone()[0], True)
            self.vtx[layer] = numpy.require(numpy.array([tri.exterior.coords[:-1] for tri in geom]).reshape((-1,3)), numpy.float32, 'C')
            if len(self.vtx[layer]):
                self.vtx[layer][:,2] *= self.__zScale
            self.idx[layer] = numpy.require(numpy.arange(len(self.vtx[layer])).reshape((-1,3)), numpy.int32, 'C')
            self.nrml[layer] = computeNormals(self.vtx[layer], self.idx[layer])

        elif layer=='volume':
            self.__cur.execute("""
                select coalesce(st_collectionhomogenize(st_collect(triangulation)), 'GEOMETRYCOLLECTION EMPTY'::geometry)
                from albion.volume where graph_id='{}'
                """.format(self.graph_id))
            geom = wkb.loads(self.__cur.fetchone()[0], True)
            self.vtx[layer] = numpy.require(numpy.array([tri.exterior.coords[:-1] for tri in geom]).reshape((-1,3)), numpy.float32, 'C')
            if len(self.vtx[layer]):
                self.vtx[layer][:,2] *= self.__zScale
            self.idx[layer] = numpy.require(numpy.arange(len(self.vtx[layer])).reshape((-1,3)), numpy.int32, 'C')
            self.nrml[layer] = computeNormals(self.vtx[layer], self.idx[layer])

        self.__old_param[layer] = self.__param[layer]


    def setZscale(self, scale):
        factor = float(scale)/self.__zScale

        for layer in ['node', 'edge', 'top', 'bottom', 'section', 'volume']:
            if self.vtx[layer] is not None:
                self.vtx[layer][:,2] *= factor
                if layer in ['section', 'volume']:
                    self.nrml[layer] = computeNormals(self.vtx[layer], self.idx[layer])

        for scatter in self.__labels:
            scatter['point'][2] *= factor

        self.__zScale = scale

