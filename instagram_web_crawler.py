# -*- coding: utf-8 -*-

from src.browser import Browser
from src.exceptions import RetryException
from src.secret import USERNAME, PASSWORD

from datetime import datetime
from functools import wraps, partial
from hashlib import md5
import json
import os
from pyquery import PyQuery as pq
import re
import requests
import sys
from time import sleep
from tqdm import tqdm
import traceback


URL = 'https://www.instagram.com'
URL_SHORTCODE = 'https://www.instagram.com/p/{}/'
URL_SAVED = 'https://www.instagram.com/{}/saved/'
URL_QUERY_POSTS = 'https://www.instagram.com/graphql/query/?query_hash={}&variables=%7B%22id%22%3A%22{}%22%2C%22first%22%3A12%2C%22after%22%3A%22{}%22%7D'
URL_QUERY_SAVED_POSTS = 'https://www.instagram.com/{}/?__a=1'
URL_QUERY_SAVED_VIDEOS = 'https://www.instagram.com/graphql/query/?query_hash={}&variables=%7B%22shortcode%22%3A%22{}%22%2C%22child_comment_count%22%3A{}%2C%22fetch_comment_count%22%3A{}%2C%22parent_comment_count%22%3A{}%2C%22has_threaded_comments%22%3A{}%7D'

HASH_NORMAL_POSTS = 'f045d723b6f7f8cc299d62b57abd500a'
HASH_SAVED_POSTS = '8c86fed24fa03a8a2eea2a70a80c7b6b'
HASH_SAVED_VIDEOS = '870ea3e846839a3b6a8cd9cd7e42290c'

COOKIE = 'mid={}; fbm_124024574287414=base_domain=.instagram.com; shbid={}; shbts={}; ds_user_id={}; csrftoken={}; sessionid={}; rur={}; urlgen={}'
SHBID = '3317'
SHBTS = '1571731121.0776558'

START_DATE = '1900-01-01'
END_DATE = datetime.now().strftime("%Y-%m-%d")

SAVE_PATH = os.path.join('.', 'results')
LOG_PATH = 'output.log'

"""
HAS_SCREEN:
    True: Open browser window.
    False: Close browser window.
"""
HAS_SCREEN = False
browser = Browser(HAS_SCREEN)
"""
NEXT_PAGE_WAIT_TIME:
    Recommended range: 0.3 ~ 1, according to your Internet speed.
"""
NEXT_PAGE_WAIT_TIME = 0.5

download_saved = False
download_from_file = True
logged_in_user = ''
username = ''

PATTERN_DATE = r'\d\d\d\d-\d\d-\d\d'

# TODO: Download media which are in the specified period.

def output_log(msg, traceback_option=True):
    with open(LOG_PATH, 'a', encoding='utf8') as output_log:
        output_log.write(msg)
    if traceback_option:
        traceback.print_exc(file=open(LOG_PATH, 'a', encoding='utf8'))

def retry(attempt=10, wait=0.3):
    def wrap(func):
        @wraps(func)
        def wrapped_f(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except RetryException:
                if attempt > 1:
                    sleep(wait)
                    return retry(attempt - 1, wait)(func)(*args, **kwargs)
                else:
                    msg = '{} - Error: Failed to login (username: {}, password: {}).\n'.format(
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), USERNAME, PASSWORD)
                    exc = RetryException(msg)

                    output_log('\n' + msg)

                    exc.__cause__ = None
                    raise exc

        return wrapped_f

    return wrap

def set_headers():
    cookies_list = browser.driver.get_cookies()
    cookies_dict = {}
    for cookie in cookies_list:
        cookies_dict[cookie['name']] = cookie['value']

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36'
    }

    headers['cookie'] = COOKIE.format(cookies_dict["mid"], SHBID, 
        SHBTS, cookies_dict["ds_user_id"], cookies_dict["csrftoken"], 
        cookies_dict["sessionid"], cookies_dict["rur"], cookies_dict["urlgen"])

    return headers

def login():
    url = "%s/accounts/login/" % (URL)
    
    browser.get(url)
    u_input = browser.find_one('input[name="username"]')
    u_input.send_keys(USERNAME)
    p_input = browser.find_one('input[name="password"]')
    p_input.send_keys(PASSWORD)

    login_btn = browser.find_one(".L3NKy")
    login_btn.click()

    @retry()
    def check_login():
        if browser.find_one('input[name="username"]'):
            raise RetryException()

    check_login()

    global logged_in_user
    logged_in_user_url = browser.find(
        "div[class='XrOey'] a")[2].get_attribute("href")
    logged_in_user = logged_in_user_url[
        logged_in_user_url[: -1].rfind('/') + 1: -1]
    print('\n* Logged in as user (username: {}).\n'.format(logged_in_user))

    headers = set_headers()

    return headers

def get_html(url, headers):
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == requests.codes['ok']:
            return response.text
        else:
            msg = '{} - Error: Failed to get page source (status_code: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code)
            output_log('\n' + msg)
            raise Exception(msg)
    except Exception:
        msg = '{} - Error: Failed to get page source (status_code: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code)
        output_log('\n' + msg)
        raise Exception(msg)

