import os
import json

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
)

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'config.json'
)


def create_session(max_retries=3, timeout=30):
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})
    retry = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=['GET'],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=32, pool_connections=16)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.timeout = timeout
    return session


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_last_template():
    config = load_config()
    return config.get('template', '{video_id}')


def save_template(template):
    config = load_config()
    config['template'] = template
    save_config(config)
