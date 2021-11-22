# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil, codecs
from datetime import datetime
# third-party
import requests
# third-party
from flask import request, render_template, jsonify, redirect
from selenium import webdriver

# sjva 공용
from framework import db, scheduler, path_data, socketio, SystemModelSetting, app, celery, path_app_root
from framework.util import Util
from framework.common.util import headers, get_json_with_auth_session
from framework.common.plugin import LogicModuleBase, default_route_socketio
from tool_expand import ToolExpandFileProcess

# 패키지
from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

import platform

bin_dir = os.path.join(os.path.dirname(__file__), 'bin', platform.system())
ARIA2C = os.path.join(bin_dir, 'aria2c' + ('.exe' if platform.system() == 'Windows' else ''))
FFMPEG = os.path.join(bin_dir, 'ffmpeg' + ('.exe' if platform.system() == 'Windows' else ''))
MP4DUMP = os.path.join(bin_dir, 'mp4dump' + ('.exe' if platform.system() == 'Windows' else ''))
MP4INFO = os.path.join(bin_dir, 'mp4info' + ('.exe' if platform.system() == 'Windows' else ''))
MP4DECRYPT = os.path.join(bin_dir, 'mp4decrypt' + ('.exe' if platform.system() == 'Windows' else ''))
MKVMERGE = os.path.join(bin_dir, 'mkvmerge' + ('.exe' if platform.system() == 'Windows' else ''))

if platform.system() != 'Windows':
    ARIA2C = 'aria2c'
    FFMPEG = 'ffmpeg'
    MKVMERGE = 'mkvmerge'
#apt-get install mkvtoolnix

    
import os, sys, traceback, subprocess, json, platform
from framework import app, logger


class Utility(object):
    download_dir = os.path.join(path_data, 'widevine_downloader', 'client')
    tmp_dir = os.path.join(download_dir, 'tmp')
    proxy_dir = os.path.join(download_dir, 'proxy')
    output_dir = os.path.join(download_dir, 'output')

    @classmethod
    def makedirs(cls):
        if os.path.exists(cls.tmp_dir) == False:
            os.makedirs(cls.tmp_dir)
        if os.path.exists(cls.proxy_dir) == False:
            os.makedirs(cls.proxy_dir)
        if os.path.exists(cls.output_dir) == False:
            os.makedirs(cls.output_dir)

    @classmethod
    def aria2c_download(cls, url, filepath, headers=None, segment=True):
        #--header="Cookie:.."
        try:
            if os.path.exists(filepath):
                return True
            command = [ARIA2C]                
            if platform.system() == 'Windows':
                if headers is not None:
                    for key, value in headers.items():
                        value = value.replace('"', '\\"')
                        command.append('--header="%s:%s"' % (key, value))
                command += [f'"{url}"', '-d', os.path.dirname(filepath), '-o', os.path.basename(filepath)]
            else:
                if headers is not None:
                    for key, value in headers.items():
                        value = value.replace('"', '\\"')
                        command.append('--header=%s:%s' % (key, value))
                command += [url, '-d', os.path.dirname(filepath), '-o', os.path.basename(filepath)]

            if segment == False:
                os.system(' '.join(command))
            else:
                ret = ToolSubprocess.execute_command_return(command, timeout=10)
                logger.debug(ret)
                if ret == 'timeout':
                    try:
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        if os.path.exists(filepath+'.aria2'):
                            os.remove(filepath+'.aria2')
                    except Exception as exception: 
                        logger.error('Exception:%s', exception)
                        logger.error(traceback.format_exc()) 
                    return cls.aria2c_download(url, filepath, headers=headers)
            return os.path.exists(filepath)
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 
        return False

    @classmethod
    def mp4dump(cls, source, target):
        try:
            if os.path.exists(target):
                return
            command = [MP4DUMP, source, '>', target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 
    
    @classmethod
    def mp4info(cls, source, target):
        try:
            if os.path.exists(target):
                return
            command = [MP4INFO, '--format', 'json', source, '>', target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 

    @classmethod
    def mp4decrypt(cls, source, target, kid, key):
        try:
            if os.path.exists(target) or kid is None or key is None:
                return
            command = [MP4DECRYPT, '--key', '%s:%s' % (kid, key), source, target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 
    

    @classmethod
    def mkvmerge(cls, option):
        try:
            command = [MKVMERGE] + option
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 



    @classmethod
    def write_file(cls, filename, data):
        try:
            import codecs
            ofp = codecs.open(filename, 'w', encoding='utf8')
            ofp.write(data)
            ofp.close()
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 

    @classmethod
    def read_file(cls, filename):
        try:
            ifp = codecs.open(filename, 'r', encoding='utf8')
            data = ifp.read()
            ifp.close()
            return data
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())



    @classmethod
    def write_json(cls, filepath, data):
        try:
            if os.path.exists(os.path.dirname(filepath)) == False:
                os.makedirs(os.path.dirname(filepath))
            with open(filepath, "w", encoding='utf8') as json_file:
                json.dump(data, json_file, indent=4, ensure_ascii=False)
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 
    
    @classmethod
    def read_json(cls, filepath):
        try:
            with open(filepath, "r", encoding='utf8') as json_file:
                data = json.load(json_file)
                return data
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 


    @classmethod
    def ttml2srt(cls, source, target):
        try:
            from ttml2srt.ttml2srt import Ttml2Srt
            logger.debug(source)
            logger.debug(target)
            ttml = Ttml2Srt(source)
            ttml.write2file(target)

        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 


    @classmethod
    def vtt2srt(cls, source, target):
        try:
            if os.path.exists(target):
                return
            command = [FFMPEG, '-y', '-i', source,  target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())

    @classmethod
    def ffmpeg_copy(cls, source, target):
        try:
            if os.path.exists(target):
                return
            command = [FFMPEG, '-y', '-i', source, '-c', 'copy', target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())

    
    @classmethod
    def window_concat(cls, init_filepath, segment, target):
        try:
            if os.path.exists(target):
                return
            command = ['copy', '/B', init_filepath, '+%s' % segment, target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())



class ToolSubprocess(object):

    @classmethod
    def execute_command_return(cls, command, format=None, force_log=True, shell=False, env=None, timeout=1000):
        logger.debug(timeout)
        try:
            if app.config['config']['running_type'] == 'windows':
                command =  ' '.join(command)

            iter_arg =  b'' if app.config['config']['is_py2'] else ''
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, shell=shell, env=env, encoding='utf8')
            try:
                process_ret = process.wait(timeout=timeout) # wait for the subprocess to exit
            except:
                import psutil
                process = psutil.Process(process.pid)
                for proc in process.children(recursive=True):
                    proc.kill()
                process.kill()
                return "timeout"
            ret = []
            with process.stdout:
                for line in iter(process.stdout.readline, iter_arg):
                    ret.append(line.strip())
                    if force_log:
                        #logger.debug(ret[-1])
                        pass
            return ret2
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc())
            logger.error('command : %s', command)