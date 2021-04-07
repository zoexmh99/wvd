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




class EntityWavve(EntityBase):
    url_regex = re.compile(r'wavve\.com(.*?)(movieid|programid)=(?P<code>[_A-Z0-9]+)')
    name = 'wavve'
    name_on_filename = 'WAVVE'

    def __init__(self, db_id, json_filepath):
        super(EntityWavve, self).__init__(db_id, json_filepath)


    def prepare(self):
        try:

            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'POST' and item['request']['url'].find('GetPlaybackResources') != -1:
                    logger.debug('zzzzzzzzzzzzzzzzzzz')
                    logger.debug('zzzzzzzzzzzzzzzzzzz')
                    logger.debug(item['request']['url'])

                    cookie = ''
                    for tmp in self.data['cookie']:
                        cookie += '%s=%s; ' % (tmp['name'], tmp['value'])
                    prime_headers['Cookie'] = cookie
                    meta = requests.get(item['request']['url'], headers=prime_headers).json()

                    self.meta['source'] = meta
                    Utility.write_json(self.meta['source'], os.path.join(self.temp_dir, '{code}.meta.json'.format(code=self.code)))
                    break
            
            self.meta['content_type'] = 'show' if self.meta['source']['catalogMetadata']['catalog']['entityType'] == 'TV Show' else 'movie'
            
            logger.debug(u"타입 : " + self.meta['content_type'])
            
            if self.meta['content_type'] == 'show':
                self.meta['episode_number'] = self.meta['source']['catalogMetadata']['catalog']['episodeNumber']
                self.meta['episode_title'] = self.meta['source']['catalogMetadata']['catalog']['title']
                self.meta['season_number'] = self.meta['source']['catalogMetadata']['family']['tvAncestors'][0]['catalog']['seasonNumber']
                self.meta['title'] = self.meta['source']['catalogMetadata']['family']['tvAncestors'][1]['catalog']['title']
                logger.debug(u'제목: [%s] 시즌:[%s], 에피:[%s] [%s]', self.meta['title'], self.meta['season_number'], self.meta['episode_number'], self.meta['episode_title'])
            else:
                self.meta['title'] = self.meta['source']['catalogMetadata']['catalog']['title']

            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].find('_audio_') != -1:
                    logger.debug("오디오 : %s", item['request']['url'])
                    match = re.compile(r'_audio_(?P<number>\d+)\.mp4').search(item['request']['url'])
                    if not match:
                        continue
                    self.audio_url = item['request']['url'].split('?')[0]
                    self.mpd_url = self.audio_url.replace('_audio_%s.mp4' % match.group('number'), '_corrected.mpd?encoding=segmentBase')
                    logger.debug('MPD URL : %s', self.mpd_url)
                    break
            logger.debug('AAAAAAAAAAAAAAAAAAAAAAAA')
            logger.debug(self.audio_url)

            if True:
                #text = requests.get(self.data['url'], headers=prime_headers).text
                #logger.debug(text)
                for item in self.data['har']['log']['entries']:
                    if item['request']['method'] == 'GET' and item['request']['url'] == self.data['url']:
                        res = self.get_response(item)
                        text = res.text
                        epi_list = re.compile(r'\<a\shref=\"(?P<url>\/region\/fe\/detail.*?)\"\s').findall(text)
                        for epi in epi_list:
                            P.logic.get_module('download').queue_chrome_request.add_request_url('https://www.primevideo.com/%s' % epi, '')

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    def make_download_info(self):
        try:
            self.download_list['video'].append(self.make_filepath(self.adaptation_set['video'][0]['representation'][-1]))

            #logger.debug(json.dumps(self.download_list, indent=4))

            logger.debug('bbbbbbbbbbbbbbbbb')
            logger.debug(self.audio_url)
            
            if self.audio_url is not None:
                for audio_adaptation_set in self.adaptation_set['audio']:
                    for representation in audio_adaptation_set['representation']:
                        #logger.debug(representation['url'] )
                        if representation['url'] == self.audio_url:
                            self.download_list['audio'].append(self.make_filepath(representation))
                            break
                    if len(self.download_list['audio']) > 0:
                        break
            
            #logger.debug(self.download_list)

            for tmp1 in ['subtitleUrls']:
                for item in self.meta['source'][tmp1]:
                    representation = {'contentType':'text', 'mimeType':'text/ttml', 'url':item['url'], 'lang':item['languageCode'].split('-')[0]}
                    #if item['displayName'].find('[CC]') != -1:
                    #    self.default_language = item['languageCode'] 
                    self.download_list['text'].append(self.make_filepath(representation))
            #logger.debug(json.dumps(self.download_list, indent=4))

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
        