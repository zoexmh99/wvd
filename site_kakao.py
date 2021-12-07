import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, requests
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, path_data, ToolBaseFile, webdriver, WebDriverWait, EC, By, Keys

from pywidevine.L3.cdm import cdm, deviceconfig
from base64 import b64encode, b64decode
from pywidevine.L3.decrypt.wvdecryptcustom import WvDecrypt

from .model_auto import ModelAutoItem
class SiteKakao(SiteBase):
    name = 'kakao'
    name_on_filename = 'KK'
    url_regex = re.compile(r'kakao\.com\/channel\/\d+\/cliplink\/(?P<code>.*?)($|\?)')
    request_url_regex = re.compile(r'kakao\.com\/embed\/player\/cliplink\/(?P<code>.*?)\?')
    auto_video_stop = False
    def __init__(self, db_id, json_filepath):
        super(SiteKakao, self).__init__(db_id, json_filepath)
        
    # 카카오 유일
    @classmethod
    def get_request_url(cls, url):
        match = cls.url_regex.search(url)
        if match:
            return f"https://tv.kakao.com/embed/player/cliplink/{match.group('code')}?service=kakao_tv&section=channel&autoplay=1&profile=HIGH4&wmode=transparent"
        return url

    def prepare(self):
        try:
            auto_db_item = ModelAutoItem.get_by_site_code(self.name, self.code)
            logger.warning(auto_db_item)

            if auto_db_item != None:
                self.meta['content_type'] = 'show'
                self.meta['season_number'] = 1
                self.meta['episode_number'] = auto_db_item.episode_no
                self.meta['title'] = auto_db_item.show_title
                if self.meta['title'] == '찐경규':
                    self.meta['episode_number'] += -1
                elif self.meta['title'] == '안소희':
                    self.meta['episode_number'] += 1
            else:    
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
            log = f"제목: [{self.meta['title']}] 시즌:[{self.meta['season_number']}], 에피:[{self.meta['episode_number']}]"
            logger.debug(log)
            self.add_log(log)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    @classmethod
    def do_driver_action(cls, ins):
        try:
            tag = WebDriverWait(ins.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="adSkipBtn"]'))
            ).click()
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())
        
        try:    
            tag = WebDriverWait(ins.driver, 5).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'link_play'))
            )
            time.sleep(2)
            tag.click()
            time.sleep(2)
            #ins.stop_timestamp = time.time()
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())

        ins.video_stop()


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
            postdata = {'headers':{}, 'data':{}}
            lic_url = 'https://drm-license.kakaopage.com/v1/license'
            for item in reversed(request_list):
                if item['request']['method'] == 'GET' and item['request']['url'].find('.mpd') != -1:
                    res = cls.get_response_cls(item)
                    pssh = cls.get_pssh(res)
                    logger.error(pssh)
                    #break
                elif item['request']['method'] == 'POST' and item['request']['url'].startswith(lic_url):
                    for h in item['request']['headers']:
                        postdata['headers'][h['name']] = h['value']
                    for h in item['request']['postData']['params']:
                        postdata['data'][h['name']] = h['value']

                if pssh is not None and len(postdata['headers'].keys()) > 0:
                    break
            
            logger.debug(postdata)
            wvdecrypt = WvDecrypt(init_data_b64=pssh, cert_data_b64=None, device=deviceconfig.device_android_generic) 

            payload = wvdecrypt.get_challenge()
            payload = b64encode(payload)
            payload = payload.decode('ascii')
            postdata['data']['payload'] = payload

            widevine_license = requests.post(url=lic_url, data=postdata['data'], headers=postdata['headers'])

            data = widevine_license.json()
            license_b64 = data['payload']
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