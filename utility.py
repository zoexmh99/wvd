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

class Utility(object):
    download_dir = os.path.join(path_data, 'widevine_downloader')
    tmp_dir = os.path.join(download_dir, 'tmp')
    json_dir = os.path.join(download_dir, 'json')
    output_dir = os.path.join(download_dir, 'output')

    
    @classmethod
    def aria2c_download(cls, url, filepath, headers=None):
        #--header="Cookie:.."
        try:
            if os.path.exists(filepath):
                return
            #if platform.system() == 'Windows':
            filepath = filepath.replace(path_app_root, '.')

            command = [ARIA2C]
            if headers is not None:
                for key, value in headers.items():
                    command.append('--header="%s:%s"' % (key, value))
            command += ["'%s'" % url, '-o', "'%s'" % filepath]
            logger.debug(' '.join(command))
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 

    @classmethod
    def mp4dump(cls, source, target):
        try:
            if os.path.exists(target):
                return
            command = [MP4DUMP, "'%s'" % source, '>', "'%s'" % target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 
    
    @classmethod
    def mp4info(cls, source, target):
        try:
            if os.path.exists(target):
                return
            command = [MP4INFO, '--format', 'json', "'%s'" % source, '>', "'%s'" % target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 

    @classmethod
    def mp4decrypt(cls, source, target, kid, key):
        try:
            if os.path.exists(target) or kid is None or key is None:
                return
            command = [MP4DECRYPT, '--key', '%s:%s' % (kid, key), "'%s'" % source, "'%s'" % target]
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
    def vtt2srt(cls, source, target):
        try:
            command = [FFMPEG, '-i', '"%s"' % source, '"%s"' % target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 


    @classmethod
    def write_file(cls, data, filename):
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
    def write_json(cls, data, filepath):
        try:
            with open(filepath, "w") as json_file:
                json.dump(data, json_file, indent=4)
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 
    
    @classmethod
    def read_json(cls, filepath):
        try:
            with open(filepath, "r") as json_file:
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
            command = [FFMPEG, '-i', "'%s'" % source,  "'%s'" % target]
            os.system(' '.join(command))
        except Exception as exception: 
            logger.error('Exception:%s', exception)
            logger.error(traceback.format_exc()) 
    