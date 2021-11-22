import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from urllib import parse
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, webdriver, WebDriverWait, EC, By, Keys, path_app_root, ToolBaseFile

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
            merge_option = ['-o', '"%s"' % self.filepath_mkv.replace(path_app_root, '.')]  
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
                Utility.window_concat(init_filepath, os.path.join(self.temp_dir, f"{self.code}_{ct}_0*.m4s"), m3u8_data[ct]['filepath_download'])
                    
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
                merge_option += ['"%s"' % m3u8_data[ct]['filepath_merge'].replace(path_app_root, '.')]
                
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
        