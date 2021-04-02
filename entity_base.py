# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
# third-party
import requests
# third-party
from flask import request, render_template, jsonify, redirect
from selenium import webdriver

# sjva 공용
from framework import db, scheduler, path_data, socketio, SystemModelSetting, app, celery
from framework.util import Util
from framework.common.util import headers, get_json_with_auth_session
from framework.common.plugin import LogicModuleBase, default_route_socketio
from tool_expand import ToolExpandFileProcess

# 패키지
from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting
from .utility import Utility


class EntityBase(object):
    
    def __init__(self, data):
        self.temp_dir = os.path.join(Utility.tmp_dir, self.name)
        if os.path.exists(self.temp_dir) == False:
            os.makedirs(self.temp_dir)
        self.data = data
        self.code = data['code']
        self.default_process()

    def find_key(self, kid):
        for key in reversed(self.data['key']):
            if kid == key['kid']:
                return key['key']

    def find_mpd(self):
        logger.debug('Find mpd..')
        request_list = self.data['har']['log']['entries']
        for item in request_list:
            if item['request']['method'] == 'GET' and item['request']['url'].find('.mpd') != -1:
                self.mpd_url = item['request']['url']
                logger.debug(self.mpd_url)
                from mpegdash.parser import MPEGDASHParser
                mpd = MPEGDASHParser.parse(self.mpd_url)
                logger.debug(mpd)
                logger.debug(MPEGDASHParser.toprettyxml(mpd))
                MPEGDASHParser.write(mpd, os.path.join(self.temp_dir, '{}.mpd'.format(self.code)))

    def default_process(self):
        logger.debug(u'공통 처리')
        self.find_mpd()


