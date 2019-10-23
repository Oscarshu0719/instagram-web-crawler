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

"""
    Usage:
        python instagran_web_crawler.py [path] [--saved] 
    
    Args:
        path: Input path (a file including one user_id per line).
        --saved: Download saved posts.

    Notice:
        Put chromedriver.exe in folder /bin.
        Copy secret.py.dist as secret.py in the same folder.

        Input file format:
            username [start_date] [end_date]

            If end_date is specific and no specific start_date, use '-'. 
            If start_date is specific and no specific end_date, 
            no other input is needed.
            (Default: Posts of all time.)

            options:
                -f: 
                    Get following users.
                -p: 
                    Download posts (including images and videos).

                (If no -f, it's no need to input options, since -p is default with no option. 
                The order of options is meaningless.)
                (Ignore letter case.)

            e.g.
                a123456789 2019-01-01 2019-06-01 -fp
                b987654321 2018-01-01 2019-01-01 -Pf
                c111111111 - 2019-02-01 -F
                d222222222 2019-03-01 -fp
                e333333333 
"""


URL = 'https://www.instagram.com'
URL_SHORTCODE = 'https://www.instagram.com/p/{}/'
URL_SAVED = 'https://www.instagram.com/{}/saved/'
URL_QUERY_POSTS = 'https://www.instagram.com/graphql/query/?query_hash={}&variables=%7B%22id%22%3A%22{}%22%2C%22first%22%3A{}%2C%22after%22%3A%22{}%22%7D'
URL_QUERY_SAVED_POSTS = 'https://www.instagram.com/{}/?__a=1'
URL_QUERY_SAVED_VIDEOS = 'https://www.instagram.com/graphql/query/?query_hash={}&variables=%7B%22shortcode%22%3A%22{}%22%2C%22child_comment_count%22%3A{}%2C%22fetch_comment_count%22%3A{}%2C%22parent_comment_count%22%3A{}%2C%22has_threaded_comments%22%3A{}%7D'
URL_QUERY_FOLLOWING_USERS = 'https://www.instagram.com/graphql/query/?query_hash={}&variables=%7B%22id%22%3A%22{}%22%2C%22include_reel%22%3A{}%2C%22fetch_mutual%22%3A{}%2C%22first%22%3A{}{}%7D'
FOLLOWING_USERS_SUFFIX = '%2C%22after%22%3A%22{}%3D%3D%22'

HASH_NORMAL_POSTS = 'f045d723b6f7f8cc299d62b57abd500a'
HASH_SAVED_POSTS = '8c86fed24fa03a8a2eea2a70a80c7b6b'
HASH_SAVED_VIDEOS = '870ea3e846839a3b6a8cd9cd7e42290c'
HASH_FOLLOWING_USERS = 'd04b0a864b4b54837c0d870b0e77e076'

FIRST = '12'

COOKIE = 'mid={}; fbm_124024574287414=base_domain=.instagram.com; shbid={}; shbts={}; ds_user_id={}; csrftoken={}; sessionid={}; rur={}; urlgen={}'

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
WAIT_TIME:
    Recommended value: 0.3 ~ 1, according to your Internet speed.
