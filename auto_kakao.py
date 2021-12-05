
import requests, re, json
from datetime import date, datetime, timedelta
from lxml import html

from lxml import etree as ET


def d(data):
    if type(data) in [type({}), type([])]:
        import json
        return '\n' + json.dumps(data, indent=4, ensure_ascii=False)
    else:
        return str(data)

try:
    import logging
    import logging.handlers
    logger = logging.getLogger('test')
    logger.setLevel(logging.DEBUG) 
    formatter = logging.Formatter(u'[%(asctime)s|%(levelname)s|%(filename)s:%(lineno)s]:%(message)s')
    streamHandler = logging.StreamHandler() 
    streamHandler.setFormatter(formatter)
    logger.addHandler(streamHandler)
    
except:
    pass

def write_file(filename, data):
    try:
        import codecs
        ofp = codecs.open(filename, 'w', encoding='utf8')
        ofp.write(data)
        ofp.close()
    except Exception as exception: 
        logger.error('Exception:%s', exception)
        logger.error(traceback.format_exc()) 



def main():
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
    
    logger.warning(d(item_list))

    for item in item_list:
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
                    episode_entity['no'] = int(playlist_item.xpath('a/span[1]')[0].text)
                    episode_entity['title'] = playlist_item.xpath('a/span[3]/strong')[0].text
                    try:
                        episode_entity['pay'] = playlist_item.xpath('a/span[3]/span/span')[0].text
                    except:
                        episode_entity['pay'] = '무료'
                    item['episodes'].append(episode_entity)
                item['episodes'] = list(reversed(item['episodes']))
        logger.debug(d(item))
        return






main()