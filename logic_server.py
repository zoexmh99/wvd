# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, base64
from datetime import datetime
import requests
# third-party
from flask import request, render_template, jsonify, redirect
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.events import EventFiringWebDriver, AbstractEventListener
from selenium.webdriver import ActionChains
from selenium.common.exceptions import *
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.select import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from tool_base import ToolBaseFile
from lib_chromedriver_with_browsermob import ChromeDriverWithBrowsermob


# 패키지
from .plugin import P, d, logger, package_name, ModelSetting, LogicModuleBase, app, path_data, path_app_root
#########################################################

name = 'server'
current_dir = os.path.dirname(__file__)
#data_dir = os.path.join(current_dir, 'data')
data_dir = os.path.join(path_data, package_name, 'server')

class LogicServer(LogicModuleBase):
    db_default = {    
        'server_db_version' : '1',
        'server_test_url' : '',
    }
    
    current_data = None
    stop_timestamp = None

    def __init__(self, P):
        super(LogicServer, self).__init__(P, 'setting')
        self.name = 'server'
        self.dm = ChromeDriverWithBrowsermob({
            'logger': logger,
            'use_proxy' : True,
            'data_path' : os.path.join(data_dir, 'chrome_data'),
            'proxy_server_port' : 52100,
        })

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        try:
            return render_template(f'{package_name}_{name}_{sub}.html', arg=arg)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return render_template('sample.html', title=f"{package_name}/{name}")


    def process_ajax(self, sub, req):
        try:
            ret = {'ret':'success'}
            if sub == 'command':
                cmd = req.form['command']
                arg1 = req.form.get('arg1', None)
                if cmd == 'start':
                    if self.dm.driver is not None:
                        ret['ret'] = 'warning'
                        ret['msg'] = u'이미 크롬이 실행중입니다.'
                    else:
                        if arg1 == None:
                            self.dm.init_driver()
                        elif arg1 == 'headless':
                            self.dm.init_driver(headless=True)
                        ret['msg'] = u'크롬을 실행했습니다.'
                elif cmd == 'stop':
                    if self.dm.driver is not None:
                        self.dm.driver_stop()
                        ret['msg'] = u'중지했습니다.'
                    else:
                        ret['ret'] = 'warning'
                        ret['msg'] = u'실행중이 아닙니다..'
                elif cmd == 'go':
                    if self.dm.driver is not None:
                        ModelSetting.set('server_test_url', arg1)
                        self.dm.go_reset_har(arg1)
                    else:
                        ret['ret'] = 'warning'
                        ret['msg'] = '실행된 브라우저가 없습니다.'
                elif cmd == 'proxy':
                    if self.proxy is None:
                        ret['ret'] = 'warning'
                        ret['msg'] = '실행된 브라우저가 없습니다.'
                    else:
                        data = self.dm.get_har()
                        filepath = os.path.join(data_dir, 'proxy', str(time.time()) + '.json')
                        if os.path.exists(os.path.dirname(filepath)) == False:
                            os.makedirs(os.path.dirname(filepath))
                        logger.warning(f"저장 : {filepath}")
                        ToolBaseFile.write(d(data), filepath)
                        ret['msg'] = '저장하였습니다.'
                elif cmd == 'capture_content':
                    self.proxy.new_har('test' if self.current_data == None else self.current_data['url'], options={'captureHeaders': True, 'captureContent':True})

                return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'data':str(e)})


    def plugin_unload(self):
        self.dm.close()


    def process_api(self, sub, req):
        ret = {'ret':'success'}
        if sub == 'start':
            url = req.form['url']
            site = req.form['site']
            code = req.form['code']
            logger.warning(url)
            if self.current_data is not None:
                ret['ret'] = 'danger'
                ret['msg'] = u'서버: 이전 요청을 처리중입니다. 잠시 후 다시 요청하세요.'
            else:
                self.current_data = {'site':site, 'url':url, 'key' : [], 'client_ddns' : req.form['client_ddns'], 'code':code}
                
                ret['msg'] = u'서버: Go Success..'
                def func():
                    self.video_start(url)
                    time.sleep(10)
                    logger.debug("비디오 중단 스레드1 시작. 요청 후 10초")
                    #stop_timestamp = time.time()
                    #self.video_stop_thread_start(stop_timestamp)
                    #self.stop_timestamp = stop_timestamp
                    if self.current_data is None:
                        return
                    from .queue_download import QueueDownload
                    for mod in QueueDownload.site_list:
                        if mod.name == self.current_data['site']:
                            if mod.auto_video_stop:
                                self.video_stop()
                            break
                    
                tmp = threading.Thread(target=func, args=())
                tmp.start()
        return jsonify(ret)

    #########################################################
    
    
    def video_stop(self):
        # 요청에 의한 시작과 키를 받아서 중단 되는게 중복 될 수 있음.
        if self.dm.driver is None:
            return
        self.current_data['har'] = self.dm.get_har()
        logger.debug('[서버] Driver Stop...')

        from .queue_download import QueueDownload
        for mod in QueueDownload.site_list:
            logger.debug(mod)
            if mod.name == self.current_data['site']:
                mod.do_make_key(self)
                break
        #self.current_data = None
        #return
        try:
            for item in self.current_data['har']['log']['entries']:
                item['response']['content'] = None

            client_url = '{client_ddns}/widevine_downloader/normal/download/video_result'.format(client_ddns=self.current_data['client_ddns'])
            logger.debug(f'[서버] 결과 전송 : {client_url}')
            res = requests.post(client_url, json=self.current_data)
            logger.debug(res)
            logger.debug(res.text)
            logger.debug(f'[서버] 결과 전송 완료 : {res.json()}')
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())  
        finally:
            self.dm.driver_stop()
            self.current_data = None


    def video_start(self, url):
        try:
            self.dm.init_driver(url)
            from .queue_download import QueueDownload
            for mod in QueueDownload.site_list:
                logger.debug(mod)
                if mod.name == self.current_data['site']:
                    mod.do_driver_action(self)
                    break
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())    
