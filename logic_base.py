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

#from lib_metadata.server_util import MetadataServerUtil
#########################################################

class LogicBase(LogicModuleBase):
    db_default = {
        'base_db_version' : '1',
        'base_chrome_mode_is_remote' : 'True',
        'base_chrome_url' : '',
    }

    def __init__(self, P):
        super(LogicBase, self).__init__(P, 'setting')
        self.name = 'base'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        
        try:
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        except:
            return render_template('sample.html', title='%s - %s' % (P.package_name, sub))


    def process_ajax(self, sub, req):
        try:
            if sub == 'web_list':
                return jsonify(ModelJavcensoredItem.web_list(request))
            elif sub == 'db_remove':
                return jsonify(ModelJavcensoredItem.delete_by_id(req.form['id']))
            elif sub == 'filename_test':
                filename = req.form['filename']
                ModelSetting.set('jav_censored_filename_test', filename)
                newfilename = ToolExpandFileProcess.change_filename_censored(filename)
                newfilename = LogicJavCensored.check_newfilename(filename, newfilename, None)
                return jsonify({'ret':'success', 'data':newfilename})

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})


    #########################################################

    