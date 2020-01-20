# -*- coding: utf-8 -*-

from src.browser import Browser
from src.constants import *
from src.exceptions import RetryException
from src.secret import USERNAME, PASSWORD, TRANS_USERNAME, TRANS_PASSWORD

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
        python instagran_web_crawler.py [path] [options] 
    
    Args:
        path: Input path (a file including one user_id per line).

        options:
            --saved: Download saved posts.
            --transfer: Transfer following users from USERNAME to TRANS_USERNAME.

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


end_date = datetime.now().strftime("%Y-%m-%d")

SAVE_PATH = os.path.join('.', 'results')

browser = Browser(HAS_SCREEN)

download_saved = False
download_from_file = True
download_posts = True
get_following = False
transfer_following = False

logged_in_username = ''
logged_in_user_id = ''
trasnfer_from_username = ''

username = ''
user_id = ''

get_json_count = 0

# TODO: Download media which are in the specified period.

def output_log(msg, traceback_option=True):
    with open(LOG_PATH, 'a', encoding='utf8') as output_file:
        output_file.write(msg)
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
                    if func.__name__ == 'check_login':
                        tmp = 'log in. (username: {}, password: {})'.format(USERNAME, PASSWORD)
                    elif func.__name__ == 'check_log_out':
                        tmp = 'log out.'

                    msg = '{} - Error: Failed to {}\n'.format(
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tmp)
                    output_log('\n' + msg, True)

                    exc = RetryException(msg)
                    exc.__cause__ = None

                    raise exc

        return wrapped_f

    return wrap

def log_out():
    url = URL + '/{}/'.format(logged_in_username)

    browser.get(url)
    option_btn = browser.find_one('.dCJp8.afkep')
    option_btn.click()
    log_out_btn = browser.find('.aOOlW.HoLwm', waittime=10)[7]
    log_out_btn.click()

    @retry()
    def check_log_out():
        if not browser.find('._9nyy2'):
            raise RetryException()

    check_log_out()

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

def login(trans_login=False):
    global logged_in_username

    url = "{}/accounts/login/".format(URL)
    
    browser.get(url)

    if trans_login:
        username = TRANS_USERNAME
        password = TRANS_PASSWORD
        global trasnfer_from_username
        trasnfer_from_username = logged_in_username
    else:
        username = USERNAME
        password = PASSWORD

    u_input = browser.find_one('input[name="username"]')
    u_input.send_keys(username)
    p_input = browser.find_one('input[name="password"]')
    p_input.send_keys(password)

    login_btn = browser.find_one(".L3NKy")
    login_btn.click()

    @retry()
    def check_login():
        if browser.find_one('input[name="username"]'):
            raise RetryException()

    check_login()

    logged_in_user_url = browser.find(
        "div[class='XrOey'] a")[2].get_attribute("href")
    logged_in_username = logged_in_user_url[
        logged_in_user_url[: -1].rfind('/') + 1: -1]
    print('\n* Logged in as {}.\n'.format(logged_in_username))

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
            output_log('\n' + msg, True)
            raise Exception(msg)
    except Exception:
        msg = '{} - Error: Failed to get page source (status_code: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code)
        output_log('\n' + msg, True)
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
            msg = '{} - Error: Failed to get image content (status_code: {}, url: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code, url)
            output_log('\n' + msg, True)
    except Exception as e:
        msg = '{} - Error: Failed to get image content (status_code: {}, url: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.status_code, url)
        output_log('\n' + msg, True)

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

def transfer_following_users(username_list):
    button_not_follow_class = '_5f5mN       jIbKX  _6VtSN     yZn4P   '

    @retry()
    def check_follow():
        follow_btn = browser.find_one('button')
        if follow_btn.get_attribute("class") == button_not_follow_class:
            raise RetryException()

    has_followed = 0
    for username in tqdm(username_list, desc='Progress'):
        url = '{}/{}/'.format(URL, username)

        browser.get(url)

        follow_btn = browser.find_one('button')

        if follow_btn.get_attribute("class") == button_not_follow_class:
            follow_btn.click()
            check_follow()
        else:
            has_followed += 1
            msg = '{} - Info: This account has followed this user (username: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username)
            print(msg)
            output_log('\n' + msg, False)

    msg = '\n{} - Info: Finish following users. (Successful: {}, Already followed: {}, from_username: {}, to_username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), len(username_list) - has_followed, has_followed, 
        trasnfer_from_username, logged_in_username)
    print(msg)

def get_following_username_list(user_id, username, headers):
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

    msg = '\n\n{} - Info: Finish exploring saved posts. {} saved posts are found (logged_in_username: {}).\n'.format(
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

    msg = '\n\n{} - Info: Finish exploring posts. {} posts are found (username: {}).\n'.format(
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
                output_log('\n' + msg, True)
        except Exception:
            msg = '{} - Warning: Failed to download this file (url: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url)
            output_log('\n' + msg, True)

def transfer_following_to_another_account(headers):
    msg = '{} - Info: Start exploring following users (username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), logged_in_username)
    print(msg)

    username_list = get_following_username_list(logged_in_user_id, logged_in_username, headers)

    save_path = os.path.join(SAVE_PATH, logged_in_username)
    if not os.path.exists(save_path): 
        os.makedirs(save_path)

    filepath = os.path.join(save_path, 'following_users.txt')
    abs_file_path = os.path.abspath(filepath)
    msg = '\n{} - Info: Following username list is saved in the file "{}".'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), abs_file_path)
    print(msg)

    with open(filepath, 'w', encoding='utf8') as output_file:
        for user in username_list:
            output_file.write(user + '\n')

    log_out()

    # Login again.
    headers = login(trans_login=True)

    msg = '{} - Info: Start following users. (from_username: {}, to_username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), trasnfer_from_username, logged_in_username)
    print(msg)

    transfer_following_users(username_list)

