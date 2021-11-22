import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, webdriver, WebDriverWait, EC, By, Keys

class SiteTving(SiteBase):
    name = 'tving'
    name_on_filename = 'TV'
    url_regex = request_url_regex = re.compile(r'tving\.com\/(vod|movie)\/player\/(?P<code>.*?)$')
    
    def __init__(self, db_id, json_filepath):
        super(SiteTving, self).__init__(db_id, json_filepath)

    def prepare(self):
        self.meta['season_number'] = 1
        try:
            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].startswith('https://api.tving.com/v2a/media/stream/info'):
                    res = self.get_response(item)
                    self.meta['source'] = res.json()
                    Utility.write_json(os.path.join(self.temp_dir, f'{self.code}.meta.json'), self.meta['source'])
                    break
            self.meta['title'] = self.meta['source']['body']['content']['info']['vod_name']['ko']
            frequency = self.meta['source']['body']['content'].get('frequency')
            if frequency == None:
                self.meta['content_type'] = 'movie'
            else:
                self.meta['content_type'] = 'show'
                self.meta['episode_number'] = frequency
            self.add_log("타입 : %s" % self.meta['content_type'])
            if self.meta['content_type'] == 'show':
                regex_list = [
                    '(?P<title>.*?)\s?시즌\s?(?P<season>\d+)',
                    '(?P<title>.*?)\s?(?P<episode>\d+)\s?화',
                    '(?P<title>.*?)\s?(?P<season>\d+)\s?기',
                    '(?P<title>.*?)\sSeason\s(?P<season>\d+)$',
                ]
                for regex in regex_list:
                    match = re.match(regex, self.meta['title'])
                    if match:
                        self.meta['title'] = match.group('title')
                        if match.groupdict().get('season'):
                            self.meta['season_number'] = int(match.groupdict().get('season'))
                        break
                log = f"제목: [{self.meta['title']}] 시즌:[{self.meta['season_number']}], 에피:[{self.meta['episode_number']}]"
                logger.debug(log)
                self.add_log(log)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    @classmethod
    def do_driver_action(cls, ins):
        WebDriverWait(ins.driver, 30).until(lambda driver: driver.find_element_by_class_name('cjp-quality')).find_element_by_tag_name('button').click()
        WebDriverWait(ins.driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, '//div[@class="cjp-quality-menu"]/div[1]'))
        ).click()
        ins.stop_timestamp = time.time()


        