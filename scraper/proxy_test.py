import re
from typing import Optional
import os
from seleniumwire import webdriver
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager



def selenium_proxy(endpoint: str) -> dict:
    wire_options = {
        "proxy": {
            "http": f"http://{endpoint}",
            "https": f"https://{endpoint}",
        }
    }

    return wire_options


def get_ip_via_chrome():
    manage_driver = Service(GeckoDriverManager().install())
    options = webdriver.FirefoxOptions()
    options.headless = False
    proxies = selenium_proxy(os.environ["PROXY_ENDPOINT"])
    driver = webdriver.Firefox(
        service=manage_driver, options=options, seleniumwire_options=proxies
    )
    driver.get("https://google.com")
    return f'\nYour IP is: {re.search(r"[0-9].{2,}", driver.page_source).group()}'


if __name__ == "__main__":
    print(get_ip_via_chrome())