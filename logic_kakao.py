import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, base64, requests
from datetime import datetime

from flask import render_template, jsonify
from .plugin import P, d, logger, package_name, ModelSetting, LogicModuleBase, app, path_data, path_app_root, scheduler
name = 'kakao'

class LogicKakao(LogicModuleBase):
    db_default = {    
        f'{name}_db_version' : '1',
        f'{name}_interval' : '30',
        f'{name}_auto_start' : 'False',
    }

    def __init__(self, P):
        super(LogicKakao, self).__init__(P, 'setting')
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
                cmd = req.form['command']
                arg1 = req.form.get('arg1', None)
                if cmd == 'start':
                    if self.driver is not None:
                        ret['ret'] = 'warning'
                        ret['msg'] = u'이미 크롬이 실행중입니다.'
                    else:
                        if arg1 == None:
                            self.chrome_driver_start()
                        elif arg1 == 'headless':
                            self.chrome_driver_start(headless=True)
                        ret['msg'] = u'크롬을 실행했습니다.'
                elif cmd == 'stop':
                    if self.driver is not None:
                        self.driver_stop()
                        ret['msg'] = u'중지했습니다.'
                    else:
                        ret['ret'] = 'warning'
                        ret['msg'] = u'실행중이 아닙니다..'
                elif cmd == 'go':
                    if self.driver is not None:
                        ModelSetting.set('server_test_url', arg1)
                        self.driver.get(arg1)
                    else:
                        ret['ret'] = 'warning'
                        ret['msg'] = '실행된 브라우저가 없습니다.'
                elif cmd == 'proxy':
                    if self.proxy is None:
                        ret['ret'] = 'warning'
                        ret['msg'] = '실행된 브라우저가 없습니다.'
                    else:
                        data = self.proxy.har
                        filepath = os.path.join(data_dir, 'proxy', str(time.time()) + '.json')
                        if os.path.exists(os.path.dirname(filepath)) == False:
                            os.makedirs(os.path.dirname(filepath))
                        logger.warning(f"저장 : {filepath}")
                        ToolBaseFile.write(d(data), filepath)
                        ret['msg'] = '저장하였습니다.'
                elif cmd == 'blob_url':
                    bytes = self.get_file_content_chrome(arg1)
                    filepath = os.path.join(data_dir, 'blob', str(time.time()) + '.wep')
                    if os.path.exists(os.path.dirname(filepath)) == False:
                        os.makedirs(os.path.dirname(filepath))
                    f = open(filepath, "wb")
                    f.write(bytes)
                    f.close()
                    ret['msg'] = '저장하였습니다.'
                elif cmd == 'capture_content':
                    self.proxy.new_har('test' if self.current_data == None else self.current_data['url'], options={'captureHeaders': True, 'captureContent':True})

                return jsonify(ret)
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'exception', 'data':str(e)})


    def scheduler_function(self):
        logger.warning('aaa')

    #########################################################
    
    
    def video_stop_thread_start(self, stop_timestamp):
        if self.driver is None:
            return
        if self.current_data['site'] == 'netflix':
            # 넷플은 제목을 얻어와야하기때문에 do_driver_action 에서 바로 콜한다.
            return
        def func():
            if self.current_data['site'] in ['primevideo', 'disney']:
                time.sleep(20)
            else:
                time.sleep(3)
            logger.debug(f"비디오 중단 스레드2 시작")
            if stop_timestamp == self.stop_timestamp:
                self.video_stop()
            else:
                logger.debug('ignore : %s', stop_timestamp)
        tmp = threading.Thread(target=func, args=())
        tmp.start()

    def video_stop(self):
        # 요청에 의한 시작과 키를 받아서 중단 되는게 중복 될 수 있음.
        if self.driver is None:
            return
        self.current_data['har'] = self.proxy.har
        logger.debug('[서버] Driver Stop...')
        self.driver_stop()
        client_url = '{client_ddns}/widevine_downloader/normal/download/video_result'.format(client_ddns=self.current_data['client_ddns'])
        logger.debug(f'[서버] 결과 전송 : {client_url}')
        res = requests.post(client_url, json=self.current_data)
        logger.debug(f'[서버] 결과 전송 완료 : {res.json()}')
        self.current_data = None


    def chrome_driver_start(self, url=None, headless=False):
        try:
            chrome_data_path = os.path.join(data_dir, 'chrome')
            if os.path.exists(chrome_data_path) == False:
                os.makedirs(chrome_data_path)
            self.create_proxy()
            options = webdriver.ChromeOptions()
            options.add_argument("user-data-dir=%s" % chrome_data_path)
            options.add_argument("--proxy-server={0}".format(self.proxy.proxy))
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--ignore-certificate-errors-spki-list')

            if headless:
                options.add_argument('headless')
                options.add_argument('window-size=1920x1080')
            capabilities = options.to_capabilities()
            """
            self.driver = webdriver.Remote("http://localhost:%s" % ModelSetting.get('server_port'), capabilities)
            #self.proxy.new_har('kakao', options={'captureHeaders': True, 'captureCookies':True, 'captureContent':True})
            """
            chromedriver = os.path.join(current_dir, 'server', 'chrome', 'chromedriver.exe')
            self.driver = webdriver.Chrome(chromedriver, chrome_options=options)
            if url is not None:
                self.proxy.new_har(url, options={'captureHeaders': True})
                self.driver.get(url)
                from .queue_download import QueueDownload
                for mod in QueueDownload.site_list:
                    logger.debug(mod)
                    if mod.name == self.current_data['site']:
                        mod.do_driver_action(self)
                        break
            else:
                self.proxy.new_har('test', options={'captureHeaders': True})
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())    

    
    def driver_stop(self):
        if self.driver is not None:
            try: self.driver.close()
            except: pass
            time.sleep(3)
            try: self.driver.quit()
            except: pass
            self.driver = None
    
    def create_proxy(self):
        if self.proxy is not None:
            return
        
        self.proxy_server = Server(path=os.path.join(current_dir, 'server', 'browsermob-proxy-2.1.4', 'bin', 'browsermob-proxy.bat'), options={'port':52300})
        self.proxy_server.start()
        logger.debug('proxy server start!!')
        time.sleep(1)
        try:
            self.proxy = self.proxy_server.create_proxy(params={'trustAllServers':'true'})
        except:
            time.sleep(2)
            self.proxy = self.proxy_server.create_proxy(params={'trustAllServers':'true'})
        time.sleep(1)
        logger.debug('proxy : %s', self.proxy.proxy)
        #logger.debug('proxy : %s', self.proxy.har)
        #command = [self.chromedriver_binary, '--port=%s' % ModelSetting.get('server_port')]

    def proxy_stop(self):
        try:
            logger.error("proxy_stop")
            #self.driver_stop()
            if self.proxy_server is not None:
                try: self.proxy_server.stop()
                except Exception as e: 
                    P.logger.error('Exception:%s', e)
                    P.logger.error(traceback.format_exc())
                self.proxy_server = None
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())    

    
    def get_file_content_chrome(self, uri):
        driver = self.driver
        result = driver.execute_async_script("""
            var uri = arguments[0];
            var callback = arguments[1];
            var toBase64 = function(buffer){for(var r,n=new Uint8Array(buffer),t=n.length,a=new Uint8Array(4*Math.ceil(t/3)),i=new Uint8Array(64),o=0,c=0;64>c;++c)i[c]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".charCodeAt(c);for(c=0;t-t%3>c;c+=3,o+=4)r=n[c]<<16|n[c+1]<<8|n[c+2],a[o]=i[r>>18],a[o+1]=i[r>>12&63],a[o+2]=i[r>>6&63],a[o+3]=i[63&r];return t%3===1?(r=n[t-1],a[o]=i[r>>2],a[o+1]=i[r<<4&63],a[o+2]=61,a[o+3]=61):t%3===2&&(r=(n[t-2]<<8)+n[t-1],a[o]=i[r>>10],a[o+1]=i[r>>4&63],a[o+2]=i[r<<2&63],a[o+3]=61),new TextDecoder("ascii").decode(a)};
            var xhr = new XMLHttpRequest();
            xhr.responseType = 'arraybuffer';
            xhr.onload = function(){ callback(toBase64(xhr.response)) };
            xhr.onerror = function(){ callback(xhr.status) };
            xhr.open('GET', uri);
            xhr.send();
            """, uri)
        if type(result) == int :
            raise Exception("Request failed with status %s" % result)
        return base64.b64decode(result)

        #bytes = get_file_content_chrome(driver, "blob:https://developer.mozilla.org/7f9557f4-d8c8-4353-9752-5a49e85058f5")
