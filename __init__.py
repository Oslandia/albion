# coding: utf-8



def classFactory(iface):
    #from .plugin import Plugin
    #return Plugin(iface)
    from .debug_plugin import Plugin
    return Plugin(iface)

