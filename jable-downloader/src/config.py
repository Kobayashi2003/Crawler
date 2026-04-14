import os
import json

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 6.1; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36'
)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')


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
