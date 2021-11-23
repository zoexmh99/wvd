import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, webdriver, WebDriverWait, EC, By, Keys

class SiteSerieson(SiteBase):
    name = 'serieson'
    name_on_filename = 'SO'
    url_regex = request_url_regex = re.compile(r'serieson\.naver\.com\/v2\/movie\/(?P<code>\d+)')


    def __init__(self, db_id, json_filepath):
        super(SiteSerieson, self).__init__(db_id, json_filepath)

    def prepare(self):
        try:
            self.meta['content_type'] = 'movie'
            self.meta['title'] = self.code
            return
            if self.db_item.url.find('MOVIE') != -1:
                self.meta['content_type'] = 'movie'
            elif self.db_item.url.find('TVSHOW') != -1:
                self.meta['content_type'] = 'show'

            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].find(f'discover/titles/{self.code}?') != -1:
                    self.meta['source'] = self.get_response(item).json()
                    Utility.write_json(os.path.join(self.temp_dir, f'{self.code}.meta.json'), self.meta['source'])
                    self.meta['title'] = self.meta['source']['data']['title']
                    if self.meta['source']['data']['as'] == 'MOVIE':
                        break
                elif item['request']['method'] == 'GET' and item['request']['url'].find(f'discover/titles/') != -1:
                    self.meta['title'] = self.get_response(item).json()['data']['title']
                    break
            
            if self.meta['source']['data']['as'] == 'EPISODE':
                self.meta['content_type'] = 'show'
                self.meta['season_number'] = self.meta['source']['data']['season']
                self.meta['episode_number'] = self.meta['source']['data']['episode']
                log = f"제목: [{self.meta['title']}] 시즌:[{self.meta['season_number']}], 에피:[{self.meta['episode_number']}]"
                
            elif self.meta['source']['data']['as'] == 'MOVIE':
                self.meta['content_type'] = 'movie'
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
                EC.element_to_be_clickable((By.XPATH, '/html/body/div/div[2]/div[1]/div[1]/div/div/div/div[4]/div[1]/button'))
            )
            time.sleep(2)
            tag.click()
            ins.stop_timestamp = time.time()
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())


