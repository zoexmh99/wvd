# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, requests
from datetime import datetime
# third-party
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.events import EventFiringWebDriver, AbstractEventListener
from selenium.webdriver import ActionChains
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.select import Select

from tool_base import d, ToolBaseFile

from pywidevine.L3.cdm import cdm, deviceconfig
from base64 import b64encode, b64decode
from pywidevine.L3.decrypt.wvdecryptcustom import WvDecrypt



# 패키지
from .plugin import P, path_data
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting
from .utility import Utility
from .model import ModelWVDItem
from mpegdash.parser import MPEGDASHParser

class SiteBase(object):
    def __init__(self, db_id, json_filepath):
        
        self.db_id = db_id
        if json_filepath is None:
            self.db_item = ModelWVDItem.get_by_id(db_id)
            self.data = Utility.read_json(self.db_item.response_filepath)
        else:
            self.db_item = ModelWVDItem()
            self.data = Utility.read_json(json_filepath)
        
        self.code = self.data['code']
        self.temp_dir = os.path.join(Utility.tmp_dir, self.name, self.code)
        if os.path.exists(self.temp_dir) == False:
            os.makedirs(self.temp_dir)
        
        self.mpd_url = self.mpd = self.mpd_base_url = None
        self.mpd_headers = {}
        self.download_list = {'video':[], 'audio':[], 'text':[]}
        self.filepath_mkv = os.path.join(self.temp_dir, '{code}.mkv'.format(code=self.code))
        self.meta = {'content_type':'movie', 'title':self.code, 'season_number':1, 'episode_number':1}
        self.use_mpd_url = True
        
        #self.default_process()

        #self.aria2c_timeout = 10000 #다운로드 기본 타임아웃
        self.streaming_protocol = "dash"  #hls, dash
        #self.is_dash_fragment = False # 통파일, 분할파일 여부

    
    def set_status(self, status):
        self.db_item.status = status
        #if self.db_id != -1:
        #    self.db_item.save()

    def add_log(self, log):
        logger.debug(log)
        if self.db_item.log is None:
            self.db_item.log = ''
        self.db_item.log += u'%s\n' % (log)
    


    def download_start(self):
        try:
            logger.debug(u'공통 처리')
            self.db_item.download_start_time = datetime.now()

            self.prepare()
            if self.check_output_file():
                logger.debug(u'output 파일 있음')
                self.set_status('completed')
                return
            self.set_status('downloading')
            
            if self.streaming_protocol == 'hls':
                ret = self.download_m3u8()
            elif self.streaming_protocol == 'dash':
                self.find_mpd()
                if self.mpd is not None:
                    self.analysis_mpd()
                self.make_download_info()
                ret = self.download()
            #self.clean()
            if ret:
                self.set_status('completed')
        finally:
            logger.debug("다운로드 종료")
            if self.db_id != -1:
                self.db_item.save()
    
    

    def check_output_file(self):
        check_filename = None
        if self.meta['content_type'] == 'show':
            regex = r'{title}\.S{season_number}E{episode_number}\.\d+p\.WEB-DL\..*?\.SW{site}\.mkv'.format(
                title = ToolBaseFile.text_for_filename(self.meta['title']),
                season_number = str(self.meta['season_number']).zfill(2),
                episode_number = str(self.meta['episode_number']).zfill(2),
                site = self.name_on_filename,
            )
            logger.debug(regex)
            regex = re.compile(regex)
        else:
            regex = r'{title}\.\d+p\.WEB-DL\..*?\.SW{site}\.mkv'.format(
                title = ToolBaseFile.text_for_filename(self.meta['title']),
                site = self.name_on_filename,
            )
            #logger.debug(regex)
            regex = re.compile(regex)

        for filename in os.listdir(Utility.output_dir):
            match = regex.match(filename)
            logger.debug(u'파일명 : %s', filename)
            if match:
                logger.debug('파일 있음')
                return True
        return False



    def find_key(self, kid):
        for key in reversed(self.data['key']):
            if kid == key['kid']:
                return key['key']

    def find_mpd(self):
        mpd_item = None
        if self.mpd_url is None:
            request_list = self.data['har']['log']['entries']
            for item in reversed(request_list):
                if item['request']['method'] == 'GET' and item['request']['url'].find('.mpd') != -1:
                    self.mpd_url = item['request']['url']
                    self.add_log('MPD URL : %s' % self.mpd_url)
                    mpd_item = item
                    break
            res = self.get_response(mpd_item)
            #logger.error(f"MPD response : {res}")
            self.mpd = MPEGDASHParser.parse(res.text)    
            for item in mpd_item['request']['headers']:
                self.mpd_headers[item['name']] = item['value']
        else:
            # 프라임비디오
            self.mpd = MPEGDASHParser.parse(self.mpd_url)
            #logger.warning('use_mpd_url : %s', self.use_mpd_url)
            #if self.use_mpd_url:
            #    self.mpd = MPEGDASHParser.parse(self.mpd_url)
            #    
            #else:

        self.mpd_base_url = self.mpd_url[:self.mpd_url.rfind('/')+1]
        self.add_log(f'MPD Base URL : {self.mpd_base_url}')
        tmp = os.path.join(self.temp_dir, '{}.mpd'.format(self.code))
        MPEGDASHParser.write(self.mpd, tmp)
        self.add_log('MPD 저장 : %s' % tmp)
               

    def analysis_mpd(self):
        self.adaptation_set = {'video':[], 'audio':[], 'text':[]}
        for period in self.mpd.periods:
            for adaptation_set in period.adaptation_sets:
                item_adaptation_set = {'representation':[]}
                item_adaptation_set['lang'] = adaptation_set.lang
                item_adaptation_set['contentType'] = adaptation_set.content_type
                #logger.error(f"adaptation_set contentType {item_adaptation_set['contentType']}")
                #logger.error(f"adaptation_set.mime_type {adaptation_set.mime_type}")
                if item_adaptation_set['contentType'] is None and adaptation_set.mime_type is not None:
                    item_adaptation_set['contentType'] = adaptation_set.mime_type.split('/')[0]
                item_adaptation_set['maxBandwidth']= adaptation_set.max_bandwidth
                if adaptation_set.segment_templates is not None:
                    item_adaptation_set['segment_templates'] = adaptation_set.segment_templates[0].to_dict()
                    item_adaptation_set['segment_templates']['segment_timeline'] = adaptation_set.segment_templates[0].segment_timelines
                    item_adaptation_set['segment_templates']['start_number'] = adaptation_set.segment_templates[0].start_number
                    if adaptation_set.segment_templates[0].segment_timelines is not None:
                        timelines = []
                        for tmp in adaptation_set.segment_templates[0].segment_timelines[0].Ss:
                            timelines.append({'t':tmp.t, 'd':tmp.d, 'r':tmp.r})
                        item_adaptation_set['segment_templates']['segment_timeline'] = timelines
                else:
                    item_adaptation_set['segment_templates'] = {}
                #logger.error(item_adaptation_set['SegmentTemplate'])
                #logger.error(adaptation_set.content_protections)
                for representation in adaptation_set.representations:
                    # 티빙
                    if item_adaptation_set['contentType'] is None and representation.mime_type is not None:
                        item_adaptation_set['contentType'] = representation.mime_type.split('/')[0]

                    item_representation = {'ct':item_adaptation_set['contentType'], 'cenc':False if adaptation_set.content_protections == None else True}
                    item_representation['lang'] = adaptation_set.lang
                    item_representation['contentType'] = item_adaptation_set['contentType']
                    if representation.segment_templates is not None:
                        # 카카오 무료
                        #logger.debug(representation.segment_templates)
                        item_representation['segment_templates'] = representation.segment_templates[0].to_dict()
                        item_representation['segment_templates']['segment_timeline'] = representation.segment_templates[0].segment_timelines
                        item_representation['segment_templates']['start_number'] = representation.segment_templates[0].start_number
                        if representation.segment_templates[0].segment_timelines is not None:
                            timelines = []
                            for tmp in representation.segment_templates[0].segment_timelines[0].Ss:
                                timelines.append({'t':tmp.t, 'd':tmp.d, 'r':tmp.r})
                            item_representation['segment_templates']['segment_timeline'] = timelines
                    else:
                        item_representation['segment_templates'] = item_adaptation_set['segment_templates']
                    item_representation['bandwidth'] = representation.bandwidth
                    item_representation['codecs'] = representation.codecs
                    item_representation['codec_name'] = representation.codecs
                    if item_representation['codecs'] is not None:
                        if item_representation['codecs'].startswith('avc1'):
                            item_representation['codec_name'] = 'H.264'
                        elif item_representation['codecs'].startswith('mp4a.40.2'):
                            item_representation['codec_name'] = 'AAC'

                    item_representation['height'] = representation.height
                    item_representation['width'] = representation.width
                    item_representation['mimeType'] = representation.mime_type
                    if item_representation['mimeType'] == None:
                        item_representation['mimeType'] = adaptation_set.mime_type
                    item_representation['id'] = representation.id
                    #logger.warning(self.mpd_base_url)
                    #logger.warning(self.mpd.base_urls)
                    #logger.warning(representation.base_urls)
                    if representation.base_urls is not None:
                        if representation.base_urls[0].base_url_value.startswith('http'):
                            # 쿠팡 자막
                            item_representation['url'] = representation.base_urls[0].base_url_value
                        else:
                            item_representation['url'] = '%s%s' % (self.mpd_base_url, representation.base_urls[0].base_url_value)
                    #elif self.mpd.base_urls is not None:
                    #    item_representation['url'] = self.mpd.base_urls[0].base_url_value
                    else:
                        item_representation['url'] = None
                        
                    #logger.warning(item_representation['url'])
                    item_adaptation_set['representation'].append(item_representation)
                self.adaptation_set[item_adaptation_set['contentType']].append(item_adaptation_set)
       
        #logger.debug(json.dumps(self.adaptation_set, indent=4))


    def make_filepath(self, representation):
        #logger.debug(representation)
        if  representation['contentType'] == 'text':
            force = representation.get('force', False)
            representation['filepath_download'] = os.path.join(self.temp_dir, '{code}.{lang}{force}.{ext}'.format(code=self.code, lang=representation['lang'], force='.force' if force else '', ext=representation['mimeType'].split('/')[1]))
            representation['filepath_merge'] = os.path.join(self.temp_dir, '{code}.{lang}{force}.srt'.format(code=self.code, lang=representation['lang'], force='.force' if force else ''))
        else:
            representation['filepath_download'] = os.path.join(self.temp_dir, '{code}.{contentType}.{lang}.{bandwidth}.original.mp4'.format(code=self.code, contentType=representation['contentType'], lang=representation['lang'] if representation['lang'] is not None else '', bandwidth=representation['bandwidth'])).replace('..', '.')
            representation['filepath_merge'] = representation['filepath_download'].replace('.original.mp4', '.decrypt.mp4')
            representation['filepath_dump'] = representation['filepath_merge'].replace('.mp4', '.dump.txt')
            representation['filepath_info'] = representation['filepath_merge'].replace('.mp4', '.info.json')

        #logger.debug(representation)
        return representation

    # 오버라이딩 할 수 있음.
    def make_download_info(self):
        try:
            for ct in ['video', 'audio']:
                max_band = 0
                max_item = None
                for adaptation_set in self.adaptation_set[ct]:
                    for item in adaptation_set['representation']:
                        if item['bandwidth'] > max_band:
                            max_band = item['bandwidth']
                            max_item = item
                self.download_list[ct].append(self.make_filepath(max_item))                      

            #logger.warning(d(self.adaptation_set['text']))
            # 왓챠는 TEXT  adaptation_set이 여러개
            #if len(self.adaptation_set['text']) > 0:
            for adaptation_set in self.adaptation_set['text']:
                if adaptation_set['representation'] is not None:
                    for item in adaptation_set['representation']:
                        #logger.error(item['url'])
                        item['url'] = item['url'].replace('&amp;', '&')
                        #logger.error(item['url'])
                        self.download_list['text'].append(self.make_filepath(item))
            logger.warning(d(self.download_list))
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    def download(self):
        try:
            self.merge_option = ['-o', '"%s"' % self.filepath_mkv]
            self.merge_option_etc = []
            self.audio_codec = ''
            for ct in ['video', 'audio']:
                #logger.warning(d(self.download_list))
                for item in self.download_list[ct]:
                    logger.debug(item['url'])
                    if item['url'] is not None:
                        #logger.warning(item['filepath_download'])
                        if os.path.exists(item['filepath_download']) == False:
                            logger.debug("다운로드 시작")
                            Utility.aria2c_download(item['url'], item['filepath_download'], segment=False)
                            logger.debug("다운로드 종료")
                    else:
                        self.download_segment(item)


                    if os.path.exists(item['filepath_download']) and os.path.exists(item['filepath_dump']) == False:
                        Utility.mp4dump(item['filepath_download'], item['filepath_dump'])

                    #logger.debug(os.path.exists(item['filepath_merge']))

                    if os.path.exists(item['filepath_merge']) == False:
                        logger.debug('암호화 해제')
                        text = Utility.read_file(item['filepath_dump'])
                        if text.find('default_KID = [') == -1:
                            shutil.copy(item['filepath_download'], item['filepath_merge'])
                        else:
                            kid = text.split('default_KID = [')[1].split(']')[0].replace(' ', '')
                            
                            key = self.find_key(kid)
                            logger.debug(self.data['key'])

                            logger.debug('%s:%s', kid, key)
                            Utility.mp4decrypt(item['filepath_download'], item['filepath_merge'], kid, key)
                            logger.debug(os.path.exists(item['filepath_merge']))

                    if os.path.exists(item['filepath_merge']) and os.path.exists(item['filepath_info']) == False:
                        Utility.mp4info(item['filepath_merge'], item['filepath_info'])
                    
                    if ct == 'audio':
                        if item['lang'] != None:
                            self.merge_option += ['--language', '0:%s' % item['lang']]
                        self.audio_codec += item['codec_name'] + '.'
                        #logger.error(self.merge_option)
                    self.merge_option += ['"%s"' % item['filepath_merge']]

            #logger.error(self.download_list['text'])
            for item in self.download_list['text']:
                if os.path.exists(item['filepath_download']) == False:
                    logger.warning(f"자막 url : {item['url']}")
                    Utility.aria2c_download(item['url'], item['filepath_download'], headers=self.mpd_headers if self.mpd_base_url is not None and item['url'].startswith(self.mpd_base_url) else {})
                if os.path.exists(item['filepath_download']) and os.path.exists(item['filepath_merge']) == False:
                    if item['mimeType'] == 'text/ttml':
                        Utility.ttml2srt(item['filepath_download'], item['filepath_merge'])
                    elif item['mimeType'] == 'text/vtt':
                        Utility.vtt2srt(item['filepath_download'], item['filepath_merge'])
                    elif item['mimeType'] == 'text/vtt/netflix':
                        sub = Utility.read_file(item['filepath_download'])
                        #new_sub = re.sub('\n{3,}', '', sub, flags=re.MULTILINE)
                        for idx, tmp in enumerate(sub.split('\n')):
                            if tmp == '1':
                                break
                        new_sub = '\n'.join(sub.split('\n')[idx:])
                        Utility.write_file(item['filepath_download'], new_sub)
                        Utility.vtt2srt(item['filepath_download'], item['filepath_merge'])
                if os.path.exists(item['filepath_merge']) == False:
                    continue
                if item['lang'] == 'ko':
                    self.merge_option += ['--language', '"0:%s"' % item['lang']]
                    #self.merge_option += ['--forced-track', '"0:yes"']
                    if item.get('force', False):
                        self.merge_option += ['--forced-track', '"0:yes"']
                    else:
                        self.merge_option += ['--default-track', '"0:yes"']
                    self.merge_option += ['"%s"' % item['filepath_merge']]

                else:
                    self.merge_option_etc += ['--language', '"0:%s"' % item['lang']]
                    if item.get('force', False):
                        self.merge_option_etc += ['--forced-track', '"0:yes"']
                    self.merge_option_etc += ['"%s"' % item['filepath_merge']]

                   

            if self.meta['content_type'] == 'show':
                self.output_filename = u'{title}.S{season_number}E{episode_number}.{quality}p.WEB-DL.{audio_codec}{video_codec}.SW{site}.mkv'.format(
                    title = ToolBaseFile.text_for_filename(self.meta['title']).strip(),
                    season_number = str(self.meta['season_number']).zfill(2),
                    episode_number = str(self.meta['episode_number']).zfill(2),
                    quality = self.download_list['video'][0]['height'],
                    audio_codec = self.audio_codec,
                    video_codec = self.download_list['video'][0]['codec_name'],
                    site = self.name_on_filename,
                )
            else:
                self.output_filename = u'{title}.{quality}p.WEB-DL.{audio_codec}{video_codec}.SW{site}.mkv'.format(
                    title = ToolBaseFile.text_for_filename(self.meta['title']).strip(),
                    quality = self.download_list['video'][0]['height'],
                    audio_codec = self.audio_codec,
                    video_codec = self.download_list['video'][0]['codec_name'],
                    site = self.name_on_filename,
                )
            #logger.warning(self.output_filename)
            self.filepath_output = os.path.join(Utility.output_dir, self.output_filename)
            #logger.warning(d(self.merge_option + self.merge_option_etc))
            
            if os.path.exists(self.filepath_output) == False:
                #logger.error(self.merge_option)
                #logger.error(self.merge_option_etc)
                Utility.mkvmerge(self.merge_option + self.merge_option_etc)
                shutil.move(self.filepath_mkv, self.filepath_output)
                self.add_log(f'파일 생성: {self.output_filename}')
            return True
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

        return False


    def download_segment(self, item):
        if self.mpd.base_urls == None:
            prefix = self.mpd_base_url
            headers = self.mpd_headers
        else:
            # 쿠팡만. 다른 url로 요청하기 때문에 host 같은 헤더가 문제 발생
            prefix = self.mpd.base_urls[0].base_url_value
            headers = {}
        url = f"{prefix}{item['segment_templates']['initialization'].replace('&amp;', '&').replace('$RepresentationID$', item['id']).replace('$Bandwidth$', str(item['bandwidth']))}"
        init_filepath = os.path.join(self.temp_dir, f"{self.code}_{item['ct']}_init.m4f")
        logger.warning(f"INIT URL : {url}")
        Utility.aria2c_download(url, init_filepath, headers=headers)

        start = 0
        if 'start_number' in item['segment_templates'] and item['segment_templates']['start_number'] is not None:
            start = int(item['segment_templates']['start_number'])
        if item['segment_templates']['segment_timeline']:
            timevalue = 0
            for timeline in item['segment_templates']['segment_timeline']:
                duration = timeline['d']
                repeat = (timeline.get('r') if timeline.get('r') is not None else 0) + 1

                for i in range(0, repeat):
                    url = f"{prefix}{item['segment_templates']['media'].replace('&amp;', '&').replace('$RepresentationID$', item['id']).replace('$Number$', str(start)).replace('$Number%06d$', str(start).zfill(6)).replace('$Bandwidth$', str(item['bandwidth'])).replace('$Time$', str(timevalue))}"
                    filepath = os.path.join(self.temp_dir, f"{self.code}_{item['ct']}_{str(start).zfill(5)}.m4f")
                    Utility.aria2c_download(url, filepath, headers=headers)
                    timevalue += duration
                    start += 1
        else:
            # 카카오, 쿠팡(.replace('&amp;', '&'))
            for i in range(start, 5000):
                url = f"{prefix}{item['segment_templates']['media'].replace('&amp;', '&').replace('$RepresentationID$', item['id']).replace('$Number$', str(i)).replace('$Number%06d$', str(i).zfill(6)).replace('$Bandwidth$', str(item['bandwidth']))}"
                filepath = os.path.join(self.temp_dir, f"{self.code}_{item['ct']}_{str(i).zfill(5)}.m4f")
                if Utility.aria2c_download(url, filepath, headers=headers) == False:
                    break
        Utility.concat(init_filepath, os.path.join(self.temp_dir, f"{self.code}_{item['ct']}_0*.m4f"), item['filepath_download'])


    def clean(self):
        for filename in os.listdir(self.temp_dir):
            if filename.startswith(self.code):
                os.remove(os.path.join(self.temp_dir, filename))
                pass


    def get_response(self, item):
        try:
            headers = {}
            for h in item['request']['headers']:
                headers[h['name']] = h['value']
            if item['request']['method'] == 'GET':
                return requests.get(item['request']['url'], headers=headers)
            elif item['request']['method'] == 'POST':
                return requests.post(item['request']['url'], headers=headers)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
    
    @classmethod
    def get_response_cls(cls, item):
        try:
            headers = {}
            for h in item['request']['headers']:
                headers[h['name']] = h['value']
            if item['request']['method'] == 'GET':
                return requests.get(item['request']['url'], headers=headers)
            elif item['request']['method'] == 'POST':
                return requests.post(item['request']['url'], headers=headers)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    # 카카오 같은 경우 iframe url로 변환
    @classmethod
    def get_request_url(cls, url):
        return url

    @classmethod
    def do_driver_action(cls, ins):
        pass
    
    @classmethod
    def do_make_key(cls, ins):
       
        try:
            # save
            filepath = os.path.join(path_data, package_name, 'server', f"{ins.current_data['site']}_{ins.current_data['code']}.json")
            if os.path.exists(filepath) == False:
                if os.path.exists(os.path.dirname(filepath)) == False:
                    os.makedirs(os.path.dirname(filepath))
                logger.warning(f"저장 : {filepath}")
                Utility.write_json(filepath, ins.current_data)

            request_list = ins.current_data['har']['log']['entries']
            pssh = None
            postdata = {'headers':{}, 'data':{}, 'cookies':{}, 'params':{}}
            for item in reversed(request_list):
                if item['request']['method'] == 'GET' and item['request']['url'].find('.mpd') != -1:
                    res = cls.get_response_cls(item)
                    pssh = cls.get_pssh(res)
                    logger.error(pssh)
                    break
            for item in request_list:
                if item['request']['method'] == 'POST' and item['request']['url'].startswith(cls.lic_url):
                    lic_url = item['request']['url']
                    for h in item['request']['headers']:
                        postdata['headers'][h['name']] = h['value']
                    for h in item['request']['queryString']:
                        postdata['params'][h['name']] = h['value']

            logger.debug(d(postdata))
            wvdecrypt = WvDecrypt(init_data_b64=pssh, cert_data_b64=None, device=deviceconfig.device_android_generic)

            widevine_license = requests.post(url=cls.lic_url, data=wvdecrypt.get_challenge(), headers=postdata['headers'], params=postdata['params'])
            logger.debug(widevine_license)
            #logger.debug(widevine_license.text)
            license_b64 = b64encode(widevine_license.content)
            wvdecrypt.update_license(license_b64)
            correct, keys = wvdecrypt.start_process()
            if correct:
                for key in keys:
                    tmp = key.split(':')
                    ins.current_data['key'].append({'kid':tmp[0], 'key':tmp[1]})
            logger.debug(correct)
            logger.debug(keys)

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    @classmethod
    def get_pssh(cls, res):
        import xmltodict
        xml = xmltodict.parse(res.text)
        mpd = json.loads(json.dumps(xml))
        logger.debug(d(mpd))
        tracks = mpd['MPD']['Period']['AdaptationSet']
        for video_tracks in tracks:
            if video_tracks.get('@mimeType') == 'video/mp4' or video_tracks.get('@contentType') == 'video':
                for t in video_tracks["ContentProtection"]:
                    if t['@schemeIdUri'].lower() == "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed":
                        pssh = t["cenc:pssh"]
        return pssh