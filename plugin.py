# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback

# third-party
import requests
from flask import Blueprint, request, send_file, redirect

# sjva 공용
from framework import app, path_data, check_api, py_urllib, SystemModelSetting, Util
from framework.logger import get_logger
from framework.util import Util
from framework.common.plugin import get_model_setting, Logic, default_route

# 패키지

#########################################################


class P(object):
    package_name = __name__.split('.')[0]
    logger = get_logger(package_name)
    blueprint = Blueprint(package_name, package_name, url_prefix='/%s' %  package_name, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
    menu = {
        'main' : [package_name, u'widevine 다운로드'],
        'sub' : [
            ['server', u'서버'], ['client', u'클라이언트'], ['download', '다운로드'], #['netflix', u'넷플릭스'], ['prime', u'아마존 프라임 비디오'], ['watcha', u'왓챠'], ['tving', u'티빙'], ['wavve', u'웨이브'],['log', u'로그']
        ], 
        'category' : 'tool',
        'sub2' : {
            'server' : [
                ['setting', u'서버 설정']
            ],
            'client' : [
                ['setting', u'클라이언트 설정'], 
            ],
            'download' : [
                ['queue', u'큐'], ['test', u'테스트'], 
            ],
        }
    }  

    plugin_info = {
        'version' : '0.2.0.0',
        'name' : package_name,
        'category_name' : 'tool',
        'icon' : '',
        'developer' : u'soju6jan',
        'description' : u'DRM 영상 다운로드',
        'home' : 'https://github.com/soju6jan/%s' % package_name,
        'more' : '',
    }

    ModelSetting = get_model_setting(package_name, logger)
    logic = None
    module_list = None
    home_module = 'client'


def initialize():
    try:
        app.config['SQLALCHEMY_BINDS'][P.package_name] = 'sqlite:///%s' % (os.path.join(path_data, 'db', '{package_name}.db'.format(package_name=P.package_name)))
        from framework.util import Util
        Util.save_from_dict_to_json(P.plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))

        from .logic_server import LogicServer
        from .logic_client import LogicClient
        from .logic_download import LogicDownload
        P.module_list = [LogicServer(P), LogicClient(P), LogicDownload(P)]
        P.logic = Logic(P)
        default_route(P)
    except Exception as e: 
        P.logger.error('Exception:%s', e)
        P.logger.error(traceback.format_exc())


initialize()

