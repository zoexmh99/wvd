import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, requests
from urllib import parse
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, path_data, ToolBaseFile, webdriver, WebDriverWait, EC, By, Keys

from pywidevine.L3.cdm import cdm, deviceconfig
from base64 import b64encode, b64decode
from pywidevine.L3.decrypt.wvdecryptcustom import WvDecrypt


class SiteSeezn(SiteBase):
    name = 'seezn'
    name_on_filename = 'SZ'
    url_regex = request_url_regex = re.compile('www\.seezntv\.com\/vodDetail\?content_id=-?(?P<code>\d+)')
   
    def __init__(self, db_id, json_filepath):
        super(SiteSeezn, self).__init__(db_id, json_filepath)
        self.streaming_protocol = 'hls'

    def prepare(self):
        try:
            self.meta['content_type'] = 'show'
            self.meta['title'] = self.code
            self.meta['episode_number'] = 1
            self.meta['season_number'] = 1
            logger.debug(self.code)
            for item in self.data['har']['log']['entries']:
                #if item['request']['method'] == 'GET' and item['request']['url'].find(f'vod_detail?content_id={self.code}') != -1:
                if item['request']['method'] == 'GET' and item['request']['url'].find(f'https://api.seezntv.com/svc/cmsMenu/app6/api/vod_detail') != -1:
                
                    logger.debug(item['request']['url'])
                    self.meta['source'] = self.get_response(item).json()
                    Utility.write_json(os.path.join(self.temp_dir, f'{self.code}.meta.json'), self.meta['source'])
                    break
            title = parse.unquote_plus(self.meta['source']['data']['title'])
            series_title = parse.unquote_plus(self.meta['source']['data']['series_title'])
            logger.error(title)
            logger.error(series_title)
            if title == series_title:
                self.meta['content_type'] = 'movie'
                self.meta['title'] = title
            else:
                self.meta['title'] = series_title
                self.meta['season_number'] = 1
                self.meta['episode_number'] = 1
                match = re.match('(?P<title>.*?)\s?시즌\s?(?P<season>\d+)', series_title)
                if match:
                    self.meta['season_number'] = int(match.group('season'))
                    self.meta['title'] = match.group('title').strip()
                match = re.match('(?P<episode>\d+)', title)
                if match:
                    self.meta['episode_number'] = int(match.group('episode'))
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    def download_m3u8(self):
        
        try:
            m3u8_base_url = None
            request_list = self.data['har']['log']['entries']
            m3u8_data = {'video':None, 'audio':None, 'text':None}
            for item in reversed(request_list):
                if item['request']['method'] == 'GET' and item['request']['url'].find('.m3u8') != -1:
                    if item['request']['url'].find('video_DRM.m3u8') != -1 and m3u8_data['video'] == None:
                        m3u8_data['video'] = {'bandwidth':'1', 'lang':None}
                        m3u8_data['video']['url'] = item['request']['url']
                        m3u8_data['video']['data'] = self.get_response(item).text
                        Utility.write_file(os.path.join(self.temp_dir, f"{self.code}.video.m3u8"), m3u8_data['video']['data'])
                        m3u8_base_url = item['request']['url'][:item['request']['url'].rfind('/')+1]
                    if item['request']['url'].find('audio_DRM.m3u8') != -1 and m3u8_data['audio'] == None:
                        m3u8_data['audio'] = {'bandwidth':'2'}
                        m3u8_data['audio']['url'] = item['request']['url']
                        m3u8_data['audio']['data'] = self.get_response(item).text
                        Utility.write_file(os.path.join(self.temp_dir, f"{self.code}.audio.m3u8"), m3u8_data['audio']['data'])
                        m3u8_data['audio']['lang'] = 'ko'
            
            for ct in ['video', 'audio', 'text']:
                if m3u8_data[ct] == None:
                    continue
                m3u8_data[ct]['url_list'] = []
                source_list = {}
                for line in m3u8_data[ct]['data'].split('\n'):
                    if line.startswith('#EXT-X-MAP'):
                        m3u8_data[ct]['url_list'].append(line.split('"')[1])
                    if line.startswith('#') == False:
                        m3u8_data[ct]['url_list'].append(line)

            self.filepath_mkv = os.path.join(self.temp_dir, f"{self.code}.mkv")
            merge_option = ['-o', '"%s"' % self.filepath_mkv]  
            for ct in ['video', 'audio']:
                m3u8_data[ct]['contentType'] = ct
                self.make_filepath(m3u8_data[ct])
                
                url = f"{m3u8_base_url}{m3u8_data[ct]['url_list'][0]}"
                init_filepath = os.path.join(self.temp_dir, f"{self.code}_{ct}_init.mp4")
                Utility.aria2c_download(url, init_filepath)
                for idx, line in enumerate(m3u8_data[ct]['url_list'][1:]):
                    url = f"{m3u8_base_url}{line}"
                    filepath = os.path.join(self.temp_dir, f"{self.code}_{ct}_{str(idx).zfill(5)}.m4s")
                    Utility.aria2c_download(url, filepath)
                Utility.concat(init_filepath, os.path.join(self.temp_dir, f"{self.code}_{ct}_0*.m4s"), m3u8_data[ct]['filepath_download'])
                    
                if os.path.exists(m3u8_data[ct]['filepath_download']) and os.path.exists(m3u8_data[ct]['filepath_dump']) == False:
                    Utility.mp4dump(m3u8_data[ct]['filepath_download'], m3u8_data[ct]['filepath_dump'])

                if os.path.exists(m3u8_data[ct]['filepath_merge']) == False:
                    text = Utility.read_file(m3u8_data[ct]['filepath_dump'])
                    if text.find('default_KID = [') == -1:
                        shutil.copy(m3u8_data[ct]['filepath_download'], m3u8_data[ct]['filepath_merge'])
                    else:
                        kid = text.split('default_KID = [')[1].split(']')[0].replace(' ', '')
                        key = self.find_key(kid)
                        Utility.mp4decrypt(m3u8_data[ct]['filepath_download'], m3u8_data[ct]['filepath_merge'], kid, key)
                        logger.debug(os.path.exists(m3u8_data[ct]['filepath_merge']))

                #if ct == 'audio':
                #    merge_option += ['--language', '0:%s' % m3u8_data[ct]['lang']]
                merge_option += ['"%s"' % m3u8_data[ct]['filepath_merge']]
                
            if self.meta['content_type'] == 'show':
                self.output_filename = u'{title}.S{season_number}E{episode_number}.1080p.WEB-DL.AAC.H.264.SW{site}.mkv'.format(
                    title = ToolBaseFile.text_for_filename(self.meta['title']).strip(),
                    season_number = str(self.meta['season_number']).zfill(2),
                    episode_number = str(self.meta['episode_number']).zfill(2),
                    site = self.name_on_filename,
                )
            else:
                self.output_filename = u'{title}.1080p.WEB-DL.AAC.H.264.SW{site}.mkv'.format(
                    title = ToolBaseFile.text_for_filename(self.meta['title']).strip(),
                    site = self.name_on_filename,
                )
            logger.warning(self.output_filename)
            self.filepath_output = os.path.join(Utility.output_dir, self.output_filename)
            if os.path.exists(self.filepath_output) == False:
                logger.error(merge_option)
                Utility.mkvmerge(merge_option)
                shutil.move(self.filepath_mkv, self.filepath_output)
                self.add_log(f'파일 생성: {self.output_filename}')
            return True
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
        


    lic_url = 'https://api.seezntv.com/svc/widevine/LIC_REQ_PRE'
    
    #?contentId=20746859&serviceType=0&drmType=Modular&coContentId=10032788770001&deviceType=0&isTest=N

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
                if item['request']['method'] == 'GET' and item['request']['url'].find('DRM.m3u8') != -1:
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
        text = res.text
        tmps = text.split('\n')
        for t in tmps:
            if t.startswith('#EXT-X-KEY:METHOD=SAMPLE-AES') and t.lower().find('urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed') != -1:
                pssh = t.split('base64,')[1].split('"')[0]
                break


        #EXT-X-KEY:METHOD=SAMPLE-AES,KEYID=397e6d24-df5f-4e7f-ba49-3b9cf45f5021,URI="data:text/plain;base64,AAAAS3Bzc2gAAAAA7e+LqXnWSs6jyCfc1R0h7QAAACsIARIQOX5tJN9fTn+6STuc9F9QIRoJY29yZXRydXN0IggyMDc0Njg1OTgA",KEYFORMAT="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed",KEYFORMATVERSIONS="1"
        return pssh

    