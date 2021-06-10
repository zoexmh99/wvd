# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
# third-party
from flask import request, render_template, jsonify, redirect
import requests
from sqlalchemy import or_, and_, func, not_, desc
from sqlalchemy.orm import backref
# sjva 공용
from framework import db, scheduler, path_data, socketio, SystemModelSetting, app, celery, path_app_root, Util
# 패키지
from .plugin import P
logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting
from .utility import Utility


app.config['SQLALCHEMY_BINDS']['%s_item' % package_name] = 'sqlite:///%s' % (os.path.join(path_app_root, 'data', 'db', '%s_item.db' % package_name))
#########################################################


class ModelWVDItem(db.Model):
    __tablename__ = '{package_name}_item'.format(package_name=package_name)
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = '%s_item' % package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    reserved = db.Column(db.JSON)

    status = db.Column(db.String)
    # ready, send_url_success, make_json
    url = db.Column(db.String)
    site = db.Column(db.String)
    code = db.Column(db.String)
    memo = db.Column(db.String)
    
    request_count = db.Column(db.Integer)

    response_data = db.Column(db.JSON) # 용량?
    response_filepath = db.Column(db.String)
    log = db.Column(db.String)

    title = db.Column(db.String)
    content_type = db.Column(db.String)
    season_number = db.Column(db.Integer)
    episode_number = db.Column(db.Integer)
    
    download_start_time = db.Column(db.DateTime)
    completed_time = db.Column(db.DateTime)

    def __init__(self):
        self.created_time = datetime.now()
        self.status = 'ready'
        self.request_count = 0
        self.log = ''

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%Y-%m-%d %H:%M:%S') 
        ret['download_start_time'] = self.download_start_time.strftime('%Y-%m-%d %H:%M:%S') if self.download_start_time is not None else ''
        ret['completed_time'] = self.completed_time.strftime('%Y-%m-%d %H:%M:%S') if self.completed_time is not None else ''
        return ret

    def save(self):
        db.session.add(self)
        db.session.commit()


    @classmethod
    def get_by_id(cls, id):
        return db.session.query(cls).filter_by(id=id).first()

    @classmethod
    def delete_by_id(cls, id):
        db.session.query(cls).filter_by(id=id).delete()
        db.session.commit()
        return True


    @classmethod
    def get_reday_list(cls):
        query = db.session.query(cls)
        query = query.filter(cls.status == 'ready')
        #query = query.filter(cls.status != 'completed')
        return query.all()


    @classmethod
    def web_list(cls, req):
        ret = {}
        page = int(req.form['page']) if 'page' in req.form else 1
        page_size = 30
        job_id = ''
        search = req.form['search_word'] if 'search_word' in req.form else ''
        option1 = req.form['option1'] if 'option1' in req.form else 'all'
        option2 = req.form['option2'] if 'option2' in req.form else 'all'
        order = req.form['order'] if 'order' in req.form else 'desc'
        query = cls.make_query(search=search, order=order, option1=option1, option2=option2)
        count = query.count()
        query = query.limit(page_size).offset((page-1)*page_size)
        lists = query.all()
        ret['list'] = [item.as_dict() for item in lists]
        ret['paging'] = Util.get_paging_info(count, page, page_size)
        ModelSetting.set('download_last_list_option', '%s|%s|%s|%s|%s' % (option1, option2, desc, search, page))
        return ret


    @classmethod
    def make_query(cls, search='', order='desc', option1='all', option2='all'):
        query = db.session.query(cls)
        if search is not None and search != '':
            if search.find('|') != -1:
                tmp = search.split('|')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        conditions.append(cls.url.like('%'+tt.strip()+'%') )
                query = query.filter(or_(*conditions))
            elif search.find(',') != -1:
                tmp = search.split(',')
                for tt in tmp:
                    if tt != '':
                        query = query.filter(cls.client_target_name.like('%'+tt.strip()+'%'))
            else:
                query = query.filter(cls.url.like('%'+search+'%'))
        if option1 != 'all':
            query = query.filter(cls.status == option1)
        if option2 != 'all':
            query = query.filter(cls.site == option2)

        query = query.order_by(desc(cls.id)) if order == 'desc' else query.order_by(cls.id)
        return query  

    """
    @classmethod
    def get_list_incompleted(cls):
        return db.session.query(cls).filter(cls.status != 'completed').all()
    """

    @classmethod
    def get_item_by_site_and_code(cls, site, code):
        return db.session.query(cls).filter_by(site=site).filter_by(code=code).first()


    @classmethod
    def get_items_by_status(cls, status):
        return db.session.query(cls).filter_by(status=status).order_by(cls.id).all()


