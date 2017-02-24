# coding=utf-8

from PyQt4.QtGui import QFileDialog, QMessageBox


def precondition_check(graph_layer, section_layer):
    if section_layer is None:
        return (False, "No active layer")
    if graph_layer is None:
        return (False, "No graph layer defined")
    if not section_layer.customProperty("session_id") is None:
        return (False, "Select a non-projected layer")
    if not section_layer.isSpatial():
        return (False, "Selected layer has no geometry")
    if section_layer.featureCount() == 0:
        return (False, "Selected layer has no features")
    return (True, "")


def execute(owner, polygons):
    file = QFileDialog.getSaveFileName(owner, "Save polygon-csv export to...")
    if len(file) == 0:
        return

    out_file = open(file, 'w')
    for index in range(0, len(polygons)):
        vertices = polygons[index]

        for i in range(0, len(vertices), 2):
            v = vertices[i]
            out_file.write('{};{};{};{}\n'.format(index, v[0], v[1], v[2]))

        for i in range(len(vertices)-1, 0, -2):
            v = vertices[i]
            out_file.write('{};{};{};{}\n'.format(index, v[0], v[1], v[2]))

        # last but not least: close the polygon
        v = vertices[0]
        out_file.write('{};{};{};{}\n'.format(index, v[0], v[1], v[2]))

    QMessageBox().information(owner, 'Export', 'Wrote {} polygon(s)'.format(
        len(polygons)))

    out_file.close()

