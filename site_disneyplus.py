import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, requests
from urllib import parse
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P, path_data, ToolBaseFile, webdriver, WebDriverWait, EC, By, Keys

from pywidevine.L3.cdm import cdm, deviceconfig
from base64 import b64encode, b64decode
from pywidevine.L3.decrypt.wvdecryptcustom import WvDecrypt


class SiteDisney(SiteBase):
    name = 'disney'
    name_on_filename = 'DP'
    url_regex = request_url_regex = re.compile(r'www\.disneyplus\.com\/ko-kr\/video\/(?P<code>.*?)$')
   
    def __init__(self, db_id, json_filepath):
        super(SiteDisney, self).__init__(db_id, json_filepath)
        self.streaming_protocol = 'hls'

    def prepare(self):
        try:
            self.meta['content_type'] = 'show'
            self.meta['title'] = self.code
            self.meta['episode_number'] = 1
            self.meta['season_number'] = 1

            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].find(f'contentId/{self.code}') != -1:
                    self.meta['source'] = self.get_response(item).json()
                    Utility.write_json(os.path.join(self.temp_dir, f'{self.code}.meta.json'), self.meta['source'])
                    break
            
            
            if self.meta['source']['data']['DmcVideo']['video']['episodeSequenceNumber'] != None:
                self.meta['content_type'] = 'show'
                self.meta['season_number'] = self.meta['source']['data']['DmcVideo']['video']['seasonSequenceNumber']
                self.meta['episode_number'] = self.meta['source']['data']['DmcVideo']['video']['episodeSequenceNumber']
            else:
                self.meta['content_type'] = 'movie'
            
            for item in self.meta['source']['data']['DmcVideo']['video']['texts']:
                if item['field'] == 'title' and item['type'] == 'full':
                    if (self.meta['content_type'] == 'show' and item['sourceEntity'] == 'series') or (self.meta['content_type'] == 'movie' and item['sourceEntity'] == 'program'):
                        self.meta['title'] = item['content']
                        break

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
                    logger.warning(item['request']['url'])
                    
                    if item['request']['url'].find('4250k_CENC') != -1 and m3u8_data['video'] == None:
                        m3u8_data['video'] = {'bandwidth':'1', 'lang':None}
                        m3u8_data['video']['url'] = item['request']['url']
                        m3u8_data['video']['data'] = self.get_response(item).text
                        Utility.write_file(os.path.join(self.temp_dir, f"{self.code}.video.m3u8"), m3u8_data['video']['data'])
                        m3u8_base_url = item['request']['url'][:item['request']['url'].rfind('/')+1]
                    if item['request']['url'].find('_mp4a') != -1 and m3u8_data['audio'] == None:
                        m3u8_data['audio'] = {'bandwidth':'2'}
                        m3u8_data['audio']['url'] = item['request']['url']
                        m3u8_data['audio']['data'] = self.get_response(item).text
                        Utility.write_file(os.path.join(self.temp_dir, f"{self.code}.audio.m3u8"), m3u8_data['audio']['data'])
                        m3u8_data['audio']['lang'] = item['request']['url'].split('/')[-1].split('_')[3]
                    if item['request']['url'].find('_ko_') != -1 and m3u8_data['text'] == None:
                        m3u8_data['text'] = {'lang':'ko', 'mimeType':'text/vtt'}
                        m3u8_data['audio']['url'] = item['request']['url']
                        m3u8_data['text']['data'] = self.get_response(item).text
                        Utility.write_file(os.path.join(self.temp_dir, f"{self.code}.text.m3u8"), m3u8_data['text']['data'])
                    """
                    if item['request']['url'].find('_en_') != -1 and m3u8_data['text'] == None:
                        m3u8_data['text'] = {'lang':'en', 'mimeType':'text/vtt'}
                        m3u8_data['audio']['url'] = item['request']['url']
                        m3u8_data['text']['data'] = self.get_response(item).text
                        Utility.write_file(os.path.join(self.temp_dir, f"{self.code}.text.m3u8"), m3u8_data['text']['data'])
                    """
            for ct in ['video', 'audio', 'text']:
                if m3u8_data[ct] == None:
                    continue
                #logger.debug(d(m3u8_data[ct]['data']))
                m3u8_data[ct]['url_list'] = []
                source_list = {}
                for line in m3u8_data[ct]['data'].split('\n'):
                    if line.startswith('#') == False:
                        key = line.split('/')[0]
                        if key not in source_list:
                            source_list[key] = []
                        source_list[key].append(line)
                max_key = None
                max_urls = 0
                for key, value in source_list.items():
                    if len(value) > max_urls:
                        max_key = key
                        max_urls = len(value)
                m3u8_data[ct]['url_list'] = source_list[max_key]

            self.filepath_mkv = os.path.join(self.temp_dir, f"{self.code}.mkv")
            merge_option = ['-o', f'"{self.filepath_mkv}"']  
            for ct in ['video', 'audio', 'text']:
                if m3u8_data[ct]['contentType'] == None:
                    continue
                m3u8_data[ct]['contentType'] = ct
                self.make_filepath(m3u8_data[ct])
                if ct in ['video', 'audio']:
                    #m3u8_data[ct]['filepath_merge2'] = m3u8_data[ct]['filepath_merge'].replace('decrypt', 'ffmpeg')
                    url = f"{m3u8_base_url}{m3u8_data[ct]['url_list'][0].replace('00/00/00_000.mp4', 'map.mp4')}"
                    init_filepath = os.path.join(self.temp_dir, f"{self.code}_{ct}_init.mp4")
                    Utility.aria2c_download(url, init_filepath)
                    for idx, line in enumerate(m3u8_data[ct]['url_list']):
                        url = f"{m3u8_base_url}{line}"
                        filepath = os.path.join(self.temp_dir, f"{self.code}_{ct}_{str(idx).zfill(5)}.m4s")
                        Utility.aria2c_download(url, filepath)
                    Utility.concat(init_filepath, os.path.join(self.temp_dir, f"{self.code}_{ct}_0*.m4s"), m3u8_data[ct]['filepath_download'])
                        
                    if os.path.exists(m3u8_data[ct]['filepath_download']) and os.path.exists(m3u8_data[ct]['filepath_dump']) == False:
                        Utility.mp4dump(m3u8_data[ct]['filepath_download'], m3u8_data[ct]['filepath_dump'])

                    if os.path.exists(m3u8_data[ct]['filepath_merge']) == False:
                        text = Utility.read_file(m3u8_data[ct]['filepath_dump'])
                        if text.find('default_KID = [') == -1:
                            shutil.copy(m3u8_data[ct]['filepath_download'], m3u8_data[ct]['filepath_merge'])
                        else:
                            kid = text.split('default_KID = [')[1].split(']')[0].replace(' ', '')
                            key = self.find_key(kid)
                            logger.debug(self.data['key'])

                            logger.debug('%s:%s', kid, key)
                            Utility.mp4decrypt(m3u8_data[ct]['filepath_download'], m3u8_data[ct]['filepath_merge'], kid, key)
                            logger.debug(os.path.exists(m3u8_data[ct]['filepath_merge']))

                    #Utility.ffmpeg_copy(m3u8_data[ct]['filepath_merge'], m3u8_data[ct]['filepath_merge2'])
                    if ct == 'audio':
                        merge_option += ['--language', '0:%s' % m3u8_data[ct]['lang']]
                    merge_option += ['"%s"' % m3u8_data[ct]['filepath_merge']]
                else:
                    sub = ''
                    last_time = None
                    logger.error(d(m3u8_data[ct]['url_list']))
                    for idx, line in enumerate(m3u8_data[ct]['url_list']):
                        url = f"{m3u8_base_url}{line}"
                        filepath = os.path.join(self.temp_dir, f"{self.code}_{ct}_{str(idx).zfill(5)}.vtt")
                        Utility.aria2c_download(url, filepath)
                        data = Utility.read_file(filepath)
                        flag_append = False
                        for line_idx, tmp in enumerate(data.split('\n')):
                            if re.match('\d{2}:\d{2}:\d{2}', tmp):
                                break
                        sub += '\n'.join(data.split('\n')[line_idx:])
                        #Utility.write_file(m3u8_data[ct]['filepath_download']+str(idx)+'.txt', sub)
                        #logger.debug(sub)
                    Utility.write_file(m3u8_data[ct]['filepath_download'], sub)
                    Utility.vtt2srt(m3u8_data[ct]['filepath_download'], m3u8_data[ct]['filepath_merge'])
                    merge_option += ['--language', '"0:ko"'] 
                    merge_option += ['--default-track', '"0:yes"']
                    merge_option += ['"%s"' % m3u8_data[ct]['filepath_merge']]

            if self.meta['content_type'] == 'show':
                self.output_filename = u'{title}.S{season_number}E{episode_number}.720p.WEB-DL.AAC.H.264.SW{site}.mkv'.format(
                    title = ToolBaseFile.text_for_filename(self.meta['title']).strip(),
                    season_number = str(self.meta['season_number']).zfill(2),
                    episode_number = str(self.meta['episode_number']).zfill(2),
                    site = self.name_on_filename,
                )
            else:
                self.output_filename = u'{title}.720p.WEB-DL.AAC.H.264.SW{site}.mkv'.format(
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
        



    lic_url = 'https://disney.playback.edge.bamgrid.com/widevine/v1/obtain-license'
    
    #?contentId=20746859&serviceType=0&drmType=Modular&coContentId=10032788770001&deviceType=0&isTest=N

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
            postdata = {'headers':{}, 'data':{}, 'cookies':{}, 'params':{}}
            for item in reversed(request_list):
                if item['request']['method'] == 'GET' and item['request']['url'].find('4250k') != -1 and item['request']['url'].find('m3u8') != -1:
                    res = cls.get_response_cls(item)
                    pssh = cls.get_pssh(res)
                    logger.error(pssh)
                    break
            for item in request_list:
                if item['request']['method'] == 'POST' and item['request']['url'].startswith(cls.lic_url):
                    lic_url = item['request']['url']
                    for h in item['request']['headers']:
                        postdata['headers'][h['name']] = h['value']
                    for h in item['request']['queryString']:
                        postdata['params'][h['name']] = h['value']

            logger.debug(d(postdata))
            wvdecrypt = WvDecrypt(init_data_b64=pssh, cert_data_b64=None, device=deviceconfig.device_android_generic)

            widevine_license = requests.post(url=cls.lic_url, data=wvdecrypt.get_challenge(), headers=postdata['headers'], params=postdata['params'])
            logger.debug(widevine_license)
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
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    @classmethod
    def get_pssh(cls, res):
        text = res.text
        tmps = text.split('\n')
        for t in tmps:
            if t.startswith('#EXT-X-KEY:METHOD=SAMPLE-AES') and t.lower().find('urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed') != -1:
                pssh = t.split('base64,')[1].split('"')[0]
                break


        #EXT-X-KEY:METHOD=SAMPLE-AES,KEYID=397e6d24-df5f-4e7f-ba49-3b9cf45f5021,URI="data:text/plain;base64,AAAAS3Bzc2gAAAAA7e+LqXnWSs6jyCfc1R0h7QAAACsIARIQOX5tJN9fTn+6STuc9F9QIRoJY29yZXRydXN0IggyMDc0Njg1OTgA",KEYFORMAT="urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed",KEYFORMATVERSIONS="1"
        return pssh