"""
WAIT_TIME = 0.5

download_saved = False
download_from_file = True
download_posts = True
get_following = False

logged_in_username = ''
logged_in_user_id = ''

username = ''
user_id = ''

PATTERN_OPTION = r'-([pf])([pf]?$)'
PATTERN_DATE = r'\d\d\d\d-\d\d-\d\d'

MAX_GET_JSON_COUNT = 10
get_json_count = 0

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

def log_out():
    url = URL + '/{}/'.foramt(logged_in_username)

    browser.get(url)
    option_btn = browser.find_one('.dCJp8.afkep')
    option_btn.click()
    log_out_btn = browser.find('.aOOlW.HoLwm', waittime=10)[7]
    log_out_btn.click()

def set_headers():
    global logged_in_user_id

    shbid = '3317'
    shbts = '1571731121.0776558'

    cookies_list = browser.driver.get_cookies()
    cookies_dict = {}
    for cookie in cookies_list:
        cookies_dict[cookie['name']] = cookie['value']

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36'
    }

    headers['cookie'] = COOKIE.format(cookies_dict["mid"], shbid, 
        shbts, cookies_dict["ds_user_id"], cookies_dict["csrftoken"], 
        cookies_dict["sessionid"], cookies_dict["rur"], cookies_dict["urlgen"])

    logged_in_user_id = cookies_dict["ds_user_id"]

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

    global logged_in_username
    logged_in_user_url = browser.find(
        "div[class='XrOey'] a")[2].get_attribute("href")
    logged_in_username = logged_in_user_url[
        logged_in_user_url[: -1].rfind('/') + 1: -1]
    print('\n* Logged in as user (username: {}).\n'.format(logged_in_username))

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

def get_json(url, headers):
    global get_json_count

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == requests.codes['ok']:
            return response.json()
        else:
            msg = '{} - Warning: Failed to get json file (status_code: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code)
            output_log('\n' + msg, False)
            print('{} - 1 Warning: Retry to get json file.\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            sleep(WAIT_TIME)
            get_json_count += 1
            if get_json_count == MAX_GET_JSON_COUNT:
                raise RetryException()
            return get_json(url, headers)
    except Exception as e:
        msg = '{} - Warning: Failed to get json file (status_code: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code)
        output_log('\n' + msg, False)
        print('{} - 2 Warning: Retry to get json file.\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        sleep(WAIT_TIME)
        get_json_count += 1
        if get_json_count == MAX_GET_JSON_COUNT:
            raise RetryException()
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
            sleep(WAIT_TIME)
        else:
            break

    return list(urls)

def get_following_username_list(user_id, headers):
    include_reel = 'true'
    fetch_mutual = 'false'
    first_first = '24'

    url = URL_QUERY_FOLLOWING_USERS.format(HASH_FOLLOWING_USERS, 
        user_id, include_reel, fetch_mutual, first_first, '')

    js_data = get_json(url, headers)

    edges = js_data['data']['user']['edge_follow']['edges']
    following_count = js_data['data']['user']['edge_follow']['count']
    page_info = js_data['data']['user']['edge_follow']['page_info']
    if page_info['end_cursor']:
        cursor = page_info['end_cursor'][: -2]
    else:
        cursor = None
    has_next_page = page_info['has_next_page']

    username_list = list()

    pbar = tqdm(total=following_count)
    pbar.set_description("Progress")

    for edge in edges:
        username_list.append(edge['node']['username'])
        pbar.update(1)

    while has_next_page:
        url = URL_QUERY_FOLLOWING_USERS.format(HASH_FOLLOWING_USERS, 
            user_id, include_reel, fetch_mutual, FIRST, 
            FOLLOWING_USERS_SUFFIX.format(cursor))

        js_data = get_json(url, headers)

        edges = js_data['data']['user']['edge_follow']['edges']
        page_info = js_data['data']['user']['edge_follow']['page_info']
        if page_info['end_cursor']:
            cursor = page_info['end_cursor'][: -2]
        else:
            cursor = None
        has_next_page = page_info['has_next_page']

        for edge in edges:
            username_list.append(edge['node']['username'])
            pbar.update(1)

    msg = '\n\n{} - Info: Finish exploring following users. {} following users are found (username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), following_count, username)
    print(msg)

    return username_list

def get_saved_urls(headers):
    url = URL_QUERY_SAVED_POSTS.format(logged_in_username)

    js_data = get_json(url, headers)

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
        url = URL_QUERY_POSTS.format(HASH_SAVED_POSTS, user_id, FIRST, cursor)

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
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), post_count, logged_in_username)
    print(msg)

    return urls

def get_urls(html, headers):
    global user_id
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
        url = URL_QUERY_POSTS.format(HASH_NORMAL_POSTS, user_id, FIRST, cursor)

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

def get_following_users(headers, is_logged_in_user=False):
    msg = '{} - Info: Start exploring following users (username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username)
    print(msg)

    if is_logged_in_user:
        get_user_id = logged_in_user_id
    elif download_posts:
        get_user_id = user_id
    else:
        url = URL + '/{}/'.format(username)
        html = get_html(url, headers)
        get_user_id = re.findall('"profilePage_([0-9]+)"', html, re.S)[0]

    username_list = get_following_username_list(get_user_id, headers)

    save_path = os.path.join(SAVE_PATH, username)
    if not os.path.exists(save_path): 
        os.makedirs(save_path)

    filepath = os.path.join(save_path, 'following_users.txt')
    msg = '\n{} - Info: Following username list is saved in the file "{}".'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filepath)
    print(msg)

    with open(filepath, 'w', encoding='utf8') as output_file:
        for user in username_list:
            output_file.write(user + '\n')

def get_saved_posts(headers):
    msg = '{} - Info: Start exploring saved posts (logged_in_username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), logged_in_username)
    print(msg)

    urls = get_saved_urls(headers)

    save_path = os.path.join(SAVE_PATH, logged_in_username + '_saved')
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

def set_options(match):
    global get_following
    global download_posts

    options = [match.group(1).lower(), match.group(2).lower()]
    if 'f' in options :
        get_following = True

        if 'p' not in options:
            download_posts = False
    
def parse_argv(argv):
    """
        Args     Argv
        1        username 

        2        username options
        2        username start_date

        3        username start_date options
        3        username start_date end_date
        3        username - end_date

        4        username start_date end_date options
        4        username - end_date options
    """

    global START_DATE
    global END_DATE
    global username

    # Ignore letter case.
    pattern_option = re.compile(PATTERN_OPTION, re.I)
    pattern_date = re.compile(PATTERN_DATE)

    if len(argv) == 1:
        pass
    elif len(argv) == 2:
        match = pattern_option.match(argv[1])
        if match:
            set_options(match)
        elif pattern_date.match(argv[1]):
            START_DATE = argv[1]
        else:
            msg = 'Error: Unknown arguments from input file (args: 2).\n'
            raise AssertionError(msg)
    elif len(argv) == 3:
        match = pattern_option.match(argv[2])
        if argv[1] == '-' and pattern_date.match(argv[2]):
            END_DATE = argv[2]
        elif pattern_date.match(argv[1]) and match:
            set_options(match)
            START_DATE = argv[1]
        elif pattern_date.match(argv[1]) and pattern_date.match(argv[2]):
            START_DATE = argv[1]
            END_DATE = argv[2]
        else:
            msg = 'Error: Unknown arguments from input file (args: 3).\n'
            raise AssertionError(msg)
    elif len(argv) == 4:
        match = pattern_option.match(argv[3])
        if argv[1] == '-' and pattern_date.match(argv[2]) and match:
                set_options(match)
                END_DATE = argv[2]
        elif pattern_date.match(argv[1]) and pattern_date.match(argv[2]) and match:
                set_options(match)
                START_DATE = argv[1]
                END_DATE = argv[2]
        else:
            msg = 'Error: Unknown arguments from input file (args: 4).\n'
            raise AssertionError(msg)
    else:
        msg = 'Error: Unknown arguments from input file (args: {}).\n'.format(len(argv))
        raise AssertionError(msg)

    username = argv[0]

def web_crawler():
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

        for argv in username_list:
            parse_argv(argv)

            if download_posts:
                get_posts(headers)

            if get_following:
                get_following_users(headers, user_id == logged_in_user_id)


if __name__ == '__main__':
    assert len(sys.argv) == 2 or len(sys.argv) == 3, 'Error: The number of arguments is incorrect.'

    if len(sys.argv) == 2 and sys.argv[1] == "--saved":
            download_saved = True
            download_from_file = False
    if len(sys.argv) == 3:
        if sys.argv[2] == "--saved":
            download_saved = True
        else:
            raise AssertionError('Error: Unknown argument at position 3.\n')

    if not os.path.exists(SAVE_PATH): 
        os.makedirs(SAVE_PATH)

    web_crawler()