@retry()
def get_json(url, headers):
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == requests.codes['ok']:
            return response.json()
        else:
            msg = '{} - Warning: Failed to get json file (status_code: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code)
            output_log('\n' + msg, False)
            print('\n{} - Warning: Retry to get json file.\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            return get_json(url, headers)
    except Exception as e:
        msg = '{} - Warning: Failed to get json file (status_code: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code)
        output_log('\n' + msg, False)
        print('\n{} - Warning: Retry to get json file.\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return get_json(url, headers)
 
def get_content(url, headers):
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == requests.codes['ok']:
            return response.content
        else:
            msg = '{} - Error: Failed to get image content (status_code: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code)
            output_log('\n' + msg, False)
    except Exception as e:
        msg = '{} - Error: Failed to get image content (status_code: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code)
        output_log('\n' + msg, False)

def get_video_url(shortcode, headers):
    child_comment_count = '3'
    fetch_comment_count = '40'
    parent_comment_count = '24'
    has_threaded_comments = 'true'

    url = URL_QUERY_SAVED_VIDEOS.format(
        HASH_SAVED_VIDEOS, shortcode, child_comment_count, fetch_comment_count, 
        parent_comment_count, has_threaded_comments)

    js_data = get_json(url, headers)
    video_url = js_data['data']['shortcode_media']['video_url']

    return video_url

def get_sidecar_urls(shortcode):
    url = URL_SHORTCODE.format(shortcode)

    browser.get(url)

    urls = set()
    is_start = True
    while True:
        ele_imgs = browser.find("._97aPb img", waittime=10)

        if isinstance(ele_imgs, list):
            for ele_img in ele_imgs:
                urls.add(ele_img.get_attribute("src"))
        else:
            break

        play_btn = browser.find_one('.B2xwy._3G0Ji.PTIMp.videoSpritePlayButton')
        if play_btn:
            urls.add(browser.find_one('.tWeCl').get_attribute("src"))
            if is_start:
                urls.remove(ele_imgs[0].get_attribute("src"))
                is_start = False
            else:
                # Exclude the preview image of a video.
                urls.remove(ele_imgs[1].get_attribute("src"))

        next_photo_btn = browser.find_one("._6CZji .coreSpriteRightChevron")

        if next_photo_btn:
            next_photo_btn.click()
            sleep(NEXT_PAGE_WAIT_TIME)
        else:
            break

    return list(urls)

def get_saved_urls(headers):
    url = URL_QUERY_SAVED_POSTS.format(logged_in_user)

    params = {
        '__a': '1'
    }

    response = requests.get(url=url,params=params,headers=headers)
    data = response.text
    js_data = json.loads(data)

    urls = list()

    user_id = js_data["logging_page_id"][12: ]

    edges = js_data["graphql"]["user"]["edge_saved_media"]["edges"]
    post_count = js_data["graphql"]["user"]["edge_saved_media"]["count"]
    page_info = js_data["graphql"]["user"]["edge_saved_media"]["page_info"]
    cursor = page_info['end_cursor']
    has_next_page = page_info['has_next_page']

    pbar = tqdm(total=post_count)
    pbar.set_description("Progress")

    for edge in edges:
        if edge['node']['__typename'] == 'GraphSidecar':
            shortcode = edge['node']['shortcode']
            for url in get_sidecar_urls(shortcode):
                urls.append(url)
        else:
            if edge['node']['is_video']:
                shortcode = edge['node']['shortcode']
                video_url = get_video_url(shortcode, headers)
                urls.append(video_url)
            else:
                display_url = edge['node']['display_url']
                urls.append(display_url)
        pbar.update(1)

    while has_next_page:
        url = URL_QUERY_POSTS.format(HASH_SAVED_POSTS, user_id, cursor)

        js_data = get_json(url, headers)

        edges = js_data['data']['user']['edge_saved_media']['edges']
        page_info = js_data['data']['user']['edge_saved_media']['page_info']
        cursor = page_info['end_cursor']
        has_next_page = page_info['has_next_page']
        
        for edge in edges:
            if edge['node']['__typename'] == 'GraphSidecar':
                shortcode = edge['node']['shortcode']
                for url in get_sidecar_urls(shortcode):
                    urls.append(url)
            else:
                if edge['node']['is_video']:
                    shortcode = edge['node']['shortcode']
                    video_url = get_video_url(shortcode, headers)
                    urls.append(video_url)
                else:
                    display_url = edge['node']['display_url']
                    urls.append(display_url)
            pbar.update(1)

    msg = '\n{} - Info: Finish exploring saved posts. {} saved posts are found (logged_in_username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), post_count, logged_in_user)
    print(msg)

    return urls

def get_urls(html, headers):
    user_id = re.findall('"profilePage_([0-9]+)"', html, re.S)[0]

    doc = pq(html)
    items = doc('script[type="text/javascript"]').items()

    urls = list()
    for item in items:
        if item.text().strip().startswith('window._sharedData'):
            js_data = json.loads(item.text()[21: -1], encoding='utf-8')

            edges = js_data["entry_data"]["ProfilePage"][0]["graphql"]["user"]["edge_owner_to_timeline_media"]["edges"]
            post_count = js_data["entry_data"]["ProfilePage"][0]["graphql"]["user"]["edge_owner_to_timeline_media"]["count"]
            page_info = js_data["entry_data"]["ProfilePage"][0]["graphql"]["user"]["edge_owner_to_timeline_media"]['page_info']
            cursor = page_info['end_cursor']
            has_next_page = page_info['has_next_page']

            pbar = tqdm(total=post_count)
            pbar.set_description("Progress")

            for edge in edges:
                if edge['node']['__typename'] == 'GraphSidecar':
                    shortcode = edge['node']['shortcode']
                    for url in get_sidecar_urls(shortcode):
                        urls.append(url)
                else:
                    if edge['node']['is_video']:
                        shortcode = edge['node']['shortcode']
                        video_url = get_video_url(shortcode, headers)
                        urls.append(video_url)
                    else:
                        display_url = edge['node']['display_url']
                        urls.append(display_url)
                pbar.update(1)

    while has_next_page:
        url = URL_QUERY_POSTS.format(HASH_NORMAL_POSTS, user_id, cursor)

        js_data = get_json(url, headers)

        edges = js_data['data']['user']['edge_owner_to_timeline_media']['edges']
        page_info = js_data['data']['user']['edge_owner_to_timeline_media']['page_info']
        cursor = page_info['end_cursor']
        has_next_page = page_info['has_next_page']
        
        for edge in edges:
            if edge['node']['__typename'] == 'GraphSidecar':
                if edge['node']['__typename'] == 'GraphSidecar':
                    shortcode = edge['node']['shortcode']
                    for url in get_sidecar_urls(shortcode):
                        urls.append(url)
            else:
                if edge['node']['is_video']:
                    shortcode = edge['node']['shortcode']
                    video_url = get_video_url(shortcode, headers)
                    urls.append(video_url)
                else:
                    display_url = edge['node']['display_url']
                    urls.append(display_url)
            pbar.update(1)

    msg = '\n{} - Info: Finish exploring posts. {} posts are found (username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), post_count, username)
    print(msg)

    return urls

def download_media(urls, headers, save_path):
    abs_save_path = os.path.abspath(save_path)
    msg = '{} - Info: Results are saved in the folder "{}".'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), abs_save_path)
    print(msg)

    for url in tqdm(urls, desc='Progress'):
        try:
            content = get_content(url, headers)

            file_type = 'mp4' if r'mp4?_nc_ht=scontent' in url else 'jpg'
            file_path = os.path.join(save_path, '{}.{}'.format(md5(content).hexdigest(), file_type))
            
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as file:
                    file.write(content)
            else:
                msg = '{} - Warning: The filename {} exists.\n'.format(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), file_path)
                output_log('\n' + msg, False)
        except Exception:
            msg = '{} - Warning: Failed to download this file (url: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url)
            output_log('\n' + msg, False)

