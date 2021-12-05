import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, requests
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, path_data, ToolBaseFile, webdriver, WebDriverWait, EC, By, Keys

from pywidevine.L3.cdm import cdm, deviceconfig
from base64 import b64encode, b64decode
from pywidevine.L3.decrypt.wvdecryptcustom import WvDecrypt


class SiteWavve(SiteBase):
    name = 'wavve'
    name_on_filename = 'WV'
    url_regex = request_url_regex = re.compile(r'wavve\.com\/player\/(movie\?movieid=|vod\?contentid=|vod\?programid=.*?&contentid=)(?P<code>.*?)($|&)')

    def __init__(self, db_id, json_filepath):
        super(SiteWavve, self).__init__(db_id, json_filepath)

   
    def prepare(self):
        try:
            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].find(f'contents/{self.code}?') != -1:
                    res = self.get_response(item)
                    self.meta['source'] = res.json()
                    Utility.write_json(os.path.join(self.temp_dir, f'{self.code}.meta.json'), self.meta['source'])
                    break
            if 'programid' in self.meta['source']:
                self.meta['content_type'] = 'show'
                self.meta['title'] = self.meta['source']['programtitle']
                self.meta['episode_number'] = int(self.meta['source']['episodenumber'])
                self.meta['season_number'] = int(self.meta['source']['seasontitle'].split('시즌')[-1])
                log = f"제목: [{self.meta['title']}] 시즌:[{self.meta['season_number']}], 에피:[{self.meta['episode_number']}]"
            else:
                self.meta['content_type'] = 'movie'
                self.meta['title'] = self.meta['source']['title']
                log = f"제목: [{self.meta['title']}]"
            logger.debug(log)
            self.add_log(log)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    @classmethod
    def do_driver_action(cls, ins):
        try:
            tag = WebDriverWait(ins.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@class="btn-play btn-default font-out"]'))
            )
            time.sleep(1)
            tag.click()
            ins.stop_timestamp = time.time()
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())


    lic_url = 'https://license.wavve.com/ri/licenseManager.do'
    