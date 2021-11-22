import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, webdriver, WebDriverWait, EC, By, Keys

class SiteKakao(SiteBase):
    name = 'kakao'
    name_on_filename = 'KK'
    url_regex = re.compile(r'kakao\.com\/channel\/\d+\/cliplink\/(?P<code>.*?)$')
    request_url_regex = re.compile(r'kakao\.com\/embed\/player\/cliplink\/(?P<code>.*?)\?')
    
    def __init__(self, db_id, json_filepath):
        super(SiteKakao, self).__init__(db_id, json_filepath)
        
    # 카카오 유일
    @classmethod
    def get_request_url(cls, url):
        match = cls.url_regex.search(url)
        if match:
            return f"https://tv.kakao.com/embed/player/cliplink/{match.group('code')}?service=kakao_tv&section=channel&autoplay=1&profile=HIGH&wmode=transparent"
        return url

    def prepare(self):
        try:
            self.meta['content_type'] = 'show'
            self.meta['season_number'] = 1
            self.meta['episode_number'] = 1
            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].find(f'api/v1/ft/playmeta/cliplink/{self.code}?') != -1:
                    res = self.get_response(item)
                    self.meta['source'] = res.json()
                    Utility.write_json(os.path.join(self.temp_dir, f'{self.code}.meta.json'), self.meta['source'])
                    break
            self.meta['title'] = self.meta['source']['clipLink']['channel']['name']
            tmp = self.meta['source']['clipLink']['displayTitle']
            match = re.match('\d+', tmp)
            if match:
                self.meta['episode_number'] = int(match.group(0))
            log = f"제목: [{self.meta['title']}] 시즌:[{self.meta['season_number']}], 에피:[{self.meta['episode_number']}]"
            logger.debug(log)
            self.add_log(log)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    @classmethod
    def do_driver_action(cls, ins):
        try:
            tag = WebDriverWait(ins.driver, 30).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'link_play'))
            )
            time.sleep(2)
            tag.click()
            ins.stop_timestamp = time.time()
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())
