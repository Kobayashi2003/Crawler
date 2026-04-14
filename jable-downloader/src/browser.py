from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from .config import USER_AGENT


def create_driver():
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    options.add_argument('--headless')
    options.add_argument(f'user-agent={USER_AGENT}')
    return webdriver.Chrome(options=options)
