from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from .config import Config

class BrowserManager:
    def __init__(self, config: Config):
        self.config = config
        self.driver = None
    
    def setup_driver(self):
        if self.config.browser == "auto":
            self.driver = self._try_browsers()
        else:
            self.driver = self._setup_specific_browser(self.config.browser)
        
        if not self.driver:
            raise Exception("No suitable browser found")
        
        return self.driver
    
    def _try_browsers(self):
        browsers = [
            ("chrome", self._setup_chrome),
            ("edge", self._setup_edge),
            ("firefox", self._setup_firefox)
        ]
        
        for browser_name, setup_func in browsers:
            try:
                print(f"Trying {browser_name}...")
                driver = setup_func()
                print(f"Successfully initialized {browser_name}")
                return driver
            except Exception as e:
                print(f"Failed to initialize {browser_name}: {e}")
                continue
        
        return None
    
    def _setup_specific_browser(self, browser_name):
        setup_functions = {
            "chrome": self._setup_chrome,
            "edge": self._setup_edge,
            "firefox": self._setup_firefox
        }
        
        if browser_name not in setup_functions:
            raise ValueError(f"Unsupported browser: {browser_name}")
        
        return setup_functions[browser_name]()
    
    def _setup_chrome(self):
        options = ChromeOptions()
        self._configure_chrome_options(options)
        
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        self._configure_chrome_driver(driver)
        
        return driver
    
    def _setup_edge(self):
        options = EdgeOptions()
        self._configure_edge_options(options)
        
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
        self._configure_edge_driver(driver)
        
        return driver
    
    def _setup_firefox(self):
        options = FirefoxOptions()
        self._configure_firefox_options(options)
        
        service = FirefoxService(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=options)
        
        return driver
    
    def _configure_chrome_options(self, options):
        options.add_argument(f'--user-agent={self.config.user_agent}')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        if self.config.headless:
            options.add_argument('--headless')
    
    def _configure_edge_options(self, options):
        options.add_argument(f'--user-agent={self.config.user_agent}')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        if self.config.headless:
            options.add_argument('--headless')
    
    def _configure_firefox_options(self, options):
        options.set_preference("general.useragent.override", self.config.user_agent)
        
        if self.config.headless:
            options.add_argument('--headless')
    
    def _configure_chrome_driver(self, driver):
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def _configure_edge_driver(self, driver):
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def quit(self):
        if self.driver:
            self.driver.quit()