def get_saved_posts(headers):
    msg = '{} - Info: Start exploring saved posts (logged_in_username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), logged_in_user)
    print(msg)

    urls = get_saved_urls(headers)

    save_path = os.path.join(SAVE_PATH, logged_in_user + '_saved')
    if not os.path.exists(save_path): 
        os.makedirs(save_path)

    download_media(urls, headers, save_path)

def get_posts(headers):
    msg = '{} - Info: Start exploring posts (username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username)
    print(msg)

    url = URL + '/{}/'.format(username)

    html = get_html(url, headers)
    urls = get_urls(html, headers)

    save_path = os.path.join(SAVE_PATH, username)
    if not os.path.exists(save_path): 
        os.makedirs(save_path)

    download_media(urls, headers, save_path)

def web_crawler():
    global START_DATE
    global END_DATE
    global username
    
    if USERNAME == '' or PASSWORD == '':
        msg = '{} - Error: Please enter your username and password in secret.py.\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        output_log('\n' + msg, False)
        raise Exception(msg)

    headers = login()

    if download_saved:
        get_saved_posts(headers)

    if download_from_file:
        with open(sys.argv[1], 'r', encoding='utf8') as input_file:
            username_list = [line.split() for line in input_file if len(line.split()) != 0]

        for x in username_list:
            if len(x) != 1:
                if re.match(PATTERN_DATE, x[1]):
                    START_DATE = x[1]
                if len(x) == 3 and re.match(PATTERN_DATE, x[2]):
                    END_DATE = x[2]
            username = x[0]

            get_posts(headers)

if __name__ == '__main__':
    assert len(sys.argv) == 2 or len(sys.argv) == 3, 'Error: The number of arguments is incorrect.'
    if len(sys.argv) == 2 and sys.argv[1] == "--saved":
            download_saved = True
            download_from_file = False
    if len(sys.argv) == 3:
        if sys.argv[2] == "--saved":
            download_saved = True
        else:
            print('Error: Unknown argument at position 3.\n')

    if not os.path.exists(SAVE_PATH): 
        os.makedirs(SAVE_PATH)

    web_crawler()
