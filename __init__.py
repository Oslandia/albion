# coding: utf-8

from .new_plugin import Plugin


def classFactory(iface):
    return Plugin(iface)

