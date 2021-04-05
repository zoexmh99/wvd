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


from .queue_chrome_request import QueueChromeRequest
from .queue_download import QueueDownload
from .model import ModelWVDItem

class LogicDownload(LogicModuleBase):
    db_default = {
        'download_db_version' : '1',
        'download_interval' : '30',
        'download_auto_start' : 'False',
        'download_test_send_url' : '',
        'download_test_video_result_json' : '',
        'download_queue_list' : '',
        'downloadl_last_list_option' : '',
    }

    
    

    def __init__(self, P):
        super(LogicDownload, self).__init__(P, 'queue')
        self.name = 'download'
        self.queue_chrome_request = QueueChromeRequest(self)
        self.queue_download = QueueDownload(self)

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
            if sub == 'web_list':
                return jsonify(ModelWVDItem.web_list(request))
            elif sub == 'db_remove':
                return jsonify(ModelWVDItem.delete_by_id(req.form['id']))
            
                
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
                pass
                #self.queue_chrome_request.start_enqueue_thread()
                #self.queue_start()
            elif sub =='queue_stop':
                self.queue_stop()
            # 목록
            elif sub == 'request_url_add':
                ret = self.queue_chrome_request.add_request_url(req.form['url'], req.form['memo'])
            elif sub == 'command':
                command = req.form['command']
                if command == 'test_send_url':
                    url = req.form['url']
                    ModelSetting.set('download_test_send_url', url)
                    ret = self.queue_chrome_request.send_url(url)
                elif command == 'download_start':
                    self.download_start()
            return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})


    def process_normal(self, sub, req):
        try:
            ret = {'ret':'success'}
            if sub == 'video_result':
                data = req.json
                self.queue_download.receive_data(data)
            return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'log':str(e)})

    def plugin_load(self):
        if os.path.exists(Utility.tmp_dir) == False:
            os.makedirs(Utility.tmp_dir)
        if os.path.exists(Utility.json_dir) == False:
            os.makedirs(Utility.json_dir)
        if os.path.exists(Utility.output_dir) == False:
            os.makedirs(Utility.output_dir)


    def scheduler_function(self):
        self.queue_chrome_request.enqueue()
        self.queue_download.enqueue()



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

    
   


        
    