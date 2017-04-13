# coding: utf-8

"""
This file is the ony allowed to deal with QGIS data structure (Qgs*)
They can be used elsewhere, but only as opaque types
So basically `import qgis.*` should only appear here and in plugin.py

TODO: test this file using a file project
"""

from math import sqrt
import logging

from qgis.core import (QgsMapLayerRegistry,
                       QgsFeatureRequest,
                       QgsWKBTypes,
                       QgsRectangle,
                       QgsFeature,
                       QgsVectorLayer,
                       QGis,
                       QgsSingleSymbolRendererV2,
                       QgsFillSymbolV2,
                       QgsGeometry)

from shapely.wkt import loads
from shapely.geometry import Point


def layer_has_z(layer):
    """test if layer has z, necessary because the wkbType
    returned by lyers in QGSI 2.16 has lost the information

    note: we return True for a layer with no geometries
    """
    if not isinstance(layer, QgsVectorLayer):
        return False
    if not layer.isSpatial():
        return False
    for feat in layer.getFeatures():
        return QgsWKBTypes.hasZ(int(feat.geometry().wkbType()))
    return True


def is_layer_projected_in_section(layer_id, section_id):
    layers = QgsMapLayerRegistry.instance().mapLayers()
    for layer in layers:
        if (layers[layer].customProperty('section_id') == section_id and
                layers[layer].customProperty('projected_layer') == layer_id):
            return True
    return False


def is_a_projected_layer(layer):
    return layer.customProperty('section_id') is not None


def projected_layer_to_original(layer, custom_property='projected_layer'):
    return (None if layer is None else
            QgsMapLayerRegistry.instance().mapLayer(
                layer.customProperty(custom_property)))


def projected_feature_to_original(source_layer, feature):
    # needed so we can use attribute(name)
    link = get_feature_attribute_values(source_layer, feature, 'link')
    try:
        result = list(query_layer_features_by_attributes(
            source_layer, {'link': link}))
        return result[0]
    except Exception as e:
        logging.error('Failed to lookup link {} in layer {} [{}]'.format(
            link, source_layer.id(), e))
        return None


def get_intersecting_features(layer, feature):
    bbox = feature.geometry().boundingBox()
    return layer.getFeatures(QgsFeatureRequest(bbox))


def does_buffer_interesects_feature(buf, feature):
    bb = feature.geometry().boundingBox()
    feature_extents = loads('LINESTRING ({} {}, {} {})'.format(
        bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum()))
    return buf.intersects(feature_extents)


def intersect_linestring_layer_with_wkt(layer, wkt, buffer_width):
    """ Return all features from given layer that intersects with wkt """
    assert QgsWKBTypes.geometryType(
            int(layer.wkbType())) == QgsWKBTypes.LineGeometry

    line = loads(wkt.replace('Z', ' Z'))
    if not line.is_valid:
        logging.warning('Invalid feature geometry wkt={}'.format(wkt))
        return
    # square cap style for the buffer -> less points
    buf = line.buffer(buffer_width, cap_style=2)
    bbox = QgsRectangle(
        buf.bounds[0], buf.bounds[1], buf.bounds[2], buf.bounds[3])
    # request features inside bounding-box
    for feature in layer.getFeatures(QgsFeatureRequest(bbox)):
        if does_buffer_interesects_feature(buf, feature):
            yield feature


def intersect_point_layer_with_wkt(layer, wkt, buffer_width):
    """ Return all features from given layer that intersects with wkt """

    assert QgsWKBTypes.geometryType(
            int(layer.wkbType())) == QgsWKBTypes.PointGeometry

    line = loads(wkt.replace('Z', ' Z'))

    if not line.is_valid:
        logging.warning('Invalid feature geometry wkt={}'.format(wkt))
        return

    # square cap style for the buffer -> less points
    buf = line.buffer(buffer_width, cap_style=2)
    bbox = QgsRectangle(
        buf.bounds[0], buf.bounds[1], buf.bounds[2], buf.bounds[3])

    # request features inside bounding-box
    for feature in layer.getFeatures(QgsFeatureRequest(bbox)):
        p = feature.geometry().asPoint()
        if buf.contains(Point(p.x(), p.y())):
            yield feature


def intersect_features_with_wkt(layers_features, wkt, buffer_width):
    line = loads(wkt.replace('Z', ' Z'))
    if not line.is_valid:
        logging.warning('Invalid feature geometry wkt={}'.format(wkt))
        return
    # square cap style for the buffer -> less points
    buf = line.buffer(buffer_width, cap_style=2)
    # request features inside bounding-box
    for layer_id in layers_features:
        layer = get_layer_by_id(layer_id)
        for feature_id in layers_features[layer_id]:
            feature = get_feature_by_id(layer, feature_id)
            if does_buffer_interesects_feature(buf, feature):
                yield (layer_id, feature_id)


