# coding: utf-8

from math import sqrt
import logging

# from qgis.core import QgsWKBTypes # unable to import QgsWKBTypes otherwize (quid?)
from qgis.core import QGis, QgsGeometry, QgsRectangle
from qgis.gui import (QgsApplication, QgsMapCanvas, QgsMapToolPan,
                      QgsMapToolZoom, QgsRubberBand)

from PyQt4.QtGui import QColor, QMessageBox

from .action_state_helper import ActionStateHelper


class Canvas(QgsMapCanvas):
    def __init__(self, section, iface, parent=None):
        QgsMapCanvas.__init__(self, parent)
        self.setWheelAction(QgsMapCanvas.WheelZoomToMouseCursor)
        self.setCrsTransformEnabled(False)

        self.__iface = iface
        self.__highlighter = None
        self.__section = section
        self.__z_auto_scale_enabled = False

        section.changed.connect(self.__define_section_line)

        self.extentsChanged.connect(self.__extents_changed)
        iface.mapCanvas().extentsChanged.connect(self.__extents_changed)
        self.__iface.layerTreeView().currentLayerChanged.connect(self.setCurrentLayer)
        self.currentLayerChanged.connect(self.__update_layer_action_states)

    def unload(self):
        self.__iface.layerTreeView().currentLayerChanged.disconnect(self.setCurrentLayer)
        self.__cleanup()
        self.section_actions = []

    def build_default_section_actions(self):
        return [
            { 'icon': QgsApplication.getThemeIcon('/mActionPan.svg'), 'label': 'pan', 'tool': QgsMapToolPan(self) },
            { 'icon': QgsApplication.getThemeIcon('/mActionZoomIn.svg'), 'label': 'zoom in', 'tool': QgsMapToolZoom(self, False) },
            { 'icon': QgsApplication.getThemeIcon('/mActionZoomOut.svg'), 'label': 'zoom out', 'tool': QgsMapToolZoom(self, True) }
        ]

    def add_section_actions_to_toolbar(self, actions, toolbar):
        self.section_actions = []

        for action in actions:
            if action is None:
                toolbar.addSeparator()
                continue

            act = toolbar.addAction(action['icon'], action['label']) if 'icon' in action else toolbar.addAction(action['label'])

            if 'tool' in action:
                act.setCheckable(True)
                act.setData(action['tool'])
                act.triggered.connect(self._setSectionCanvasTool)
            elif 'clicked' in action:
                act.setCheckable('layer_state' in action)
                act.triggered.connect(action['clicked'])

            action['action'] = act
            self.section_actions += [ action ]

            if 'precondition' in action:
                h = ActionStateHelper(act)
                h.add_is_enabled_test(action['precondition'])
                h.update_state()

    def _setSectionCanvasTool(self, checked):
        if not checked:
            return

        tool = self.sender().data()
        self.setMapTool(tool)

        for action in self.section_actions:
            if 'tool' in action:
                action['action'].setChecked(tool == action['tool'])

    def __cleanup(self):
        if self.__highlighter is not None:
            self.__iface.mapCanvas().scene().removeItem(self.__highlighter)
            self.__highlighter = None
            self.__iface.mapCanvas().refresh()

    def __define_section_line(self, line_wkt, width):
        self.__cleanup()
        if not line_wkt:
            return
        self.__highlighter = QgsRubberBand(self.__iface.mapCanvas(), QGis.Line)
        self.__highlighter.addGeometry(QgsGeometry.fromWkt(line_wkt), None) # todo use section.line
        self.__highlighter.setWidth((2 * width) / self.__iface.mapCanvas().getCoordinateTransform().mapUnitsPerPixel())
        color = QColor(255, 0, 0, 128)
        self.__highlighter.setColor(color)

        if not len(self.layers()):
            return
        min_z = min((layer.extent().yMinimum() for layer in self.layers()))
        max_z = max((layer.extent().yMaximum() for layer in self.layers()))
        z_range = max_z - min_z
        self.setExtent(QgsRectangle(0, min_z - z_range * 0.1, self.__section.line.length, max_z + z_range * 0.1))

        if self.__z_auto_scale_enabled:
            self.z_autoscale(True)
        else:
            self.refresh()

    def z_autoscale(self, enabled):
        self.__z_auto_scale_enabled = enabled
        ext = self.extent()
        smin, smax = ext.xMinimum(), ext.xMaximum()
        ztmin, ztmax = self.__section.z_range(smin, smax)
        logging.debug('z range {};{}'.format(ztmin, ztmax))
        if ztmin == ztmax:
            return
        dzt = ztmax - ztmin

        zmin, zmax = ext.yMinimum(), ext.yMaximum()
        logging.debug('ext {} {} {} {}'.format(smin, zmin, smax, zmax))
        dz = zmax - zmin
        fct = 1.0 if not enabled else abs(dz/dzt)
        self.__section.set_z_scale(fct)
        logging.debug('new ext  {} {} {} {}'.format(smin, ztmin, smax, ztmax))
        logging.debug('scaling by {}'.format(fct))
        self.setExtent(QgsRectangle(smin, ztmin*fct, smax, ztmax*fct))
        self.refresh()

    def __extents_changed(self):
        if not self.__section.is_valid:
            return

        ext = self.extent()

        line = QgsGeometry.fromWkt(self.__section.line.wkt)

        # section visibility bounds
        start = max(0, ext.xMinimum())
        end = start + min(line.length(), ext.width())

        vertices = [line.interpolate(start).asPoint()]
        vertex_count = len(line.asPolyline())
        distance = 0

        for i in range(1, vertex_count):
            vertex_i = line.vertexAt(i)
            distance += sqrt(line.sqrDistToVertexAt(vertex_i, i-1))
            # 2.16 distance = line.distanceToVertex(i)

            if distance <= start:
                pass
            elif distance < end:
                vertices += [vertex_i]
            else:
                break

        vertices += [line.interpolate(end).asPoint()]

        if self.__highlighter is not None:
            self.__highlighter.reset()
            self.__highlighter.addGeometry(QgsGeometry.fromPolyline(vertices), None)
            self.__highlighter.setWidth((2.0 * self.__section.width)/self.__iface.mapCanvas().getCoordinateTransform().mapUnitsPerPixel())

    def __toggle_edit(self, checked):
        #TODO: simplistic implementation. Would be nice to be able to use QgisApp::toggleEditing( QgsMapLayer *layer, bool allowCancel)
        currentLayer = self.currentLayer()

        if currentLayer is None:
            self.__update_layer_action_states()
        else:
            if checked:
                if not currentLayer.isReadOnly():
                    currentLayer.startEditing()
            else:
                if currentLayer.isModified():
                    res = QMessageBox.information(None, "Stop editing", "Do you want to save the changes to layer {}?".format(currentLayer.name()), QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)

                    if res == QMessageBox.Cancel:
                        return
                    elif res == QMessageBox.Discard:
                        currentLayer.rollBack()
                        currentLayer.triggerRepaint()
                    else:
                        currentLayer.commitChanges()
                else:
                    currentLayer.rollBack()



    def __update_layer_action_states(self):
        currentLayer = self.currentLayer()

        for action in self.section_actions:
            if 'layer_state' in action:
                action['action'].setChecked(False if currentLayer is None else action['layer_state'](currentLayer))
