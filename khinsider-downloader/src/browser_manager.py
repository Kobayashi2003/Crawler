import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from .config import Config

_LOCALHOST_BYPASS = 'localhost,127.0.0.1,::1'


def create_driver(config: Config):
    # Bypass system proxy for localhost so ChromeDriver <-> Chrome DevTools
    # connections are not intercepted (e.g. by Clash / VPN / corporate proxy).
    for var in ('NO_PROXY', 'no_proxy'):
        existing = os.environ.get(var, '')
        if _LOCALHOST_BYPASS not in existing:
            os.environ[var] = f'{existing},{_LOCALHOST_BYPASS}'.lstrip(',')

    if config.browser == 'auto':
        for name, fn in [('chrome', _setup_chrome), ('edge', _setup_edge), ('firefox', _setup_firefox)]:
            try:
                print(f'Trying {name}...')
                driver = fn(config)
                print(f'Successfully initialized {name}')
                return driver
            except Exception as e:
                print(f'Failed to initialize {name}: {e}')
        raise RuntimeError('No suitable browser found')

    setup = {'chrome': _setup_chrome, 'edge': _setup_edge, 'firefox': _setup_firefox}
    if config.browser not in setup:
        raise ValueError(f'Unsupported browser: {config.browser}')
    return setup[config.browser](config)


def _setup_chrome(config: Config):
    options = ChromeOptions()
    options.add_argument(f'--user-agent={config.user_agent}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-proxy-server')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    if config.headless:
        options.add_argument('--headless=new')
    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def _setup_edge(config: Config):
    options = EdgeOptions()
    options.add_argument(f'--user-agent={config.user_agent}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-proxy-server')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    if config.headless:
        options.add_argument('--headless=new')
    driver = webdriver.Edge(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def _setup_firefox(config: Config):
    options = FirefoxOptions()
    options.set_preference('general.useragent.override', config.user_agent)
    if config.headless:
        options.add_argument('--headless')
    return webdriver.Firefox(options=options)