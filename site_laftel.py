import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P

class SiteLaftel(SiteBase):
    name = 'laftel'
    name_on_filename = 'LT'
    url_regex = request_url_regex = re.compile(r'laftel\.net(.*?)\/(?P<code>\d+)$')

    def __init__(self, db_id, json_filepath):
        super(SiteLaftel, self).__init__(db_id, json_filepath)
        
    def prepare(self):
        try:
            match = re.search(r'.*?\/(?P<program>\d+)\/(?P<code>\d+)$', self.db_item.url)
            logger.debug(match.group('program'))
            meta = {}
            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].find(f"https://laftel.net/api/episodes/v2/{self.code}/") != -1:
                    meta['code'] = self.get_response(item).json()
                    item['request']['url'] = f"https://laftel.net/api/items/v1/{match.group('program')}/"
                    meta['program'] = self.get_response(item).json()
                    self.meta['source'] = meta
                    Utility.write_json(os.path.join(self.temp_dir, f'{self.code}.meta.json'), self.meta['source'])
                    break
            
            self.meta['title'] = self.meta['source']['code']['title']
            if self.meta['source']['program']['animation_info']['medium'] == '극장판':
                self.meta['content_type'] = 'movie'
            else:
                self.meta['content_type'] = 'show'
                self.meta['season_number'] = -1
                self.meta['episode_number'] = int(self.meta['source']['code']['episode_num'])
                regex = ['(?P<title>.*?)\s?(?P<season>\d+)기', '(?P<title>.*?)\s?part\s?(?P<season>\d+)', '(?P<title>.*?)\s?시즌\s?(?P<season>\d+)']
                for r in regex:
                    match = re.match(r, self.meta['title'])
                    if match:
                        self.meta['title'] = match.group('title').strip()
                        self.meta['season_number'] = int(match.group('season'))
                if self.meta['season_number'] == -1:
                    tmp = self.meta['source']['program']['name'].replace(self.meta['source']['code']['title'], '').strip()
                    logger.debug(self.meta['source']['program']['name'])
                    logger.debug(self.meta['source']['code']['title'])
                    logger.warning(tmp)
                    try:
                        self.meta['season_number'] = int(re.search('\d+', tmp).group(0))
                    except:
                        self.meta['season_number'] = 1
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    lic_url = 'https://license.pallycon.com/ri/licenseManager.do'