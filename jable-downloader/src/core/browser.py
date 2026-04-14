import os
import subprocess

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from ..utils.config import USER_AGENT


def create_driver():
    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')
    options.add_argument('--headless')
    options.add_argument('--log-level=3')
    options.add_argument('--disable-logging')
    options.add_argument(f'user-agent={USER_AGENT}')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    service = Service(log_output=os.devnull)
    service.creation_flags = subprocess.CREATE_NO_WINDOW
    return webdriver.Chrome(options=options, service=service)
