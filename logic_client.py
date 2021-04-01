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

from .site_prime import EntityPrime


class LogicClient(LogicModuleBase):
    db_default = {
        'client_db_version' : '1',
        'client_server_ddns' : '',
        'client_server_apikey' : '',
        'client_send_url' : '',
        'client_video_result_json' : '',
    }

    module_map = {'prime' : EntityPrime} 

    def __init__(self, P):
        super(LogicClient, self).__init__(P, 'setting')
        self.name = 'client'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        
        try:
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        except:
            return render_template('sample.html', title='%s - %s' % (P.package_name, sub))


    def process_ajax(self, sub, req):
        try:
            ret = {'ret':'success'}
            if sub == 'send_url':
                url = req.form['url']
                ModelSetting.set('base_send_url', url)
                ret = self.send_url(url, is_test=True)
            elif sub == 'video_result_test':
                filepath = req.form['json_filepath']
                ModelSetting.set('base_video_result_json', filepath)
                data = Utility.read_json(filepath)
                def func():
                    self.start_video_result(data)
                thread = threading.Thread(target=func, args=())
                thread.daemon = True
                thread.start()
                ret['msg'] = u'시작했습니다.'
            return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})


    def process_api(self, sub, req):
        ret = {'ret':'success'}
        if sub == 'video_result':
            logger.debug(req.form)
            data = req.json
            logger.debug('vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv')
            logger.debug(data)
            self.process_video_result(data)
            
        return jsonify(ret)


    def plugin_load(self):
        if os.path.exists(Utility.tmp_dir) == False:
            os.makedirs(Utility.tmp_dir)
        if os.path.exists(Utility.json_dir) == False:
            os.makedirs(Utility.json_dir)
        if os.path.exists(Utility.output_dir) == False:
            os.makedirs(Utility.output_dir)

    #########################################################


    def send_url(self, url, is_test=False):
        try:
            server_url = '{server_ddns}/widevine_downloader/api/server/start'.format(server_ddns=ModelSetting.get('base_server_ddns'))
            data={'apikey':ModelSetting.get('base_server_apikey'), 'url':url, 'client_ddns':SystemModelSetting.get('ddns'), 'client_apikey':SystemModelSetting.get('auth_apikey')}
            return requests.post(server_url, data=data).json()
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return {'ret':'warning', 'msg': str(e)}


    url_regex = {'prime' : re.compile(r'www\.primevideo\.com(.*?)detail\/(?P<code>.*?)\/') }
    def process_video_result(self, data):
        # video
        filename = '%s.json' % Util.change_text_for_use_filename(data['url'])[:100]
        for site, regex in self.url_regex.items():
            match = regex.search(data['url'])
            if match:
                filename = '%s_%s.json' % (site, match.group('code'))
                data['site'] = site
                data['code'] = match.group('code')

        json_filepath = os.path.join(Utility.json_dir, filename)
        Utility.write_json(data, json_filepath)
        self.start_video_result(data)

    def start_video_result(self, data):
        logger.debug(u"비디오 결과 분석 시작")
        logger.debug('URL : %s', data['url'])

        filename = '%s.json' % Util.change_text_for_use_filename(data['url'])[:100]
        for site, regex in self.url_regex.items():
            match = regex.search(data['url'])
            if match:
                #P.logic.get_module(site).start_process_video_result(data)
                entity = self.module_map[site]()
                entity.start_process_video_result(data)


