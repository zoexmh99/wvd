# -*- coding: utf-8 -*-
#from .plugin import blueprint, menu, plugin_load, plugin_unload, plugin_info
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

from framework import app

try:
    from selenium import webdriver
except:
    os.system("{} install selenium".format(app.config['config']['pip']))

try:
    import lxml.html
except: 
    os.system("{} install lxml".format(app.config['config']['pip']))


from .plugin import P
blueprint = P.blueprint
menu = P.menu
plugin_load = P.logic.plugin_load
plugin_unload = P.logic.plugin_unload
plugin_info = P.plugin_info




