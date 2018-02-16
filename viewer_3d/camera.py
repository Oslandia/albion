# -*- coding: UTF-8 -*-

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QVector3D

class Camera(object):
    "a simple camera"
    def __init__(self, eye, at, up=QVector3D(0, 0, 1)):
        self.at0 = QVector3D(at)
        self.eye0 = QVector3D(eye)
        self.up0 = QVector3D(up)
        self.reset()

    def reset(self, other=None):
        if other is None:
            self.at = QVector3D(self.at0)
            self.eye = QVector3D(self.eye0)
            self.up = QVector3D(self.up0)
        else:
            self.at = other.at
            self.eye = other.eye
            self.up = other.up

    def move(self, delta_x, delta_y, buttons, modifiers):
        # user is dragging
        to = (self.at - self.eye)
        distance = to.length()
        if int(buttons) & Qt.LeftButton:
            right = QVector3D.crossProduct(to, self.up)
            right = right.normalized()
            up = QVector3D.crossProduct(right, to).normalized()
            translation = right*(delta_x*distance)\
                        + up*(delta_y*distance)
            self.eye -= translation*5
            # correct eye position to maintain distance
            to = (self.at - self.eye)
            self.eye = self.at - to.normalized()*distance
            self.up = QVector3D.crossProduct(right, to).normalized()

       
        elif int(buttons) & Qt.MiddleButton:
            right = QVector3D.crossProduct(to, self.up).normalized()
            up = QVector3D.crossProduct(right, to).normalized()
            translation = right*(delta_x*distance)\
                        + up*(delta_y*distance)
            self.at -= translation
            self.eye -= translation

        elif  int(buttons) & Qt.RightButton :
            translation = to*delta_y
            self.eye -= translation

