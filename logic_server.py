# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
# third-party
import requests
# third-party
from flask import request, render_template, jsonify, redirect
from selenium import webdriver

# sjva 공용
from framework import db, scheduler, path_data, socketio, SystemModelSetting, app, celery
from framework.util import Util
from framework.common.util import headers, get_json_with_auth_session
from framework.common.plugin import LogicModuleBase, default_route_socketio
from tool_expand import ToolExpandFileProcess

# 패키지
from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

#from lib_metadata.server_util import MetadataServerUtil
#########################################################

class LogicServer(LogicModuleBase):
    db_default = {    
        'server_db_version' : '1',
        'server_chromedriver_auto_start' : 'False',
        'server_port' : '19515',
        'server_remote_allow' : 'True',
        'server_test_url' : '',
        'server_test_netflix_video' : '0',
    }

    chromedriver_process = None
    driver = None
    server_dir = os.path.join(os.path.dirname(__file__), 'server')
    chromedriver_binary = os.path.join(server_dir, 'chrome', 'chromedriver.exe')
    proxy_server = None
    proxy = None
    current_data = None

    def __init__(self, P):
        super(LogicServer, self).__init__(P, 'setting')
        self.name = 'server'

    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        try:
            arg['server_chromedriver_status'] = self.chorme_driver_status()
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return render_template('sample.html', title='%s - %s' % (P.package_name, sub))


    def process_ajax(self, sub, req):
        try:
            ret = {'ret':'success'}
            if sub == 'command':
                cmd = req.form['cmd']
                data = req.form['data']
                logger.debug('cmd:[%s] data:[%s]', cmd, data)
                if cmd == 'run':
                    if self.chromedriver_process is not None:
                        ret['ret'] = 'warning'
                        ret['msg'] = u'이미 실행중입니다.'
                    else:
                        self.chrome_driver_start()
                        time.sleep(1)
                        ret['msg'] = u'실행했습니다.'
                        ret['data'] = self.chorme_driver_status()
                elif cmd == 'stop':
                    if self.chromedriver_process is None:
                        ret['ret'] = 'warning'
                        ret['msg'] = '실행중이 아닙니다.'
                    else:
                        self.chrome_driver_stop()
                        ret['msg'] = '중지했습니다.'
                        ret['data'] = self.chorme_driver_status()
                elif cmd == 'test':
                    if self.chromedriver_process is None:
                        ret['ret'] = 'warning'
                        ret['msg'] = u'크롬드라이버를 먼저 실행하세요.'
                    elif self.driver is not None:
                        ret['ret'] = 'warning'
                        ret['msg'] = u'이미 크롬이 실행중입니다.'
                    else:
                        if data == '':
                            self.chrome_driver_test()
                        elif data == 'headless':
                            self.chrome_driver_test(headless=True)
                        ret['msg'] = u'크롬을 실행했습니다.'
                elif cmd == 'chrome_stop':
                    if self.driver is not None:
                        self.driver_stop()
                        ret['msg'] = u'중지했습니다.'
                    else:
                        ret['ret'] = 'warning'
                        ret['msg'] = u'실행중이 아닙니다..'
                elif cmd == 'go':
                    if self.driver is not None:
                        ModelSetting.set('server_test_url', data)
                        self.driver.get(data)
                    else:
                        ret['ret'] = 'warning'
                        ret['msg'] = u'실행된 브라우저가 없습니다.'
                
                return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'data':str(e)})


    def plugin_load(self):
        if ModelSetting.get_bool('server_chromedriver_auto_start'):
            self.chrome_driver_start()


    def plugin_unload(self):
        self.driver_stop()
        self.chrome_driver_stop()
    
    def process_normal(self, sub, req):
        if sub == 'key':
            data = req.get_json()
            logger.debug(json.dumps(data, indent=4))
            if self.current_data is not None:
                if data['url'] == self.current_data['url']:
                    self.current_data['key'].append(data)
                    stop_timestamp = time.time()
                    self.video_stop_thread_start(stop_timestamp)
                    self.stop_timestamp = stop_timestamp
        elif sub == 'get_netflix_video_profile_mode':
            logger.debug('get_netflix_video_profile_mode')
            return jsonify(ModelSetting.get('server_test_netflix_video'))
        return jsonify('success')


    def process_api(self, sub, req):
        ret = {'ret':'success'}
        if sub == 'start':
            url = req.form['url']
            if self.current_data is not None:
                ret['ret'] = 'danger'
                ret['msg'] = u'서버: 이전 요청을 처리중입니다. 잠시 후 다시 요청하세요.'
            else:
                if self.chromedriver_process is None:
                    ret['ret'] = 'danger'
                    ret['msg'] = u'서버: chromedriver가 실행중이 아닙니다.'
                else:
                    self.current_data = {'url':url, 'key' : [], 'client_ddns' : req.form['client_ddns']}
                    self.chrome_driver_go(url)
                    ret['msg'] = u'서버: Go Success..'
            
        return jsonify(ret)


    #########################################################
    
    stop_timestamp = None
    def video_stop_thread_start(self, stop_timestamp):
        def func():
            time.sleep(3)
            if stop_timestamp == self.stop_timestamp:
                self.video_stop()
            else:
                logger.debug('ignore : %s', stop_timestamp)
        tmp = threading.Thread(target=func, args=())
        tmp.start()



    def driver_stop(self):
        if self.driver is not None:
            try: self.driver.close()
            except: pass
            time.sleep(1)
            try: self.driver.quit()
            except: pass
            self.driver = None
    

    def video_stop(self):
        self.current_data['har'] = self.proxy.har
        """
        if self.current_data['url'].find('primevideo') != -1:
            request_list = self.current_data['har']['log']['entries']
            find_ttml = False
            for item in request_list:
                logger.debug(item['request']['url'])
                if item['request']['url'].find('.ttml2') != -1:
                    find_ttml = True
                    break
            if find_ttml == False:
                self.stop_timestamp = time.time()
                self.video_stop_thread_start(self.stop_timestamp)
                logger.debug("재대기!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                return
        """
        self.current_data['cookie'] = self.driver.get_cookies()
        logger.debug('Driver Stop...')
        self.driver_stop()
        logger.debug(json.dumps(self.current_data['key'], indent=4))
        #self.current_data = None
        client_url = '{client_ddns}/widevine_downloader/normal/download/video_result'.format(client_ddns=self.current_data['client_ddns'])
        logger.debug(u'결과 전송 : %s', client_url)
        res = requests.post(client_url, json=self.current_data)
        logger.debug(u'결과 전송 완료')
        self.current_data = None

    def chorme_driver_status(self):
        return u'실행중' if (self.chromedriver_process is not None) else u'------'
       
    def chrome_driver_start(self):
        try:
            def func():
                from browsermobproxy import Server
                self.proxy_server = Server(path=os.path.join(self.server_dir, 'browsermob-proxy-2.1.4', 'bin', 'browsermob-proxy.bat'))
                self.proxy_server.start()
                logger.debug('proxy server start!!')
                time.sleep(1)
                self.proxy = self.proxy_server.create_proxy(params={'trustAllServers':'true'})
                time.sleep(1)
                logger.debug('proxy : %s', self.proxy.proxy)

                command = [self.chromedriver_binary, '--port=%s' % ModelSetting.get('server_port')]
                if ModelSetting.get_bool('server_remote_allow'):
                    command += '--allower-ips=""'
                self.chromedriver_process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
                if self.chromedriver_process is not None:
                    self.chromedriver_process.wait()
                self.chromedriver_process = None

            
            thread = threading.Thread(target=func, args=())
            thread.setDaemon(True)
            thread.start()
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
    

    def chrome_driver_stop(self):
        try:
            self.driver_stop()
            if self.proxy_server is not None:
                try: self.proxy_server.stop()
                except: pass
                self.proxy_server = None
                
            if self.chromedriver_process is not None and self.chromedriver_process.poll() is None:
                psutil_process = psutil.Process(self.chromedriver_process.pid)
                for proc in psutil_process.children(recursive=True):
                    proc.kill()
                self.chromedriver_process.kill()
                self.chromedriver_process = None
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())    


    def chrome_driver_test(self, headless=False):
        try:
            chromedriver = os.path.join(path_data, 'chrome', 'chromedriver.exe')
            chrome_data_path = os.path.join(self.server_dir, 'chrome_data')
            if os.path.exists(chrome_data_path) == False:
                os.makedirs(chrome_data_path)

            options = webdriver.ChromeOptions()
            options.add_argument("user-data-dir=%s" % chrome_data_path)
            options.add_argument("--proxy-server={0}".format(self.proxy.proxy))
            options.add_argument('ignore-certificate-errors')

            if headless:
                options.add_argument('headless')
                options.add_argument('window-size=1920x1080')
            capabilities = options.to_capabilities()
            self.driver = webdriver.Remote("http://localhost:%s" % ModelSetting.get('server_port'), capabilities)

        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())    

    

    def chrome_driver_go(self, url):
        try:
            chromedriver = os.path.join(path_data, 'chrome', 'chromedriver.exe')
            chrome_data_path = os.path.join(self.server_dir, 'chrome_data')
            if os.path.exists(chrome_data_path) == 'False':
                os.makedirs(chrome_data_path)

            options = webdriver.ChromeOptions()
            options.add_argument("user-data-dir=%s" % chrome_data_path)
            options.add_argument("--proxy-server={0}".format(self.proxy.proxy))
            options.add_argument('ignore-certificate-errors')

            capabilities = options.to_capabilities()
            self.driver = webdriver.Remote("http://localhost:%s" % ModelSetting.get('server_port'), capabilities)
            self.proxy.new_har(url, options={'captureHeaders': True, 'captureCookies':True, 'captureContent':True})
            self.driver.get(url)
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())  