import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, webdriver, WebDriverWait, EC, By, Keys


class SiteWatcha(SiteBase):
    name = 'watcha'
    name_on_filename = 'WC'
    url_regex = request_url_regex = re.compile(r'watcha\.com\/watch\/(?P<code>.*?)($|\?)')

    def __init__(self, db_id, json_filepath):
        super(SiteWatcha, self).__init__(db_id, json_filepath)

    def prepare(self):
        try:
            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].find('%s.json' % self.code) != -1:
                    res = self.get_response(item)
                    self.meta['source'] = res.json()
                    Utility.write_json(self.meta['source'], os.path.join(self.temp_dir, '{code}.meta.json'.format(code=self.code)))
                """
                if item['request']['method'] == 'GET' and item['request']['url'].find('tv_episodes.json?all=true') != -1:
                    res = self.get_response(item)
                    tmp = res.json()
                    for code in tmp['tv_episode_codes']:
                        P.logic.get_module('download').queue_chrome_request.add_request_url('https://watcha.com/watch/%s' % code, '')
                    break
                """
            self.meta['title'] = self.meta['source']['title']
            if self.meta['source']['content_type'] == 'tv_episodes':
                self.meta['content_type'] = 'show'
                self.meta['season_number'] = 1
                regex_list = [
                    '(?P<title>.*?)\s?시즌\s?(?P<season>\d+)',
                    '(?P<title>.*?):\s에피소드\s?(?P<episode>\d+)',
                    '(?P<title>.*?)\s?(?P<season>\d+)\s?기',
                    '(?P<title>.*?)\sSeason\s(?P<season>\d+)$',
                ]
                
                for regex in regex_list:
                    match = re.match(regex, self.meta['title'])
                    if match:
                        self.meta['title'] = match.group('title').strip()
                        if match.groupdict().get('season'):
                            self.meta['season_number'] = int(match.groupdict().get('season'))
                        break
                self.meta['episode_number'] = self.meta['source']['tv_episode_formal_number']
                log = f"제목: [{self.meta['title']}] 시즌:[{self.meta['season_number']}], 에피:[{self.meta['episode_number']}]"
            else:
                self.meta['content_type'] = 'movie'
                log = f"제목: [{self.meta['title']}]"
            logger.debug(log)
            self.add_log(log)

        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

     
