# coding=utf-8

from qgis.core import * # unable to import QgsWKBTypes otherwize (quid?)

from shapely.geometry import Point, LineString
from shapely.wkt import loads
from shapely.ops import transform

from .helpers import projected_feature_to_original
from operator import xor
import logging

def hasZ(layer):
    """test if layer has z, necessary because the wkbType returned by lyers in QGSI 2.16
    has lost the information

    note: we return True for a layer with no geometries
    """

    if not layer.isSpatial():
        return False
    for feat in layer.getFeatures():
        return QgsWKBTypes.hasZ(int(feat.geometry().wkbType()))
    return True

class Layer(object):
    def __init__(self, source_layer, projected_layer):
        self.source_layer = source_layer
        self.projected_layer = projected_layer
        assert hasZ(source_layer) # @todo remove this and configure attribute for z
        self.__points = None
        self.skip_selection_signal = False

    def apply(self, section, remove_all):
        "project source features on section plnae defined by line"

        projected = self.projected_layer

        if remove_all:
            projected.dataProvider().deleteFeatures(projected.allFeatureIds())

        if not section.is_valid:
            return None

        logging.debug('projecting {} (geom={})'.format(self.source_layer.name(), self.projected_layer.geometryType()))

        source = self.source_layer
        line = section.line
        features = []
        # square cap style for the buffer -> less points
        buf = line.buffer(section.width, cap_style=2)
        for feature in source.getFeatures():
            centroid = feature.geometry().boundingBox().center()
            if Point(centroid.x(), centroid.y()).intersects(buf):
                geom = feature.geometry()
                new_feature = QgsFeature(feature.id())
                new_feature.setGeometry(section.project(geom))
                new_feature.setAttributes(feature.attributes())
                features.append(new_feature)

        projected.beginEditCommand('layer projection')
        projected.dataProvider().addFeatures(features)
        projected.endEditCommand()
        projected.updateExtents()

    def propagateChangesToSourceLayer(self, section):

        edit = self.projected_layer.editBuffer()

        if edit is None:
            return

        logging.debug('{} will commit changes'.format(self.projected_layer.id()))
        self.source_layer.beginEditCommand('unproject transformation')

        for i in edit.changedGeometries():
            modified_feature = self.projected_layer.getFeatures(QgsFeatureRequest(i)).next()
            feature = projected_feature_to_original(self.source_layer, modified_feature)
            unprojected = section.unproject(edit.changedGeometries()[i])
            self.source_layer.dataProvider().changeGeometryValues({feature.id(): unprojected})

        self.source_layer.endEditCommand()
        self.source_layer.updateExtents()

    def synchronize_selection_source_to_proj(self, selected_ids):
        def ids_to_filter(ids):
            i = []
            for id_ in ids:
                i += [str(id_)]
            return i

        if self.skip_selection_signal:
            return

        self.skip_selection_signal = True

        logging.debug('>>> synchronize_selection_source_to_proj {}'.format(len(selected_ids)))
        if len(selected_ids) == 0:
            self.projected_layer.removeSelection()
        else:
            query = u"attribute($currentfeature, 'id') in ({}) OR attribute($currentfeature, 'id:Integer64(10,0)') in ({})".format(','.join(ids_to_filter(selected_ids)), ','.join(ids_to_filter(selected_ids)))
            # 2.16 layer.projected_layer.selectByExpression("attribute($currentfeature, query))

            features = self.projected_layer.getFeatures(QgsFeatureRequest().setFilterExpression(query))
            selected_ids = [f.id() for f in features]
            deselected_ids = filter(lambda i: not(i in selected_ids), self.projected_layer.selectedFeaturesIds())
            # Change selection in one call to no cause infinite ping-pong
            self.projected_layer.modifySelection(selected_ids, deselected_ids)

        logging.debug('<<< synchronize_selection_source_to_proj {}'.format(len(selected_ids)))
        self.skip_selection_signal = False

    def synchronize_selection_proj_to_source(self):
        if self.skip_selection_signal:
            return

        self.skip_selection_signal = True

        # sync selected items from layer_from in [layers_to]
        selected_ids = self.projected_layer.selectedFeaturesIds()
        source_selected_ids = self.source_layer.selectedFeaturesIds()

        select = []
        deselect = []

        for f in self.projected_layer.getFeatures():
            g = projected_feature_to_original(self.source_layer, f)

            is_selected_in_proj   = f.id() in selected_ids
            is_selected_in_source = g.id() in source_selected_ids

            if xor(is_selected_in_proj, is_selected_in_source):
                if is_selected_in_proj:
                    select += [g.id()]
                else:
                    deselect += [g.id()]

        logging.debug('>>> synchronize_selection_proj_to_source [{}] -> [{}, {}]'.format(len(selected_ids), len(select), len(deselect)))
        if len(select) > 0 or len(deselect) > 0:
            self.source_layer.modifySelection(select, deselect)
        logging.debug('<<< synchronize_selection_proj_to_source [{}] -> [{}, {}]'.format(len(selected_ids), len(select), len(deselect)))

        self.skip_selection_signal = False

