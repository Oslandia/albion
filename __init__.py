# coding: utf-8

from .plugin import Plugin


def classFactory(iface):
    return Plugin(iface)