def clone_feature_with_geometry_transform(feature, transform_geom):
    clone = QgsFeature(feature)
    clone.setGeometry(transform_geom(QgsGeometry(feature.geometry())))
    return clone


def remove_features_from_layer(layer, feature_ids=None):
    ''' Remove features from layer. If feature_ids is None,
        removes all features '''
    layer.dataProvider().deleteFeatures(
        layer.allFeatureIds() if feature_ids is None else feature_ids)
    # use editCommand API to make force emission of editCommandEnded event
    layer.beginEditCommand('dummy')
    layer.endEditCommand()


def insert_features_in_layer(features, layer):
    layer.beginEditCommand('innsert new features')
    layer.dataProvider().addFeatures(features)
    layer.endEditCommand()
    layer.updateExtents()


def create_memory_layer(geometry_type, crs, name, custom_properties=None):
    assert geometry_type in (QGis.Point, QGis.Line, QGis.Polygon)
    layer = QgsVectorLayer(
        "{}?crs={}&index=yes".format(
            {
                QGis.Point: "Point",
                QGis.Line: "LineString",
                QGis.Polygon: "Polygon"
            }[geometry_type],
            crs.authid()
            ), name, "memory")
    layer.setCrs(crs)
    if custom_properties:
        for key in custom_properties:
            layer.setCustomProperty(key, custom_properties[key])
    return layer


def copy_layer_attributes_to_layer(src_layer,
                                   dst_layer,
                                   extra_attributes=None):
    attr = [src_layer.fields().field(f) for f in range(
        src_layer.fields().count())]
    if extra_attributes:
        attr += extra_attributes
    dst_layer.dataProvider().addAttributes(attr)
    dst_layer.updateFields()


def clone_layer_as_memory_layer(layer, custom_properties=None):
    clone = create_memory_layer(
        layer.geometryType(),
        layer.crs(),
        layer.name(),
        custom_properties)
    copy_layer_attributes_to_layer(layer, clone)
    # cpy style
    clone.setRendererV2(layer.rendererV2().clone())
    return clone


def layer_matches_all_properties(layer, properties):
    for key in properties:
        if layer.customProperty(key) != properties[key]:
            return False
    return True


def get_all_layers():
    return QgsMapLayerRegistry.instance().mapLayers().values()


def get_all_layers_with_property_set(property_name):
    return [l for l in QgsMapLayerRegistry.instance().mapLayers().values() if
            l.customProperty(property_name) is not None]


def get_layers_with_properties(properties):
    return [l for l in QgsMapLayerRegistry.instance().mapLayers().values() if
            layer_matches_all_properties(l, properties)]


def query_layer_feature_by_id(layer_id, feature_id):
    layer = QgsMapLayerRegistry.instance().mapLayer(layer_id)
    try:
        return layer.getFeatures(QgsFeatureRequest(feature_id)).next()
    except:
        return None


def __fixup_layer_attribute_name(layer, name):
    if layer.fieldNameIndex(name) >= 0:
        return name
    else:
        patched = '{}:Integer64(10,0)'.format(name)
        if layer.fieldNameIndex(patched) >= 0:
            return patched
        else:
            raise Exception('Invalid field name {} for layer {}'.format(
                name, layer.id()))


def __fixup_layer_attribute_names(layer, *attributes_value):
    result = {}
    # each attributes_value is a dict
    for arg in attributes_value:
        for name in arg:
            result[__fixup_layer_attribute_name(
                layer, name)] = arg[name]
    return result


def query_layer_features_by_attributes(layer, *attributes_value):
    assert len(attributes_value) > 0
    expr = []
    fixed = __fixup_layer_attribute_names(layer, *attributes_value)
    for attr in fixed:
        expr += ['"{}" = \'{}\''.format(attr, fixed[attr])]
    req = QgsFeatureRequest()
    if len(attributes_value) == 1:
        req.setFilterExpression(expr[0])
    else:
        req.setFilterExpression(' AND '.join(expr))
    logging.debug('query_layer_features_by_attributes req = "{}"'.format(
        req.filterExpression().expression()))
    return layer.getFeatures(req)


