# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
# third-party
import requests
# third-party
from flask import request, render_template, jsonify, redirect

# sjva 공용
from framework import db, scheduler, path_data, socketio, SystemModelSetting, app, celery, path_app_root, Util

# 패키지
from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting
from .utility import Utility
from .entity_base import EntityBase

#########################################################

class EntityWatcha(EntityBase):
    url_regex = re.compile(r'watcha\.com\/watch\/(?P<code>.*?)$')
    name = 'watcha'
    name_on_filename = 'WC'


    def __init__(self, db_id, json_filepath):
        super(EntityWatcha, self).__init__(db_id, json_filepath)

    def prepare(self):
        try:
            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].find('%s.json' % self.code) != -1:
                    res = self.get_response(item)
                    self.meta['source'] = res.json()
                    Utility.write_json(self.meta['source'], os.path.join(self.temp_dir, '{code}.meta.json'.format(code=self.code)))
                if item['request']['method'] == 'GET' and item['request']['url'].find('tv_episodes.json?all=true') != -1:
                    res = self.get_response(item)
                    logger.debug('111111111111111111111111111111')
                    tmp = res.json()
                    for code in tmp['tv_episode_codes']:
                        P.logic.get_module('download').queue_chrome_request.add_request_url('https://watcha.com/watch/%s' % code, '')

                   
                    logger.debug(json.dumps(tmp, indent=4))
                    
                    #self.meta['source'] = res.json()
                    #Utility.write_json(self.meta['source'], os.path.join(self.temp_dir, '{code}.meta.json'.format(code=self.code)))
                    break
                
            
            self.meta['content_type'] = 'show' if self.meta['source']['content_type'] == 'tv_episodes' else 'movie'
            self.add_log(u"타입 : %s" % self.meta['content_type'])
            
            if self.meta['content_type'] == 'show':
                logger.debug(self.meta['source']['title'])
                
                match_list = [
                    re.compile(u'(?P<title>.*?)\s?시즌\s?(?P<number>\d+)').search(self.meta['source']['title']),
                    re.compile(u'(?P<title>.*?)\s?(?P<number>\d+)\s?기').search(self.meta['source']['title']),
                    re.compile('(?P<title>.*?)\sSeason\s(?P<number>\d+)$').search(self.meta['source']['eng_title'])
                ]
                for match in match_list:
                    if match:
                        self.meta['title'] = match.group('title')
                        self.meta['season_number'] = match.group('number')
                        break
                self.meta['episode_number'] = self.meta['source']['tv_episode_formal_number']
                self.meta['episode_title'] = ''
                                
                logger.debug(u'제목: [%s] 시즌:[%s], 에피:[%s] [%s]', self.meta['title'], self.meta['season_number'], self.meta['episode_number'], self.meta['episode_title'])
            else:
                self.meta['title'] = self.meta['source']['title']
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

     


    def make_download_info(self):
        try:
            self.download_list['video'].append(self.make_filepath(self.adaptation_set['video'][0]['representation'][-1]))
            self.download_list['audio'].append(self.make_filepath(self.adaptation_set['audio'][0]['representation'][-1]))
            if len(self.adaptation_set['text']) > 0:
                self.download_list['text'].append(self.make_filepath(self.adaptation_set['text'][0]['representation'][-1]))
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())