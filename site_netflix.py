import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, webdriver, WebDriverWait, EC, By, Keys

class SiteNetflix(SiteBase):
    url_regex = request_url_regex = re.compile(r'netflix\.com\/watch\/(?P<code>.*?)($|\?)')
    name = 'netflix'
    name_on_filename = 'NF'

    def __init__(self, db_id, json_filepath):
        super(SiteNetflix, self).__init__(db_id, json_filepath)


    def prepare(self):
        try:
            self.meta['content_type'] = 'movie'
            self.meta['title'] = self.code
            if 'title' in self.data:
                match = re.match('(?P<title>.*?)\s?시즌\s?(?P<season>\d+):\s(?P<episode>\d+)화',self.data['title'])
                if match:
                    self.meta['content_type'] = 'show'
                    self.meta['title'] = match.group('title')
                    self.meta['season_number'] = int(match.group('season'))
                    self.meta['episode_number'] = int(match.group('episode'))
                else:
                    self.meta['title'] = self.data['title']
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    def find_mpd(self):
        pass
    
    def make_download_info(self):
        try:
            json_filepath = os.path.join(self.temp_dir, f'{self.code}.json')
            if os.path.exists(json_filepath):
                data = Utility.read_json(json_filepath)
            else:
                user_auth_data = {
                    'scheme': 'EMAIL_PASSWORD',
                    'authdata': {
                        'email': ModelSetting.get('client_netflix_id'),
                        'password': ModelSetting.get('client_netflix_pw'),
                    }
                }
                import pymsl
                client = pymsl.MslClient(user_auth_data, languages=['ko_KR'])
                data = client.load_manifest(int(self.code))
                Utility.write_json(json_filepath, data)

            for stream in reversed(data['result']['video_tracks'][0]['streams']):
                if stream['content_profile'] == 'playready-h264hpl40-dash':
                    self.download_list['video'].append(self.make_filepath({'contentType':'video', 'lang':None, 'url':stream['urls'][0]['url'], 'bandwidth':stream['bitrate'], 'height':1080, 'codec_name':'H.264'}))
                    break
            
            max_bitrate = 0
            max_stream = None
            max_audio = None
            for audio in data['result']['audio_tracks']:
                #if audio['profile'] == 'dd-5.1-dash' and audio['languageDescription'].find(u'[원어]') != -1:
                if audio['languageDescription'].find('[원어]') != -1:
                    for stream in audio['streams']:
                        if stream['bitrate'] >= max_bitrate:
                            max_stream = stream
                            max_audio = audio
            if max_stream:
                tmp = self.make_filepath({'contentType':'audio', 'lang':max_stream['language'], 'url':stream['urls'][0]['url'], 'bandwidth':stream['bitrate'], 'cenc':False, 'codec_name':''})
                
                if max_audio['codecName'] == 'DDPLUS':
                    tmp['codec_name'] = 'DDP'
                tmp['codec_name'] += max_audio['channels']
                if max_stream['surroundFormatLabel'] == 'Atmos':
                    tmp['codec_name'] += '.Atmos'
                self.download_list['audio'].append(tmp)

            for text in data['result']['timedtexttracks']:
                if 'webvtt-lssdh-ios8' not in text['ttDownloadables']:
                    continue
                self.download_list['text'].append(self.make_filepath({
                    'contentType':'text', 
                    'mimeType':'text/vtt/netflix', 
                    'lang':text['language'], 
                    'url':list(text['ttDownloadables']['webvtt-lssdh-ios8']['downloadUrls'].values())[1], 
                    'force' : text['isForcedNarrative']
                }))
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())    



    @classmethod
    def do_driver_action(cls, ins):
        # Play 버튼이 생기는 경우가 있다.
        try:
            tag = WebDriverWait(ins.driver, 10).until(lambda driver: driver.find_element_by_xpath('//button[@aria-label="Play"]'))
            tag.click()
        except:
            logger.debug("넷플 play 버튼 없나 봄")

        tag = WebDriverWait(ins.driver, 30).until(lambda driver: driver.find_element_by_xpath('//div[@data-uia="video-title"]'))
        logger.debug(tag.get_attribute('innerText'))
        ins.current_data['title'] = tag.get_attribute('innerText')
        ins.video_stop()
        
        