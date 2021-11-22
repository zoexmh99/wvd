# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, time, shutil, subprocess, psutil
from datetime import datetime
# third-party
import requests
# third-party


try:
    import logging
    import logging.handlers
    logger = logging.getLogger('test')
    logger.setLevel(logging.DEBUG) 
    formatter = logging.Formatter(u'[%(asctime)s|%(levelname)s|%(filename)s:%(lineno)s] : %(message)s')
    streamHandler = logging.StreamHandler() 
    streamHandler.setFormatter(formatter)
    logger.addHandler(streamHandler)
    
except:
    pass



def aria2c_download(url, filepath, headers=None):
    #--header="Cookie:.."
    try:
        if os.path.exists(filepath):
            return True
        logger.debug('1111111111111')
        logger.debug(filepath)
        
        command = [r"C:\SJVA3_DEV\widevine_downloader\bin\Windows\aria2c.exe"]
        if headers is not None:
            for key, value in headers.items():
                if value.find('"') == -1:
                    command.append('--header="%s:%s"' % (key, value))
        command += [f'"{url}"', '-o', filepath]

        logger.warning(command)
        #subprocess.check_output
        os.system(' '.join(command))
        return os.path.exists(filepath)
    except Exception as exception: 
        logger.error('Exception:%s', exception)
        logger.error(traceback.format_exc()) 
    return False

"""
content_key_decryption.js:70 WidevineDecryptor: Session: 790D6F6009B2DC341E475C397C61BE8C KID= 12c918ea94645d18a6371aa7ab89eae8 Key: 1dfc5d237e334c268bf1088667d4d623
content_key_decryption.js:70 WidevineDecryptor: Session: 790D6F6009B2DC341E475C397C61BE8C KID= 5cb73345b69d50c189c334c11fb14fbc Key: 1f4f81fefa2e4a5358693a0d70abf147
content_key_decryption.js:70 WidevineDecryptor: Session: 790D6F6009B2DC341E475C397C61BE8C KID= f300a962f23a589797350e3448ab0f95 Key: 206936ffdbb3e9a24a568fd75b6cca85
a2dd0a8ced2666bec0cad662245384dc0d54684c.85431fd36bf51ca25466.js:1 KeyStatusesChangeEvent


12 c9 18 ea 94 64 5d 18 a6 37 1a a7 ab 89 ea e8

"""

def download():
    headers = {
        'Accept' : '*/*',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        #Connection: keep-alive
        'Host': 'page-v3.kakaocdn.net',
        'Origin': 'https://page.kakao.com',
        'Referer': 'https://page.kakao.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36'
    }

    #p = r"C:\SJVA3_DEV\widevine_downloader\kakaopage"

    url = "https://page-v3.kakaocdn.net/pwm/0/JtxHhlWg4ONfDImkkv5WGwvvwOp21nXY/1631864461/xJdedZNyWRcMIvAfNa4fTH7BswA_/4/v1/page-vod/5e33c2dd752a2f1687a77396/wservices/703f3a48-5946-46eb-b88f-dccac6347c6c/0/a-init.mp4"

    filpath = r"kakaopage\test_audio_init.mp4"
    aria2c_download(url, filpath, headers=headers)

    for i in range(1, 1000):
        filpath = f"kakaopage\\test_audio_{str(i).zfill(4)}.mp4"
        url = f"https://page-v3.kakaocdn.net/pwm/0/JtxHhlWg4ONfDImkkv5WGwvvwOp21nXY/1631864461/xJdedZNyWRcMIvAfNa4fTH7BswA_/4/v1/page-vod/5e33c2dd752a2f1687a77396/wservices/703f3a48-5946-46eb-b88f-dccac6347c6c/0/a-{i}.mp4"

        aria2c_download(url, filpath, headers=headers)


def main():
    download()

main()