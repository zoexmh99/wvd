import os, sys, traceback
from framework import app, path_data, path_app_root, celery, db, SystemModelSetting, socketio
from plugin import get_model_setting, Logic, default_route, PluginUtil, LogicModuleBase

class P(object):
    package_name = __name__.split('.')[0]
    from framework.logger import get_logger
    logger = get_logger(package_name)
    from flask import Blueprint
    blueprint = Blueprint(package_name, package_name, url_prefix='/%s' %  package_name, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
    menu = {
        'main' : [package_name, u'widevine 다운로드'],
        'sub' : [
            ['server', u'서버'], ['client', u'클라이언트'], ['download', '다운로드'], ['manual', '매뉴얼'], ['log', u'로그'] 
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
                ['list', u'목록'], ['setting', u'설정'], 
            ],
            'manual' : [
                ['README.md', 'README'], ['etc/site.md', '사이트별 특징'], 
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
        'policy_level' : 5,
    }

    ModelSetting = get_model_setting(package_name, logger)
    logic = None
    module_list = None
    home_module = 'client'

from tool_base import d
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting
    



def initialize():
    try:
        app.config['SQLALCHEMY_BINDS'][P.package_name] = 'sqlite:///%s' % (os.path.join(path_data, 'db', '{package_name}.db'.format(package_name=P.package_name)))
        PluginUtil.make_info_json(P.plugin_info, __file__)

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