def query_layer_features_by_attributes_in(layer, *attributes_in):
    assert len(attributes_in) > 0
    expr = []
    fixed = __fixup_layer_attribute_names(layer, *attributes_in)
    for attr in fixed:
        ex = ''
        for v in fixed[attr]:
            ex += "'{}',".format(str(v))
        expr += ['"{}" IN ({})'.format(attr, ex[0:-1])]
    req = QgsFeatureRequest()
    if len(attributes_in) == 1:
        req.setFilterExpression(expr[0])
    else:
        req.setFilterExpression(' AND '.join(expr))
    return layer.getFeatures(req)


def get_layer_features_count_by_attributes(layer, *attributes_value):
    values = list(query_layer_features_by_attributes(layer, *attributes_value))
    return len(values)


def get_layer_unique_attribute(layer, attr):
    return layer.uniqueValues(
        layer.fieldNameIndex(
            __fixup_layer_attribute_name(layer, attr)))


def get_layer_max_feature_attribute(layer, attr):
    ids = get_layer_unique_attribute(layer, attr)
    return max(ids) if len(ids) > 0 else 0


def get_all_features_attributes(layer, *attributes):
    # TODO: beware Integer(64, 10)
    for feature in layer.getFeatures():
        feature.setFields(layer.fields(), False)
        attr = []
        for a in attributes:
            attr += [feature.attribute(__fixup_layer_attribute_name(layer, a))]
        yield attr


def get_all_layer_features(layer):
    return layer.getFeatures()


def get_layer_by_id(id):
    return QgsMapLayerRegistry.instance().mapLayer(id)


def get_feature_by_id(layer, feature_id):
    return layer.getFeatures(QgsFeatureRequest(feature_id)).next()


def layer_has_field(layer, field_name):
    return layer.fields().fieldNameIndex(field_name) >= 0


def get_feature_attribute_values(layer, feature, *attributes):
    result = []
    for a in attributes:
        idx = layer.fields().fieldNameIndex(
            __fixup_layer_attribute_name(layer, a))
        result += [feature[idx]]
    if len(attributes) == 1:
        return result[0]
    return result


def get_name(x):
    return x.name()


def get_id(x):
    return x.id()


def compute_feature_length(feature):
    assert QgsWKBTypes.hasZ(int(feature.geometry().wkbType()))
    v = loads(feature.geometry().exportToWkt().replace('Z', ' Z'))
    return sqrt(
        sum(
            [pow(v.coords[1][i] - v.coords[0][i], 2) for i in range(0, 3)]))


def get_feature_centroid(feature):
    geom = feature.geometry()
    if QgsWKBTypes.hasZ(int(geom.wkbType())):
        v = loads(geom.exportToWkt().replace('Z', ' Z'))
        points_count = len(v.coords)
        z_avg = sum([v.coords[i][2] for i in range(0, points_count)])
        return [v.centroid.x, v.centroid.y, z_avg]
    else:
        p = geom.centroid().asPoint()
        return [p.x(), p.y()]


def feature_to_shapely_wkt(feature):
    return feature.geometry().exportToWkt().replace('Z', ' Z')


def get_layer_selected_ids(layer):
    return layer.selectedFeaturesIds()


def init_layer_polygon_renderer(layer):
    layer.setRendererV2(QgsSingleSymbolRendererV2(QgsFillSymbolV2()))


def create_new_feature(layer, wkt, attributes=None):
    new_feature = QgsFeature()
    if wkt is not None:
        geom = qgeom_from_wkt(wkt)
        if geom is None:
            raise Exception('invalid wkt "{}"'.format(wkt))
        new_feature.setGeometry(geom)

    new_feature.setFields(layer.fields())
    if attributes is not None:
        for attr in attributes:
            new_feature.setAttribute(attr, attributes[attr])

    return new_feature


def root_layer_group_from_iface(iface):
    return iface.layerTreeView().layerTreeModel().rootGroup()


def is_3d_layer(layer, section_layers_id):
    """Return True if it's a layer which is drew in 3D

    XXX is it a better to identify this kind of layer (by an attribute or some
    metadata)?
    """
    if layer.customProperty('section_id') is not None:
        return False
    if layer.customProperty('graph'):
        return False
    if not layer.isSpatial():
        return False
    if QgsWKBTypes.geometryType(int(layer.wkbType())) != QgsWKBTypes.LineGeometry:
        return False
    if not isinstance(layer.rendererV2(), QgsSingleSymbolRendererV2):
        return False
    if get_id(layer) in section_layers_id:
        return False
    return True


def qgeom_from_wkt(wkt):
    """Return a QGis Geometry from a wkt string
    """
    return QgsGeometry.fromWkt(wkt)


def wkt_from_qgeom(geom):
    """Return a WKT string from a QGis Geometry object
    """
    return QgsGeometry.exportToWkt(geom)
