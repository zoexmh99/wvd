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
prime_headers = {
    'Accept': '*/*',
    'Connection': 'keep-alive',
    'Origin': 'https://www.primevideo.com',
    'Referer': 'https://www.primevideo.com/',
    'Host': 'atv-ps-fe.primevideo.com',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36',
    'Content-Length': '0',
    'sec-ch-ua': '"Google Chrome";v="89", "Chromium";v="89", ";Not A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
}


class EntityWatcha(EntityBase):
    url_regex = re.compile(r'watcha\.com\/watch\/(?P<code>.*?)$')
    name = 'watcha'



    def __init__(self, data):
        super(EntityWatcha, self).__init__(data)

        self.meta = None
        self.show_title = None
        self.season_number = None
        self.episode_number = None
        self.episode_title = None

        self.mp4_info = {'video':{'url':None}, 'audio':{'url':None}}
        self.video_url = None
        self.video_download_url = None
        self.video_original_filepath = None
        self.video_decryped_filepath = None

        self.audio_url = None
        self.audio_download_url = None
        self.audio_original_filepath = None
        self.audio_decryped_filepath = None

        self.default_language = None
        self.set_data(data)
        


    def start_process_video_result(self):
        logger.debug(u'프라임 비디오 시작')
        #self.set_data(data)

        logger.debug(u'자막 다운로드..')
        self.download_subtitle()

        logger.debug(u'mp4 다운로드 & 암호 해제')
        self.download_mp4()
        
        logger.debug(u'mkv 생성')
        self.merge()
        
        logger.debug(u'임시 파일 삭제')
        self.clean()
        logger.debug(u'완료..')



    def set_data(self, data):
        for period in self.mpd.period:
            logger.debug(period)
            for adaptation_set in period.adaptation_sets:
                logger.debug(adaptation_set)
                logger.debug(adaptation_set.content_type)




        request_list = self.data['har']['log']['entries']
        for item in request_list:



            if self.meta is None and item['request']['method'] == 'POST' and item['request']['url'].find('GetPlaybackResources') != -1:
                cookie = ''
                for tmp in self.data['cookie']:
                    cookie += '%s=%s; ' % (tmp['name'], tmp['value'])
                prime_headers['Cookie'] = cookie
                self.set_meta(requests.get(item['request']['url'], headers=prime_headers).json())#, data=post_data)
            
            elif self.mp4_info['video']['url'] is None and item['request']['method'] == 'GET' and item['request']['url'].find('_video_') != -1:
                self.mp4_info['video']['url'] = item['request']['url']
                match = re.compile(r'_video_(?P<video_number>\d+)\.mp4').search(self.mp4_info['video']['url'])
                self.mp4_info['video']['download_url'] = self.mp4_info['video']['url'].replace(match.group(0), '_video_12.mp4')
                self.mp4_info['video']['codec'] = 'H.264'
            elif self.mp4_info['audio']['url'] is None and item['request']['method'] == 'GET' and item['request']['url'].find('_audio_') != -1:
                self.mp4_info['audio']['url'] = item['request']['url']
                self.mp4_info['audio']['download_url'] = self.mp4_info['audio']['url']
                self.mp4_info['audio']['codec'] = 'AAC'
                
        

    def set_meta(self, meta):
        self.meta = meta
        self.content_type = self.meta['catalogMetadata']['catalog']['entityType']
        
        logger.debug(u"타입 : " + self.content_type)
        
        if self.content_type == 'TV Show':
            self.episode_number = self.meta['catalogMetadata']['catalog']['episodeNumber']
            self.episode_title = self.meta['catalogMetadata']['catalog']['title']
            self.season_number = self.meta['catalogMetadata']['family']['tvAncestors'][0]['catalog']['seasonNumber']
            self.show_title = self.meta['catalogMetadata']['family']['tvAncestors'][1]['catalog']['title']
            logger.debug(u'제목: [%s] 시즌:[%s], 에피:[%s] [%s]', self.show_title, self.season_number, self.episode_number, self.episode_title)


    def download_subtitle(self):
        #for tmp1 in ['forcedNarratives', 'subtitleUrls']:
        for tmp1 in ['subtitleUrls']:
            for item in self.meta[tmp1]:
                if item['displayName'].find('[CC]') != -1:
                    self.default_language = item['languageCode'] 
                #logger.debug(item)
                filepath = os.path.join(self.temp_dir, '{}.{}.{}.ttml'.format(self.code, item['type'], item['languageCode']))
                Utility.aria2c_download(item['url'], filepath)
                srt_filepath = filepath.replace('.ttml', '.srt')
                Utility.ttml2srt(filepath, srt_filepath)

    def download_mp4(self):
        for item in ['video', 'audio']:
            self.mp4_info[item]['original_filepath'] = os.path.join(self.temp_dir, '{}.{}.original.mp4'.format(self.code, item))
            self.mp4_info[item]['decryped_filepath'] = os.path.join(self.temp_dir, '{}.{}.decrypted.mp4'.format(self.code, item))
            self.mp4_info[item]['dump_filepath'] = os.path.join(self.temp_dir, '{}.{}.dump'.format(self.code, item))
            self.mp4_info[item]['info_filepath'] = os.path.join(self.temp_dir, '{}.{}.json'.format(self.code, item))
            self.mp4_info[item]['key'] = None

            if os.path.exists(self.mp4_info[item]['original_filepath']) == False:
                Utility.aria2c_download(self.mp4_info[item]['download_url'], self.mp4_info[item]['original_filepath'])

            if os.path.exists(self.mp4_info[item]['original_filepath']) and os.path.exists(self.mp4_info[item]['dump_filepath']) == False:
                Utility.mp4dump(self.mp4_info[item]['original_filepath'], self.mp4_info[item]['dump_filepath'])

            if os.path.exists(self.mp4_info[item]['dump_filepath']):
                text = Utility.read_file(self.mp4_info[item]['dump_filepath'])
                #logger.debug(text)
                self.mp4_info[item]['kid'] = text.split('default_KID = [')[1].split(']')[0].replace(' ', '')
                logger.debug('kid : %s', self.mp4_info[item]['kid'])
                self.mp4_info[item]['key'] = self.find_key(self.mp4_info[item]['kid'])
                logger.debug('--key %s:%s', self.mp4_info[item]['kid'], self.mp4_info[item]['key'])

            if os.path.exists(self.mp4_info[item]['decryped_filepath']) == False and self.mp4_info[item]['key'] is not None:
                Utility.mp4decrypt(self.mp4_info[item]['original_filepath'], self.mp4_info[item]['decryped_filepath'], self.mp4_info[item]['kid'], self.mp4_info[item]['key'])

            if os.path.exists(self.mp4_info[item]['decryped_filepath']) and os.path.exists(self.mp4_info[item]['info_filepath']) == False:
                Utility.mp4info(self.mp4_info[item]['decryped_filepath'], self.mp4_info[item]['info_filepath'])


    def merge(self):
        if os.path.exists(self.mp4_info['video']['decryped_filepath']) == False:
            return
        if os.path.exists(self.mp4_info['audio']['decryped_filepath']) == False:
            return

        self.mkv_filepath = os.path.join(self.temp_dir, '%s.mkv' % self.code)
        if os.path.exists(self.mkv_filepath) == False:
            audio_json = Utility.read_json(self.mp4_info['audio']['info_filepath'])
            option = ['-o', '"%s"' % self.mkv_filepath.replace(path_app_root, '.'),
                '-A', '"%s"' % self.mp4_info['video']['decryped_filepath'].replace(path_app_root, '.'), 
                '--language 0:%s' % audio_json['tracks'][0]['language'],
                '"%s"' % self.mp4_info['audio']['decryped_filepath'].replace(path_app_root, '.'),
                '--default-language', 'kor'
            ]

            etc_option = []
            for filename in os.listdir(self.temp_dir):
                if filename.startswith(self.code) and filename.endswith('.srt'):
                    nation = filename.split('.')[-2].split('-')[0]
                    if nation == 'ko':
                        option += ['--language', '"0:%s"' % nation]
                        option += ['--default-track', '"0:yes"']
                        option += ['--forced-track', '"0:yes"']
                        option += ['"%s"' % os.path.join(self.temp_dir, filename).replace(path_app_root, '.')]
                    else:
                        etc_option += ['--language', '"0:%s"' % nation, '"%s"' % os.path.join(self.temp_dir, filename).replace(path_app_root, '.')]
            option += etc_option
            logger.debug(option)
            Utility.mkvmerge(option)


        audio_json = Utility.read_json(self.mp4_info['audio']['info_filepath'])
        video_json = Utility.read_json(self.mp4_info['video']['info_filepath'])
        self.output_filename = u'{show_title}.S{season_number}E{episode_number}.{quality}p.{audio_codec}.{video_codec}.SfKo.mkv'.format(
            show_title = self.show_title,
            season_number = str(self.season_number).zfill(2),
            episode_number = str(self.episode_number).zfill(2),
            quality = video_json['tracks'][0]['sample_descriptions'][0]['height'],
            audio_codec = audio_json['tracks'][0]['sample_descriptions'][0]['mpeg_4_audio_object_type_name'].split(' ')[0],
            video_codec = video_json['tracks'][0]['sample_descriptions'][0]['coding_name']
        )
        self.output_filepath = os.path.join(Utility.output_dir, self.output_filename)
        if os.path.exists(self.output_filepath) == False:
            shutil.move(self.mkv_filepath, self.output_filepath)
            logger.debug('파일 생성: %s', self.output_filename)


    def clean(self):
        for filename in os.listdir(self.temp_dir):
            if filename.startswith(self.code):
                os.remove(os.path.join(self.temp_dir, filename))
