# -*- coding: utf-8 -*-

from src.browser import Browser
from src.exceptions import RetryException
from src.secret import USERNAME, PASSWORD

from datetime import datetime
from functools import wraps
import json
import os 
import re
import requests
from requests.adapters import HTTPAdapter
import sys
from time import sleep
from tqdm import tqdm
import traceback

from urllib.request import urlopen
from bs4 import BeautifulSoup as bs


"""
    Usage:
        python instagran_web_crawler.py [path] [--saved] 
    
    Args:
        path: Input path (a file including one user_id per line).
        --saved: Download from saved.

    Notice:
        Put chromedriver.exe in folder /bin.
        Copy secret.py.dist as secret.py in the same folder.

        Input file format:
            username [start_date] [end_date]

            (If end_date is specific and no specific start_date, use '-'. 
            If start_date is specific and no specific end_date, 
            no other input is needed.)
            (Default: Posts of all time.)

            e.g.
                a123456789 2019-01-01 2019-06-01
                b987654321 2018-01-01 2019-01-01
                c111111111 - 2019-02-01
                d222222222 2019-03-01
                e333333333 
"""

# TODO: Download videos.
# TODO: Download media which are in the specified period.

URL = 'https://www.instagram.com'
URL_SAVED = 'https://www.instagram.com/{}/saved/'

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

logged_in_user = ''
download_saved = False
download_from_file = False

PATTERN_DATE = r'\d\d\d\d-\d\d-\d\d'


def output_log(msg, traceback=True):
    with open(LOG_PATH, 'a', encoding='utf8') as output_log:
        output_log.write(msg)
    if traceback:
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

def dismiss_login_prompt():
    # May be None.
    ele_login = browser.find_one(".Ls00D .Szr5J")
    if ele_login:
        ele_login.click()

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

def print_user_profile(user_profile):
    print("\n* User profile: ")
    print("name: {}".format(user_profile["name"]))
    print("description: {}".format(user_profile["description"]))
    print("photo_url: {}".format(user_profile["photo_url"]))
    print("post_num: {}".format(user_profile["post_num"]))
    print("follower_num: {}".format(user_profile["follower_num"]))
    print("following_num: {}".format(user_profile["following_num"]))
    print()

def get_user_profile(username):
    try:
        url = "%s/%s/" % (URL, username)
        browser.get(url)
        name = browser.find_one(".rhpdm").text
        description = browser.find_one(".-vDIg span")
        # If the browser visits your page, the class of the photo will change.
        photo = browser.find_one("._6q-tv")
        # Others' page.
        if photo:
            photo = photo.get_attribute("src")
        # Your page.
        else:
            photo = browser.find_one(".be6sR").get_attribute("src")

        statistics = [ele.text for ele in browser.find(".g47SY")]
        post_num, follower_num, following_num = statistics

        return {
            "name": name,
            "description": description.text if description else None,
            "photo_url": photo,
            "post_num": post_num,
            "follower_num": follower_num,
            "following_num": following_num,
        }
    except AttributeError:
        msg = '{} - Error: Failed to get the user profile (username: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username)
        output_log('\n' + msg)
        msg = ' ' + msg
        raise AttributeError(msg)

def fetch_datetime(dict_post):
    ele_datetime = browser.find_one(".eo2As .c-Yi7 ._1o9PC")
    if ele_datetime:
        datetime = ele_datetime.get_attribute("datetime")
        dict_post["datetime"] = datetime

def fetch_imgs(dict_post):
    img_urls = set()
    while True:
        ele_imgs = browser.find("._97aPb img", waittime=10)

        if isinstance(ele_imgs, list):
            for ele_img in ele_imgs:
                img_urls.add(ele_img.get_attribute("src"))
        else:
            break

        next_photo_btn = browser.find_one("._6CZji .coreSpriteRightChevron")

        if next_photo_btn:
            next_photo_btn.click()
            sleep(0.3)
        else:
            break

    dict_post["img_urls"] = list(img_urls)

# def fetch_videos(dict_post):
    # video_urls = set()
    # while True:
    #     ele_videos = browser.find(".QvAa1 ", waittime=10)

    #     if ele_videos:
    #         ele_videos.click()
    # ele_videos = browser.find(".QvAa1 ", waittime=10)
    # if ele_videos:
    #     ele_videos.click()

