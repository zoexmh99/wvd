# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil
from datetime import datetime
# third-party
import requests
# third-party
from flask import request, render_template, jsonify, redirect
from sqlalchemy import or_, and_, func, not_, desc
import lxml.html
from lxml import etree as ET

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
#from lib_metadata.server_util import MetadataServerUtil
#########################################################

class LogicClient(LogicModuleBase):
    db_default = {
        'client_db_version' : '1',
        'client_server_ddns' : '',
        'client_server_apikey' : '',
        'client_netflix_id' : '',
        'client_netflix_pw' : '',
    }

    def __init__(self, P):
        super(LogicClient, self).__init__(P, 'setting')
        self.name = 'client'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        try:
            return render_template(f'{package_name}_{self.name}_{sub}.html', arg=arg)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return render_template('sample.html', title=f"{package_name}/{self.name}")

    

    #########################################################
