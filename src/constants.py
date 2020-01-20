# -*- coding: utf-8 -*-

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
LOG_PATH = 'output.log'

"""
HAS_SCREEN:
    True: Open browser window.
    False: Close browser window.
"""
HAS_SCREEN = False

"""
WAIT_TIME:
    Recommended value: 0.3 ~ 1, according to your Internet speed.
"""
WAIT_TIME = 0.5

PATTERN_OPTION = r'-([pf])([pf]?$)'
PATTERN_DATE = r'\d\d\d\d-\d\d-\d\d'

MAX_GET_JSON_COUNT = 10