def download_files(url_list, username, filename):
    if not os.path.exists(SAVE_PATH): 
        os.makedirs(SAVE_PATH)

    save_path = os.path.join(SAVE_PATH, username)
    if not os.path.exists(save_path): 
        os.makedirs(save_path)

    try:
        index = 1
        for url in url_list:
            session = requests.Session()
            session.mount(url, HTTPAdapter(max_retries=5))
            downloaded = session.get(url, timeout=(5, 10))
            file_path = os.path.join(save_path, filename + 
                '_{}.jpg'.format(str(index)))
            with open(file_path, 'wb') as file:
                file.write(downloaded.content)
            index += 1
    except Exception as e:
        msg = '\n{} - Warning: Failed to download this file (url: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url)
        output_log(msg)
        print(msg)

def get_posts(username, post_num):
    @retry()
    def check_next_post(cur_key):
        # May be None.
        ele_a_datetime = browser.find_one(".eo2As .c-Yi7")

        # It takes time to load the post for some users with slow network.
        if ele_a_datetime is None:
            raise RetryException()

        next_key = ele_a_datetime.get_attribute("href")
        if cur_key == next_key:
            raise RetryException()

    browser.implicitly_wait(1)
    browser.scroll_down()
    # May be None.
    ele_post = browser.find_one(".v1Nh3 a")
    if ele_post:
        ele_post.click()

    dict_posts = {}

    pbar = tqdm(total=post_num)
    pbar.set_description("Progress")
    cur_key = None

    # Get all posts.
    for _ in range(post_num):
        dict_post = {}

        # Get post details.
        try:
            check_next_post(cur_key)

            # Get datetime and url as key. May be None.
            ele_a_datetime = browser.find_one(".eo2As .c-Yi7")
            cur_key = ele_a_datetime.get_attribute("href")
            dict_post["key"] = cur_key

            fetch_datetime(dict_post)

            # # The web crawler explores posts from new to old.
            # if dict_post["datetime"][: 10] < START_DATE:
            #     break
            # if dict_post["datetime"][: 10] > END_DATE:
            #     print(dict_post["datetime"][: 10])
            #     continue

            fetch_imgs(dict_post)
            # fetch_videos(dict_post)
        except RetryException:
            msg = '\n{} - Warning: Failed to download this file (key: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                cur_key or '[URL not fetched]')
            output_log(msg)
            print(msg)

            break
        except Exception:
            msg = '\n{} - Warning: Failed to download this file (key: {}).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                cur_key if isinstance(cur_key, str) else '[URL not fetched]')
            output_log(msg)
            print(msg)

        filename = dict_post["key"][28: -1]
        download_files(dict_post["img_urls"], username, filename)

        dict_posts[browser.current_url] = dict_post

        pbar.update(1)
        left_arrow = browser.find_one(".HBoOv")
        if left_arrow:
            left_arrow.click()

def get_saved_posts():
    url_saved = URL_SAVED.format(logged_in_user)

    browser.get(url_saved)

    url = 'https://www.instagram.com/oscar980719/?__a=1'

    cookies_list = browser.driver.get_cookies()
    cookies_dict = {}
    for cookie in cookies_list:
        cookies_dict[cookie['name']] = cookie['value']

    param = {
        '__a': '1'
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36'
    }

    headers['cookie'] = COOKIE.format(cookies_dict["mid"], cookies_dict["shbid"], 
        cookies_dict["shbts"], cookies_dict["ds_user_id"], cookies_dict["csrftoken"], 
        cookies_dict["sessionid"], cookies_dict["rur"], cookies_dict["urlgen"])
    
    response = requests.get(url=url,params=param,headers=headers)
    data = response.text
    data = json.loads(data)

    post_num = data["graphql"]["user"]["edge_saved_media"]["count"]
    get_posts(logged_in_user, post_num)

def web_crawler():
    global START_DATE
    global END_DATE
    
    if USERNAME == '' or PASSWORD == '':
        msg = '{} - Error: Please enter your username and password in secret.py (option --saved).\n'.format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        output_log('\n' + msg, traceback=False)
        raise Exception(msg)

    login()

    if download_saved:
        get_saved_posts()

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

            user_profile = get_user_profile(username)

            print_user_profile(user_profile)

            dismiss_login_prompt()

            post_num = int(user_profile["post_num"].replace(",", ""))
            print('* Total number of posts: {} (username: {}).\n'.format(post_num, username))
            get_posts(username, post_num)

if __name__ == '__main__':
    assert len(sys.argv) == 2 or len(sys.argv) == 3, 'Error: The number of arguments is incorrect.'
    if len(sys.argv) == 2:
        if sys.argv[1] == "--saved":
            download_saved = True
    if len(sys.argv) == 3:
        if sys.argv[2] == "--saved":
            download_saved = True
            download_from_file = True
        else:
            print('Error: Unknown argument at position 3.\n')

    web_crawler()
