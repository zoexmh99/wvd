# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil
from datetime import datetime
# third-party
import requests
# third-party
from flask import request, render_template, jsonify, redirect

# sjva 공용
from framework import db, scheduler, path_data, socketio, SystemModelSetting, app, celery, Util, py_queue, py_urllib

# 패키지
from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting
from .utility import Utility
from .model import ModelWVDItem
from .site_prime import EntityPrime
from .site_watcha import EntityWatcha

#########################################################


class QueueDownload(object):
    site_list = [EntityPrime, EntityWatcha]


    def __init__(self, module):
        self.module = module
        self.queue = py_queue.Queue()
        self.thread = threading.Thread(target=self.thread_function, args=())
        self.thread.daemon = True
        self.thread.start()
        

    def thread_function(self):
        while True:
            try:
                db_id = self.queue.get()
                self.process_one(db_id)
                time.sleep(2)
                self.queue.task_done()    
            except Exception as e: 
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())

    def process_one(self, db_id):
        def func():
            ret = self.start_video_result(db_id, None)
        thread = threading.Thread(target=func, args=())
        #thread.daemon = True
        thread.start()
        thread.join()

    
    def enqueue(self):
        queue_list = list(self.queue.queue)
        for db_item in ModelWVDItem.get_items_by_status('make_json'):
            already_exist = False
            for queue_id in queue_list:
                if queue_id == db_item.id:
                    already_exist = True
                    break
            if already_exist == False:
                self.queue.put(db_item.id)

    def enqueue_one(self, db_id):
        self.queue.put(db_id)
       

    def receive_data(self, data):
        filename = '%s.json' % Util.change_text_for_use_filename(data['url'])[:100]
        for site in self.site_list:
            match = site.url_regex.search(data['url'])
            if match:
                filename = '%s_%s.json' % (site.name, match.group('code'))
                data['site'] = site.name
                data['code'] = match.group('code')
        json_filepath = os.path.join(Utility.json_dir, filename)
        Utility.write_json(data, json_filepath)

        db_item = ModelWVDItem.get_item_by_site_and_code(data['site'], data['code'])
        if db_item is not None and db_item.status == 'send_url_success':
            db_item.status = 'make_json'
            db_item.response_filepath = json_filepath
            db_item.save()
            self.enqueue_one(db_item.id)


    # 여긴 thread로 진입
    def start_video_result(self, db_id, json_filepath): 
        #result = self.start_video_result2(data)    
        #return            
        if app.config['config']['use_celery']:
            result = QueueDownload.start_video_result1.apply_async((db_id, json_filepath))
            logger.debug("Celery 대기")
            ret = result.get() 
            logger.debug("Celery 대기 종료")
            
        else:
            ret = QueueDownload.start_video_result1(db_id, json_filepath)

        return ret 


    @staticmethod
    @celery.task
    def start_video_result1(db_id, json_filepath):
        logger.debug(u"비디오 결과 분석 시작")
        db_item = ModelWVDItem.get_by_id(db_id)
        for site in QueueDownload.site_list:
            if site.name == db_item.site:
                entity = site(db_id, json_filepath)
                entity.download_start()
        return True

    