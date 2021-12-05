import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, base64, requests
from datetime import datetime, timedelta
from lxml import html
from lxml import etree as ET
from flask import render_template, jsonify
from .plugin import P, d, logger, package_name, ModelSetting, LogicModuleBase, app, path_data, path_app_root, scheduler
name = 'auto'

from .model_auto import ModelAutoItem

class LogicAuto(LogicModuleBase):
    db_default = {    
        f'{name}_db_version' : '1',
        f'{name}_interval' : '30',
        f'{name}_auto_start' : 'False',
    }

    def __init__(self, P):
        super(LogicAuto, self).__init__(P, 'setting')
        self.name = name

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        try:
            arg['scheduler'] = str(scheduler.is_include(self.get_scheduler_name()))
            arg['is_running'] = str(scheduler.is_running(self.get_scheduler_name()))
            return render_template(f'{package_name}_{name}_{sub}.html', arg=arg)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return render_template('sample.html', title=f"{package_name}/{name}")


    def process_ajax(self, sub, req):
        try:
            ret = {'ret':'success'}
            if sub == 'command':
                return jsonify(ret)
            elif sub == 'web_list':
                return jsonify(ModelAutoItem.web_list(req))
            elif sub == 'db_remove':
                return jsonify(ModelAutoItem.delete_by_id(req.form['id']))
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'data':str(e)})


    def scheduler_function(self):
        logger.warning('aaa')
        self.kakao()
        self.auto_request()

    #########################################################
    
    def auto_request(self):
        db_items = ModelAutoItem.get_request_item()
        queue_chrome_request = P.logic.get_module('download').queue_chrome_request
        for db_item in db_items:
            ret = queue_chrome_request.add_request_url(db_item.request_url, f"{db_item.show_title} - {db_item.episode_no} - {db_item.episode_title}")
            if ret['ret'] == 'success':
                db_item.status = 'request'
                db_item.save()
            else:
                logger.warning(db_item)


    


    def kakao(self):
        res = requests.get('https://tv.kakao.com/top')
        root = html.fromstring(res.text)
        logger.debug(root)

        tags = root.xpath('//div[@class="area_category"]')
        logger.debug(tags)
        now = datetime.now()
        item_list = []
        for tag in tags:
            entity = {'episodes':[]}
            entity['title'] = tag.xpath('.//span[@class="txt_subject"]')[0].text
            first_item = tag.xpath('.//div[@class="inner_favoritem"]')[0]
            link = first_item.xpath('.//a')[0].attrib['href']
            entity['channel_id'] = link.split('/')[2]
            entity['upload_time'] = first_item.xpath('.//a/span[3]/span[2]/span[2]')[0].attrib['data-raw-date']
            upload_time = datetime.strptime(entity['upload_time'], '%Y-%m-%d %H:%M:%S')
            if (now - upload_time).days > 10:
                break
            item_list.append(entity)
        
        #logger.warning(d(item_list))

        for item in item_list:
            channel_append_count = 0
            root = html.fromstring(requests.get(f"https://tv.kakao.com/channel/{item['channel_id']}/playlist").text)
            
            tags = root.xpath('//*[@id="mArticle"]/div[2]/ul/li[1]')
            for tag in tags:
                name = tag.xpath('a/span[2]/strong')[0].text
                if name.find('본편') != -1:
                    item['playlist'] = f"https://tv.kakao.com{tag.xpath('a')[0].attrib['href']}"
                    playlist_root = html.fromstring(requests.get(item['playlist']).text)
                    playlist_item_tags = playlist_root.xpath('//*[@id="playerPlaylist"]/ul[1]/li')
                    for playlist_item in playlist_item_tags:
                        episode_entity = {}
                        episode_entity['link'] = 'https://tv.kakao.com' + playlist_item.xpath('a')[0].attrib['href']
                        episode_entity['code'] = playlist_item.xpath('a')[0].attrib['href'].split('?')[0].split('/')[-1]
                        episode_entity['no'] = int(playlist_item.xpath('a/span[1]')[0].text)
                        episode_entity['title'] = playlist_item.xpath('a/span[3]/strong')[0].text
                        try:
                            episode_entity['pay'] = playlist_item.xpath('a/span[3]/span/span')[0].text
                            continue
                        except:
                            episode_entity['pay'] = '무료'
                        item['episodes'].append(episode_entity)
                    item['episodes'] = list(reversed(item['episodes']))

            for episode in item['episodes']:
                db_item = ModelAutoItem.get_by_episode_no('kakao', item['channel_id'], episode['no'])
                if db_item == None:
                    db_item = ModelAutoItem()
                    db_item.site = 'kakao'
                    db_item.show_id = item['channel_id']
                    db_item.show_title = item['title']
                    db_item.episode_no = episode['no']
                    db_item.episode_title = episode['title']
                    db_item.request_url = episode['link']
                    #db_item.episode_free = episode['pay']
                    db_item.code = episode['code']
                    db_item.save()
                    channel_append_count += 1
                else:
                    break
            #if channel_append_count == 0:
            #    break
            logger.debug(d(item))
   










   