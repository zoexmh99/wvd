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
from .site_watcha import EntityWatcha

class LogicDownload(LogicModuleBase):
    db_default = {
        'download_db_version' : '1',
        'download_test_send_url' : '',
        'download_test_video_result_json' : '',
        'download_queue_list' : '',
    }

    site_list = [EntityPrime, EntityWatcha]
    

    def __init__(self, P):
        super(LogicDownload, self).__init__(P, 'queue')
        self.name = 'download'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        
        try:
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return render_template('sample.html', title='%s - %s' % (P.package_name, sub))


    def process_ajax(self, sub, req):
        try:
            ret = {'ret':'success'}
            if sub == 'send_url':
                url = req.form['url']
                ModelSetting.set('download_test_send_url', url)
                ret = self.send_url(url, is_test=True)
            elif sub == 'video_result_test':
                filepath = req.form['json_filepath']
                logger.debug('filepath : %s', filepath)
                ModelSetting.set('download_test_video_result_json', filepath)
                data = Utility.read_json(filepath)
                def func():
                    self.start_video_result(data)
                thread = threading.Thread(target=func, args=())
                #thread.daemon = True
                thread.start()
                ret['msg'] = u'시작했습니다.'
            elif sub == 'queue_start':
                self.queue_start()
            elif sub =='queue_stop':
                self.queue_stop()
            return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})


    def process_normal(self, sub, req):
        ret = {'ret':'success'}
        if sub == 'video_result':
            data = req.json
            def func():
                self.process_video_result(data)
            thread = threading.Thread(target=func, args=())
            #thread.daemon = True
            thread.start()
        return jsonify(ret)


    def plugin_load(self):
        if os.path.exists(Utility.tmp_dir) == False:
            os.makedirs(Utility.tmp_dir)
        if os.path.exists(Utility.json_dir) == False:
            os.makedirs(Utility.json_dir)
        if os.path.exists(Utility.output_dir) == False:
            os.makedirs(Utility.output_dir)

    #########################################################

    def queue_start(self):
        queue_list = ModelSetting.get_list('download_queue_list', '\n')
        for item in queue_list:
            logger.debug("URL : %s", item)
            self.send_url(item)


    def queue_stop(self):
        pass


    def send_url(self, url, is_test=False):
        try:
            server_url = '{server_ddns}/widevine_downloader/api/server/start'.format(server_ddns=ModelSetting.get('client_server_ddns'))
            data={'apikey':ModelSetting.get('client_server_apikey'), 'url':url, 'client_ddns':SystemModelSetting.get('ddns')}
            return requests.post(server_url, data=data).json()
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return {'ret':'warning', 'msg': str(e)}

    
    def process_video_result(self, data):
        # video
        filename = '%s.json' % Util.change_text_for_use_filename(data['url'])[:100]
        logger.debug('1111111111111111')
        logger.debug(filename)
        for site in self.site_list:
            logger.debug([data['url']])
            logger.debug(site.url_regex)
            match = site.url_regex.search(data['url'])
            logger.debug(site.url_regex)

            if match:
                logger.debug('22222222222222222222222222222222222')
                filename = '%s_%s.json' % (site.name, match.group('code'))
                data['site'] = site.name
                data['code'] = match.group('code')

        json_filepath = os.path.join(Utility.json_dir, filename)
        Utility.write_json(data, json_filepath)
        self.start_video_result(data)


        
    # 여긴 thread로 진입
    def start_video_result(self, data): 
        #result = self.start_video_result2(data)    
        #return            
        if app.config['config']['use_celery']:
            result = self.start_video_result1.apply_async((self, data))
            logger.debug("Celery 대기")
            result.get() 
            logger.debug("Celery 대기 종료")
            
        else:
            result = self.start_video_result2(data)

    @celery.task
    def start_video_result1(self, data):
        self.start_video_result2(data)

    def start_video_result2(self, data):
        logger.debug(u"비디오 결과 분석 시작")
        logger.debug('URL : %s', data['url'])

        for site in self.site_list:
            if site.name == data['site']:
                entity = site(data)
                entity.download_start()
