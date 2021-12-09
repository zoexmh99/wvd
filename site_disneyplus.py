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
                        #m3u8_data['video']['url'] = 'http://vod-ftc-ap-north-2.media.dssott.com/ps01/disney/2cd95643-36c3-4e5c-ab67-9e7c51567839/r/composite_8500k_CENC_CTR_FHD_SDR_a5794f70-b9ff-46e6-8c05-27e2f2f7c4e0_374ae605-3509-4966-9203-410920769578.m3u8'
                        #item['request']['url'] = m3u8_data['video']['url']
                        m3u8_data['video']['data'] = self.get_response(item).text
                        Utility.write_file(os.path.join(self.temp_dir, f"{self.code}.video.m3u8"), m3u8_data['video']['data'])
                        m3u8_base_url = item['request']['url'][:item['request']['url'].rfind('/')+1]
                    elif item['request']['url'].find('_mp4a') != -1 and m3u8_data['audio'] == None:
                        m3u8_data['audio'] = {'bandwidth':'2'}
                        m3u8_data['audio']['url'] = item['request']['url']
                        m3u8_data['audio']['data'] = self.get_response(item).text
                        Utility.write_file(os.path.join(self.temp_dir, f"{self.code}.audio.m3u8"), m3u8_data['audio']['data'])
                        m3u8_data['audio']['lang'] = item['request']['url'].split('/')[-1].split('_')[3]
                    elif item['request']['url'].find('_ko_') != -1 and m3u8_data['text'] == None:
                        #logger.warning(item['request']['url'])
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
            #logger.debug(d(m3u8_data))
            for ct in ['video', 'audio', 'text']:
                ##if m3u8_data[ct]['contentType'] == None:
                #    continue
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
                    #logger.warning(d(m3u8_data[ct]['url_list']))
                    for idx, line in enumerate(m3u8_data[ct]['url_list']):
                        url = f"{m3u8_base_url}{line}"
                        filepath = os.path.join(self.temp_dir, f"{self.code}_{ct}_{str(idx).zfill(5)}.vtt")
                        #logger.debug(url)
                        #logger.debug(filepath)
                        Utility.aria2c_download(url, filepath)
                        data = Utility.read_file(filepath)
                        #logger.debug(data)
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

            #pssh = 'AAAAMnBzc2gAAAAA7e+LqXnWSs6jyCfc1R0h7QAAABISEK1u7AX3eEPDiEf3tCcPP+U='
            #pssh = 'AAAAMnBzc2gAAAAA7e+LqXnWSs6jyCfc1R0h7QAAABISENZJf1J2DELjvKQYl+HaJg4='
            #logger.debug(d(postdata))
            #import html
            #import urllib.parse
            
            #html.unescape(json_string)
            #postdata['headers'] = {'User-Agent': 'BAMSDK/v6.1.0 (disney-svod-3d9324fc 1.16.0.0; v3.0/v6.1.0; android; tv)', 'Accept-Encoding': 'gzip', 'Accept': '*/*', 'Connection': 'keep-alive', 'x-application-version': 'google', 'x-bamsdk-platform-id': 'android-tv', 'x-bamsdk-client-id': 'disney-svod-3d9324fc', 'x-bamsdk-platform': 'android-tv', 'x-bamsdk-version': '6.1.0', 'Authorization': 'Bearer eyJ6aXAiOiJERUYiLCJraWQiOiJ0Vy10M2ZQUTJEN2Q0YlBWTU1rSkd4dkJlZ0ZXQkdXek5KcFFtOGRJMWYwIiwiY3R5IjoiSldUIiwiZW5jIjoiQzIwUCIsImFsZyI6ImRpciJ9..yCTacR3paMnWq5nb.EWmJ6kLXQwigLiRiICeYc4iYLR9uSBV9ZZOmkF4nfVjm4BDJdm2gLQXt0M2jIZCXhQOWbUby9UN4TvlV-zlZKw0w2EHnF68A5fJZS_5tccJLArqQnsr15NKuVSyoAG-G0F7DraSDNcNvzpm_T1Hp65FC2Je_ojuzU62iMIGfUbrNDKZRcN0r2_OIMhIPLNPXHNXl0G04McZQAI5AbASzrwWt8uuJ1eUJxaRJOqjM3Co-yM1JQa0vEEiVAJFunVhzU0mQ03fFnchp41GBiGFE9_I-CU5HXWolv9H5lU8TI_x6OLu1BlInq9ArkS44vjP4AsKYVuyCwxpyOVEUUWt5N8FS01Qvl1cIE3OWMsTOflU6oPLv_cVBWRr4xGhGiPztUpseNm0p4-bCaPMcIps7thea-dj4F8AfzQbO2Tg8BSRPH65Ib0FO_9g7eKFhbUJU-1jdUCYq7UGje-LOkARY4lgY3ZXnMB4Fr2nY_ghYmkuAh4CUAgqYdxrjklG-GjqvZDnCznaYRj82wTCQZU0af_DD83bQEfE5U9zgR-RRr83uZKI0LAdEpx9_Q29Fmz8Qp1IoAAUB1HWgQTToN9euCCOPFKPiVb9Y2hx5xfJz6wI6I6Ic0nKaU3Hio6R6U_LzFz5eoX4k_nnVkAUoWg-THVO6uVKk79zYAUuGjIIwG6h80R936D5K_xYHK1LR2eC9xqo4p0sC3C0zqeftvgmjGlx0IAN7iHObjtl9BbGjCMtd2a5Pv4qj8Hx2IyjVAoLdShRwCXHdZP-05gz2SHCoSD3okQXsnEcwPCNHhXWql8Iaq-Evt3DmKJJruUtFOC0ZfN1Y4g_FibjD5z4zrWOLFSnV2gLOhM1SrWgtO-3fdUNGrYH4zv7HgqkI4RjUczEFgyz3uOm921kplIYe54aOOoFtA-eN7lTiWV01ZWfcIDfFNaUQ1tUwwDE1L_ItLM9uqmaoc3TnnBfw3lAdnquigYlm6rzw9H-RSJfN9mVRkauNg36wGLSMSugmtlICdLy6hMscTN8RgPgwQlZU9_hWlsvR0wdPXuGwD_BLrTJggj9iTL83AY41rAdpGD5maL5qJq4ZbGY6vOrdpdU8P7Jy6YeVCbC1bmQA1JcPUKCfEC6y7g8I6mPp63ThPdWEr9hMCA7SvE_ZzDFca8w2r5dBYgAW9TjNSGDJgAsfO_CjTTRb6GUYdMY8RvaQlYdzcYHhpj4-c7u8xxLVFy6GmHd_8kpP7nuBv73GdpQ9UzPIouJh6W3fPxgt_67oXARMSAhs_Gd80RgMyR_qoSrOi1H5Tcw13UCwpMi_7CRQyqG5eTz1DndiIBS725E1esB03fueTmQVnOnqChU8EVjMoAPj-DQXNA5FT9DW58x5yiBHucrXdgEhLtYAGuGOhWrurMcjlbdtk915cSZqK8qNSLrmGpHcMDgnm-W0fw2AY5E1hVJ8KQH2LI_FdAX4juoR1v7s-XbZLDiHF_VXt4_m7X0LuokZEYds0unoCCmimhAdpEAB8d7fKsd6LMir66_7b4_0va11c6ILk_2_WJhW0ELhyJS_H_jmF4dAEv8G32_7Xp3WEpUqM7dxDGdwtgZPiZoNuBByWe51Xy2KW5P6tPCT0KIn6TTsON_A1TVLIN6qkVShPKdH1otcjSaS1FHJLDoVeLol7lZaokkF-b9pBweSNFW8XIU0HuZu1Mqj4YnOQ2eQtfUwgdFd03hpHhACwtqX-MYz1wPGGBWYIubcSDifzdp10VRU8N9O3HXDOXsevMSiyvGdPaVsSt8-vuMfeeYwCA_MRjAiYOcDWLp-KWMLeIaVWP32PtX6Y4hCGzQPaC48d4ImqlFt9GqwBo9Pb5UIyQo6pFbabLuhyHR4or_UANJZC6bHL8yGxMvcUlDveU6NxDIfUkhjVqP4S67lPTBd9MmeWshNgGQJ6OeYk49h1IsMy6c_1-vE68ehEeIQyLYYkfflKJIqbqkgEufp6w9ByuTYyVaYIsRc3R8bkOxlCspLekRVyMWf23BM7AnoSzMNAbTzPkuJY8Lcvx02JD9w_g7Fwwuw4Rju0wLvK-B_rdCjntyvAV40glyaaD0v3iEw9YzpkE1jNGiHYb_KpbgxwltmDg3y8-VVFZiXWmSPz2vh-zJmSpryIIjeIkz54koZgKxNS9mJtqxZW_kiCM0txBimDV2wq34HehzXMugA0OiOHnX5Zyp3IqjOA-dWZyec9PBZjmpr2yW1GdtzQot6d018gSKFjoqUyq_7A_ruIdHaOyiNEVz92PdLs1l6c6Cl4M6fXS_dLI6S9f5KMBrL4nQ3a-utAXgX4KoFIxPBWbC1b1sbc-Q04w9k5Xy2yvBaJYr-UrRAe5zcLYKzagb1XhF6-_1SKSaccyxaL8Rt3AbNMOvBI_eApN45bohFHGBFq7_uba4Ay4nAvcdcbWyiT3yf5vuhXNyGzV3YVtE79WhevTQGaxO6DCvSUukaIlM_PPd4nyKpIC5g0o77UppVzP-R4jzBWYHbfkFBIj_xKmgGuv1b1igaORPPxy8LtSIE5QWO1ghS2tcKZFMz4-uUc1VJ9mzGvKqgemKMfOaurs7JL_4YxCzr5hCCpr10sRXajOEy9HJSvDIizf3B42IaMV0yrNXBbxXxOjjZ0RnlmpSkrNtaqWg_bTsh3Eh3ZrPHLV6Gw39wnGMfW0F79nNEDZC9kSFD8tEjycQNuO-JZTjBs2Aw43TAkjfzzlAWPA.gzGaJRogJ_b29O9AnEeJUw', 'x-bamsdk-transaction-id': '880651ca-5b8e-4253-9668-ddca80e893f9'}
            wvdecrypt = WvDecrypt(init_data_b64=pssh, cert_data_b64=None, device=deviceconfig.device_android_generic)

            widevine_license = requests.post(url=cls.lic_url, data=wvdecrypt.get_challenge(), headers=postdata['headers'], params=postdata['params'])
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
