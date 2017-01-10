# coding=utf-8

from qgis.core import *
from qgis.gui import *
import logging

def is_layer_projected_in_section(layer_id, section_id):
    layers = QgsMapLayerRegistry.instance().mapLayers()

    for layer in layers:
        if layers[layer].customProperty("section_id") == section_id and layers[layer].customProperty("projected_layer") == layer_id:
            return True
    return False


def projected_layer_to_original(layer, custom_property="projected_layer"):
    return None if layer is None else QgsMapLayerRegistry.instance().mapLayer(layer.customProperty(custom_property))

def projected_feature_to_original(source_layer, feature):
    # needed so we can use attribute(name)
    feature.setFields(source_layer.fields(), False)
    source_id = feature.attribute("id")

    try:
        it = source_layer.getFeatures(
                QgsFeatureRequest().setFilterExpression ( u'"id" = {0}'.format(source_id)))
        return it.next()
    except Exception as e:
        logging.error('Failed to lookup id {} in layer {}'.format(source_id, source_layer.id()))
        return None


