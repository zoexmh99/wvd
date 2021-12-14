import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, requests
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, path_data, ToolBaseFile, webdriver, WebDriverWait, EC, By, Keys


from pywidevine.cdm import cdm, deviceconfig
from base64 import b64encode, b64decode
from pywidevine.decrypt.wvdecryptcustom import WvDecrypt


class SiteCoupang(SiteBase):
    name = 'coupang'
    name_on_filename = 'CP'
    url_regex = request_url_regex = re.compile(r'coupangplay\.com\/play\/(?P<code>.*)\/(movie|episode)')

    def __init__(self, db_id, json_filepath):
        super(SiteCoupang, self).__init__(db_id, json_filepath)

    def prepare(self):
        try:
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

    

    """
    # 플레이버튼 나옴
    # 플레이 하지 않아도 로딩됨
    @classmethod
    def do_driver_action(cls, ins):
        try:
            WebDriverWait(ins.driver, 5).until(lambda driver: driver.find_element_by_xpath('//div[@class="icon icon-play first-play"]')).click()
            logger.debug("클릭")
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())
    """


    lic_url = 'https://www.coupangplay.com/api/playback/license'

    
    @classmethod
    def do_make_key(cls, ins):
        try:
            # save
            """
            filepath = os.path.join(path_data, package_name, 'server', f"{ins.current_data['site']}_{ins.current_data['code']}.json")
            if os.path.exists(filepath) == False:
                if os.path.exists(os.path.dirname(filepath)) == False:
                    os.makedirs(os.path.dirname(filepath))
                logger.warning(f"저장 : {filepath}")
                Utility.write_json(filepath, ins.current_data)
            """

            request_list = ins.current_data['har']['log']['entries']
            pssh = None
            headers = {}
            params = {}
            cookies = {}
            lic_url = 'https://www.coupangplay.com/api/playback/license'
            for item in reversed(request_list):
                if item['request']['method'] == 'GET' and item['request']['url'].find('.mpd') != -1:
                    res = cls.get_response_cls(item)
                    pssh = cls.get_pssh(res)
                    logger.error(pssh)
                    #break
                elif item['request']['method'] == 'POST' and item['request']['url'].startswith(lic_url):
                    for h in item['request']['headers']:
                        if h['name'] != 'Cookie':
                            headers[h['name']] = h['value']
                    for h in item['request']['queryString']:
                        params[h['name']] = h['value']
                    for h in item['request']['cookies']:
                        cookies[h['name']] = h['value']

                if pssh is not None and len(headers.keys()) > 0:
                    break
            logger.debug(headers)
            logger.debug(params)
            logger.debug(cookies)

            wvdecrypt = WvDecrypt(init_data_b64=pssh, cert_data_b64=None, device=deviceconfig.device_chromecdm_2209)            
            widevine_license = requests.post(url=lic_url, data=wvdecrypt.get_challenge(), headers=headers, params=params, cookies=cookies)
            #logger.debug(widevine_license)
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
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())
