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
from framework.common.util import headers
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
        super(LogicDownload, self).__init__(P, 'list')
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

            elif sub == 'request_url_add':
                ret = self.queue_chrome_request.add_request_url(req.form['url'], req.form['memo'])
            elif sub == 'command':
                command = req.form['command']
                if command == 'test_send_url':
                    url = req.form['url']
                    ModelSetting.set('download_test_send_url', url)
                    ret = self.queue_chrome_request.send_url(url)
                elif command == 'test_video_result_json':
                    json_filepath = req.form['json_filepath']
                    ModelSetting.set('download_test_video_result_json', json_filepath)
                    self.queue_download.start_video_result(-1, json_filepath)
                elif command == 'download_start':
                    self.download_start()
                elif command == 'set_status':
                    logger.debug(req.form['status'])
                    logger.debug(req.form['db_id'])
                    db_item = ModelWVDItem.get_by_id(int(req.form['db_id']))
                    db_item.status = req.form['status']
                    db_item.save()
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
        """
        queue_list = ModelSetting.get_list('download_queue_list', '\n')
        for item in queue_list:
            logger.debug("URL : %s", item)
            self.send_url(item)
        """
        pass


    def queue_stop(self):
        pass

