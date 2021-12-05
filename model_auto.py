# python
import os, sys, traceback, re, json, threading, time, shutil, fnmatch, glob
from datetime import datetime, timedelta

# sjva 공용
from framework import db, app, path_data
from sqlalchemy import or_, and_, func, not_, desc
from plugin import ModelBase

# 패키지
from .plugin import P, logger, package_name, ModelSetting


class ModelAutoItem(ModelBase):
    __tablename__ = 'kakao_item'
    __bind_key__ = package_name

    model_setting = ModelSetting
    logger = logger

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    status = db.Column(db.String) # ready

    site = db.Column(db.String)
    show_id = db.Column(db.String)
    show_title = db.Column(db.String)
    episode_no = db.Column(db.Integer)
    episode_title = db.Column(db.String)
    episode_free = db.Column(db.String)
    request_url = db.Column(db.String)
    data = db.Column(db.JSON)

    completed_time = db.Column(db.DateTime)


    def __init__(self):
        self.created_time = datetime.now()
        self.status = "ready"

    
    @classmethod
    def get_by_episode_no(cls, site, show_id, episode_no):
        try:
            return db.session.query(cls).filter_by(site=site).filter_by(show_id=show_id).filter_by(episode_no=episode_no).first()
        except Exception as e:
            cls.logger.error(f'Exception:{str(e)}')
            cls.logger.error(traceback.format_exc())

    # JSON 
    @classmethod
    def make_query(cls, order='desc', search='', option1='all', option2='all'):
        query = db.session.query(cls)
        if search is not None and search != '':
            if search.find('|') != -1:
                tmp = search.split('|')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        conditions.append(cls.append_files.like('%'+tt.strip()+'%') )
                query = query.filter(or_(*conditions))
            elif search.find(',') != -1:
                tmp = search.split(',')
                for tt in tmp:
                    if tt != '':
                        query = query.filter(cls.append_files.like('%'+tt.strip()+'%'))
            else:
                query = query.filter(or_(cls.append_files.like('%'+search+'%'), cls.append_files.like('%'+search+'%')))

        #if av_type != 'all':
        #    query = query.filter(cls.av_type == av_type)

        if option1 != 'all':
            query = query.filter(cls.section_id == option1)
        
        if option2 == 'append':
            query = query.filter(cls.part_append_count > 0)

        if order == 'desc':
            query = query.order_by(desc(cls.id))
        else:
            query = query.order_by(cls.id)

        return query 


    