def get_saved_posts(headers):
    msg = '{} - Info: Start exploring saved posts (logged_in_username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), logged_in_username)
    print(msg)

    urls = get_saved_urls(headers)

    save_path = os.path.join(SAVE_PATH, logged_in_username)
    if not os.path.exists(save_path): 
        os.makedirs(save_path)
    
    save_path = os.path.join(save_path, 'saved')
    if not os.path.exists(save_path): 
        os.makedirs(save_path)

    download_media(urls, headers, save_path)

def get_posts(headers):
    msg = '{} - Info: Start exploring posts (username: {}).\n'.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username)
    print(msg)

    url = '{}/{}/'.format(URL, username)

    html = get_html(url, headers)
    urls = get_urls(html, headers)

    save_path = os.path.join(SAVE_PATH, username)
    if not os.path.exists(save_path): 
        os.makedirs(save_path)

    save_path = os.path.join(save_path, 'posts')
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
    
def parse_options(argv):
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
    global end_date
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
            end_date = argv[2]
        elif pattern_date.match(argv[1]) and match:
            set_options(match)
            START_DATE = argv[1]
        elif pattern_date.match(argv[1]) and pattern_date.match(argv[2]):
            START_DATE = argv[1]
            end_date = argv[2]
        else:
            msg = 'Error: Unknown arguments from input file (args: 3).\n'
            raise AssertionError(msg)
    elif len(argv) == 4:
        match = pattern_option.match(argv[3])
        if argv[1] == '-' and pattern_date.match(argv[2]) and match:
                set_options(match)
                end_date = argv[2]
        elif pattern_date.match(argv[1]) and pattern_date.match(argv[2]) and match:
                set_options(match)
                START_DATE = argv[1]
                end_date = argv[2]
        else:
            msg = 'Error: Unknown arguments from input file (args: 4).\n'
            raise AssertionError(msg)
    else:
        msg = 'Error: Unknown arguments from input file (args: {}).\n'.format(len(argv))
        raise AssertionError(msg)

    username = argv[0]

def web_crawler(file_path):
    if USERNAME == '' or PASSWORD == '':
        msg = '{} - Error: Please enter your username and password in secret.py.\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        output_log('\n' + msg, False)
        raise Exception(msg)

    headers = login()

    if not os.path.exists(SAVE_PATH): 
        os.makedirs(SAVE_PATH)

    if download_saved:
        get_saved_posts(headers)

    if download_from_file:
        with open(file_path, 'r', encoding='utf8') as input_file:
            username_list = [line.split() for line in input_file if len(line.split()) != 0]

        for argv in username_list:
            parse_options(argv)

            if download_posts:
                get_posts(headers)

            if get_following:
                if download_posts:
                    get_user_id = user_id
                else:
                    url = '{}/{}/'.format(URL, username)
                    html = get_html(url, headers)
                    get_user_id = re.findall('"profilePage_([0-9]+)"', html, re.S)[0]

                username_list = get_following_username_list(get_user_id, username, headers)

                save_path = os.path.join(SAVE_PATH, username)
                if not os.path.exists(save_path): 
                    os.makedirs(save_path)

                filepath = os.path.join(save_path, 'following_users.txt')
                abs_file_path = os.path.abspath(filepath)
                msg = '\n{} - Info: Following username list is saved in the file "{}".'.format(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), abs_file_path)
                print(msg)

                with open(filepath, 'w', encoding='utf8') as output_file:
                    for user in username_list:
                        output_file.write(user + '\n')
    
    if transfer_following:
        transfer_following_to_another_account(headers)


if __name__ == '__main__':
    """ (First argument is omitted.)
    Args     Argv
    1        input_file
    1        --saved
    1        --transfer

    2        input_file --saved
    2        input_file --transfer
    2        --saved --transfer

    3        input_file --saved --transfer
    """

    assert 2 <= len(sys.argv) <= 4, 'Error: The number of arguments is incorrect.'

    file_path = ''

    sys.argv.remove(sys.argv[0])
    args = len(sys.argv)

    if "--saved" in sys.argv:
        download_saved = True
        sys.argv.remove("--saved")
    if "--transfer" in sys.argv:
        transfer_following = True
        sys.argv.remove("--transfer") 

    if args == 1:
        if len(sys.argv) == 1:
            file_path = sys.argv[0]
        else:
            download_from_file = False
    elif args == 2:
        if len(sys.argv) == 0:
            download_from_file = False
        elif len(sys.argv) == 1:
            file_path = sys.argv[0]
        else:
            raise AssertionError('Error: Unknown arguments ({}).\n'.format(str(sys.argv)))
    elif args == 3:
        if len(sys.argv) == 1:
            file_path = sys.argv[0]
        else:
            raise AssertionError('Error: Unknown arguments ({}).\n'.format(str(sys.argv)))

    web_crawler(file_path)
