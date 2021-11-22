import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
from .site_base import SiteBase, d, logger, package_name, ModelSetting, Utility, P

class SitePrime(SiteBase):
    name = 'prime'
    name_on_filename = 'PV'
    url_regex = request_url_regex = re.compile(r'www\.primevideo\.com(.*?)detail\/(?P<code>.*?)[\/$].*?\?autoplay=1')

    def __init__(self, db_id, json_filepath):
        super(SitePrime, self).__init__(db_id, json_filepath)
        self.audio_url = None

    def prepare(self):
        try:
            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'POST' and item['request']['url'].find('GetPlaybackResources') != -1:
                    self.meta['source'] = self.get_response(item).json()
                    Utility.write_json(os.path.join(self.temp_dir, f'{self.code}.meta.json'), self.meta['source'])
                    break
            
            self.meta['content_type'] = 'show' if self.meta['source']['catalogMetadata']['catalog']['entityType'] == 'TV Show' else 'movie'
            
            if self.meta['source']['catalogMetadata']['catalog']['entityType'] == 'TV Show':
                self.meta['content_type'] = 'show'
                self.meta['episode_number'] = self.meta['source']['catalogMetadata']['catalog']['episodeNumber']
                #self.meta['episode_title'] = self.meta['source']['catalogMetadata']['catalog']['title']
                self.meta['season_number'] = self.meta['source']['catalogMetadata']['family']['tvAncestors'][0]['catalog']['seasonNumber']
                self.meta['title'] = self.meta['source']['catalogMetadata']['family']['tvAncestors'][1]['catalog']['title']
            else:
                self.meta['content_type'] = 'movie'
                self.meta['title'] = self.meta['source']['catalogMetadata']['catalog']['title']

            for item in self.data['har']['log']['entries']:
                if item['request']['method'] == 'GET' and item['request']['url'].find('_audio_') != -1:
                    match = re.compile(r'_audio_(?P<number>\d+)\.mp4').search(item['request']['url'])
                    if not match:
                        continue
                    self.audio_url = item['request']['url'].split('?')[0]
                    self.mpd_url = self.audio_url.replace('_audio_%s.mp4' % match.group('number'), '_corrected.mpd?encoding=segmentBase')
                    logger.debug('MPD URL : %s', self.mpd_url)
                    break
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())


    def make_download_info(self):
        try:
            super().make_download_info()
            audio_rep = None
            for period in self.mpd.periods:
                for adaptation_set in period.adaptation_sets:
                    if adaptation_set.content_type != 'audio':
                        continue
                    for representation in adaptation_set.representations:

                        if self.audio_url.find(representation.base_urls[0].base_url_value) != -1:
                            audio_rep = representation
                        elif audio_rep is not None:
                            # 더 좋은 것은 바로 대입
                            audio_rep = representation
                    if audio_rep != None: # 다른 set은 안함.
                        break
            logger.error(audio_rep.base_urls[0].base_url_value)
            if audio_rep != None:
                self.download_list['audio'] = [audio_rep]
                for item_adaptation_set in self.adaptation_set['audio']:
                    for item_adaptation_set in item_adaptation_set['representation']:
                        #logger.error(d(item_adaptation_set))
                        if item_adaptation_set['url'].find(audio_rep.base_urls[0].base_url_value) != -1:
                            self.download_list['audio'] = [self.make_filepath(item_adaptation_set)]
                            break

            for tmp1 in ['subtitleUrls', 'forcedNarratives']:
                for item in self.meta['source'][tmp1]:
                    if item['languageCode'].split('-')[0] == 'ms':
                        continue
                    self.download_list['text'].append(self.make_filepath({
                        'contentType':'text', 
                        'mimeType':'text/ttml', 
                        'lang':item['languageCode'].split('-')[0], 
                        'url':item['url'], 
                        'force' : (tmp1 == 'forcedNarratives')
                    }))
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
        