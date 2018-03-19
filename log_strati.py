# coding=utf-8

from qgis.core import QgsDataSourceURI

from PyQt4 import uic
from PyQt4.QtGui import QGraphicsScene, QImage, QPixmap, QMainWindow, QBrush, QColor, QWheelEvent, QPen
from PyQt4.QtCore import Qt, QObject

from shapely import wkb
import os
from builtins import bytes

class BoreHoleScene(QGraphicsScene):

    def __init__(self, project, parent=None):
        super(BoreHoleScene, self).__init__(parent)
        self.__project = project
        self.__id = None
        self.m_per_pixel = -.2

        self.__redraw = True

    def texture(self, code):
        fil = os.path.join(os.path.dirname(__file__), 'symbologie', code+'.svg')
        if os.path.exists(fil):
            return QImage(fil)
        else:
            return QImage()

    def formation_color(self, code):
        color = {
                300: QColor(150, 50, 50),
                310: QColor(100, 50, 50),
                320: QColor(150, 50, 50),
                340: QColor(200, 50, 50),
                400: QColor(150, 100, 50)
                }
        col = color[code] if code in color else QColor(150, 150, 150)
        return col

    def set_m_per_pixel(self, m_per_pixel):
        self.m_per_pixel = m_per_pixel
        self.__redraw = True
        self.invalidate()

    def set_current_id(self, id_):
        self.__id = id_
        self.__redraw = True
        self.invalidate()

    def drawForeground(self, painter, rect):
        #print "BoreHoleScene.drawForeground"
        if self.__redraw:
            with self.__project.connect() as con:
                cur = con.cursor()
                self.__redraw = False
                self.clear()
                fm = painter.fontMetrics();

                if self.__id is None:
                    QGraphicsScene.drawForeground(self, painter, rect)
                    return
                
                cur.execute("SELECT geom FROM albion.hole WHERE id='{}'".format(self.__id))
                res = cur.fetchone()

                if not res:
                    QGraphicsScene.drawForeground(self, painter, rect)
                    return

                hole = wkb.loads(bytes.fromhex(res[0]))
                line = [p[2] for p in hole.coords]
                tick_width = 20
                spacing = 5
                tick_text_offset = -10
                tabs = [50, 75, 150, 250, 350, 400, 500]
                zmin, zmax = min(line), max(line)
                zpmin, zpmax = 0, ((zmin-zmax)-5)/self.m_per_pixel

                text = self.addText(self.__id)
                text.setPos(tabs[1], -5*fm.height())

                label = 'Depth [m]'
                text = self.addText(label)
                text.setRotation(-90)
                text.setPos(0, 0)
                text = self.addText('Formation')
                text.setPos(tabs[1], -3*fm.height())
                text = self.addText('Radiometry')
                text.setPos(tabs[2], -3*fm.height())
                text = self.addText('Resistivity')
                text.setPos(tabs[3], -3*fm.height())
                text = self.addText('Mineralization')
                text.setPos(tabs[4], -3*fm.height())

                top = zpmin-3*fm.height()
                pen = QPen()
                pen.setWidth(3)
                for tab in [tabs[1], tabs[2], tabs[3], tabs[4], tabs[6]]:
                    self.addLine(tab, top, tab, zpmax, pen)
                self.addLine(tabs[1], zpmin, tabs[-1], zpmin, pen)
                self.addLine(tabs[1], zpmax, tabs[-1], zpmax, pen)
                self.addLine(tabs[1], top, tabs[-1], top, pen)

                # depth ticks
                for z in range(0, int(-(zmax-zmin)-5), -10):
                    text = "% 4.0f"%(max(line)+z)
                    z /= self.m_per_pixel
                    width = fm.width(text);
                    text = self.addText(text)
                    text.setPos(tabs[0]-width-spacing, tick_text_offset+int(z))
                    self.addLine(tabs[0], z, tabs[1], z)
                    self.addLine(tabs[2], z, tabs[4], z)

                #res = cur.execute("SELECT AsText(GEOMETRY), code FROM lithologies WHERE forage={}".format(self.__id)).fetchall()

                ## litho image
                #for geom, code in res:
                #    line = [(float(pt.split()[2])-z_tube+h_tube_sol)
                #            for pt in geom.replace('LINESTRING Z(','').replace(')','').split(',')]
                #    z_start = line[0]/self.m_per_pixel
                #    z_end = line[-1]/self.m_per_pixel
                #    brush = QBrush()
                #    brush.setTextureImage(self.texture(code))
                #    self.addRect(tabs[1], z_start, tabs[2]-tabs[1], z_end-z_start, brush=brush)

                ## bar diagram grid
                #for i in range(1, 10):
                #    pen.setWidth(1 if i != 5 else 2)
                #    x = tabs[3]+(tabs[4]-tabs[3])*float(i)/10
                #    self.addLine(x, zmin, x, zmax, pen)

                # formation color
                cur.execute("SELECT geom, code FROM albion.formation WHERE hole_id='{}'".format(self.__id))

                for geom, code in cur.fetchall():
                    line = [p[2] for p in wkb.loads(bytes.fromhex(geom)).coords]
                    z_start = (line[0]-zmax)/self.m_per_pixel
                    z_end = (line[-1]-zmax)/self.m_per_pixel
                    brush = QBrush()
                    brush.setStyle(Qt.SolidPattern)
                    brush.setColor(self.formation_color(code))
                    self.addRect(tabs[1], z_start, tabs[2]-tabs[1], z_end-z_start, brush=brush)
                    #width = fm.width(code);
                    #text = self.addText(code)
                    #text.setPos(tabs[2]+spacing, tick_text_offset+int(.5*(z_start+z_end)))
                    self.addLine(tabs[2], z_start, tabs[2], z_start)
                    self.addLine(tabs[2], z_end, tabs[2], z_end)

                # radiometry diagram
                cur.execute("SELECT max(gamma) FROM albion.radiometry WHERE hole_id='{}'".format(self.__id))
                gamma_max = cur.fetchone()[0]
                cur.execute("SELECT geom, gamma FROM albion.radiometry WHERE hole_id='{}' AND gamma>=0".format(self.__id))
                for geom, gamma in cur.fetchall():
                    line = [p[2] for p in wkb.loads(bytes.fromhex(geom)).coords]
                    z_start = (line[0]-zmax)/self.m_per_pixel
                    z_end = (line[-1]-zmax)/self.m_per_pixel
                    brush = QBrush()
                    brush.setStyle(Qt.SolidPattern)
                    brush.setColor(QColor(55, 51, 149))
                    self.addRect(tabs[2], z_start, (tabs[3]-tabs[2])*gamma/gamma_max, z_end-z_start, pen=QPen(Qt.NoPen), brush=brush)

                # resistivity diagram
                cur.execute("SELECT max(rho) FROM albion.resistivity WHERE hole_id='{}'".format(self.__id))
                rho_max = cur.fetchone()[0]
                cur.execute("SELECT geom, rho FROM albion.resistivity WHERE hole_id='{}' AND rho>=0".format(self.__id))
                for geom, rho in cur.fetchall():
                    line = [p[2] for p in wkb.loads(bytes.fromhex(geom)).coords]
                    z_start = (line[0]-zmax)/self.m_per_pixel
                    z_end = (line[-1]-zmax)/self.m_per_pixel
                    brush = QBrush()
                    brush.setStyle(Qt.SolidPattern)
                    brush.setColor(QColor(155, 51, 49))
                    self.addRect(tabs[3], z_start, (tabs[4]-tabs[3])*rho/rho_max, z_end-z_start, pen=QPen(Qt.NoPen), brush=brush)

                # mineralization
                cur.execute("SELECT geom, oc, accu, grade FROM albion.mineralization WHERE hole_id='{}'".format(self.__id))

                for geom, oc, accu, grade in cur.fetchall():
                    line = [p[2] for p in wkb.loads(bytes.fromhex(geom)).coords]
                    z_start = (line[0]-zmax)/self.m_per_pixel
                    z_end = (line[-1]-zmax)/self.m_per_pixel
                    brush = QBrush()
                    brush.setStyle(Qt.SolidPattern)
                    brush.setColor(QColor(250, 250, 50))
                    self.addRect(tabs[4], z_start, tabs[5]-tabs[4], z_end-z_start, brush=brush)
                    txt = "oc="+str(oc)+"\naccu="+str(accu)+"\ngrade="+str(grade)
                    width = fm.width(txt);
                    text = self.addText(txt)
                    text.setPos(tabs[5]+spacing, -int(1.5*fm.height())+int(.5*(z_start+z_end)))
                    self.addLine(tabs[4], z_start, tabs[6], z_start)
                    self.addLine(tabs[4], z_end, tabs[6], z_end)



                self.setSceneRect(self.itemsBoundingRect())

        QGraphicsScene.drawForeground(self, painter, rect)
            
    class ScrollFilter(QObject):
        def __init__(self, parent):
            super(BoreHoleScene.ScrollFilter, self).__init__(parent)

        def eventFilter(self, obj, event):
            if isinstance(event, QWheelEvent): 
                if event.delta() < 0:
                    self.parent().set_m_per_pixel(self.parent().m_per_pixel*1.2)
                else:
                    self.parent().set_m_per_pixel(self.parent().m_per_pixel*0.8)
            return False

    def scroll_filter(self):
        self.__scroll_filter = BoreHoleScene.ScrollFilter(self)
        return self.__scroll_filter

class BoreHoleWindow(QMainWindow):

    def __init__(self, conn_info, parent=None):
        super(BoreHoleWindow, self).__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'log_strati.ui'), self)
        self.scene = BoreHoleScene(conn_info, self)
        self.graphicsView.setScene(self.scene)
        self.graphicsView.installEventFilter(self.scene.scroll_filter())


    #    id_, = cur.execute("SELECT OGC_FID FROM forages WHERE nom='{}'".format(name)).fetchone()

if __name__=='__main__':
    import sys
    from PyQt4.QtCore import QSettings
    from PyQt4.QtGui import QApplication

    QApplication.setOrganizationName("QGIS")
    QApplication.setOrganizationDomain("qgis.org")
    QApplication.setApplicationName("QGIS2")

    app = QApplication(sys.argv)


    view = BoreHoleWindow(sys.argv[1])
    view.scene.set_current_id(sys.argv[2])
    view.show()

    app.exec_()

    

