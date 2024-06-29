#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import inspect
import logging
import os
import random
import subprocess
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

WAIT_RETRY_COUNT = 1
AGENT_NAME = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    + "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


def create_driver_impl(profile_name, data_path, agent_name, is_headless):
    chrome_data_path = data_path / "chrome"
    log_path = data_path / "log"

    os.makedirs(chrome_data_path, exist_ok=True)
    os.makedirs(log_path, exist_ok=True)

    options = Options()

    if is_headless:
        options.add_argument("--headless")

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")  # for Docker
    options.add_argument("--disable-dev-shm-usage")  # for Docker

    options.add_argument("--disable-desktop-notifications")
    options.add_argument("--disable-extensions")

    options.add_argument("--lang=ja-JP")
    options.add_argument("--window-size=1920,1200")

    options.add_argument("--user-data-dir=" + str(chrome_data_path / profile_name))

    options.add_argument("user-agent={agent_name}".format(agent_name=agent_name))

    driver = webdriver.Chrome(
        service=Service(
            log_path=str(log_path / "webdriver.log"),
            service_args=["--verbose"],
        ),
        options=options,
    )

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {
            "userAgent": agent_name,
            "acceptLanguage": "ja,en-US;q=0.9,en;q=0.8",
            "platform": "macOS",
            "userAgentMetadata": {
                "brands": [
                    {"brand": "Google Chrome", "version": "123"},
                    {"brand": "Not:A-Brand", "version": "8"},
                    {"brand": "Chromium", "version": "123"},
                ],
                "platform": "macOS",
                "platformVersion": "15.0.0",
                "architecture": "x86",
                "model": "",
                "mobile": False,
                "bitness": "64",
                "wow64": False,
            },
        },
    )

    driver.set_page_load_timeout(30)

    return driver


def create_driver(profile_name, data_path, agent_name=AGENT_NAME, is_headless=True):
    # NOTE: 1回だけ自動リトライ
    try:
        return create_driver_impl(profile_name, data_path, agent_name, is_headless)
    except:
        return create_driver_impl(profile_name, data_path, agent_name, is_headless)


def xpath_exists(driver, xpath):
    return len(driver.find_elements(By.XPATH, xpath)) != 0


def get_text(driver, xpath, safe_text):
    if len(driver.find_elements(By.XPATH, xpath)) != 0:
        return driver.find_element(By.XPATH, xpath).text.strip()
    else:
        return safe_text


def click_xpath(driver, xpath, wait=None, is_warn=True):
    if wait is not None:
        wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        time.sleep(0.05)

    if xpath_exists(driver, xpath):
        elem = driver.find_element(By.XPATH, xpath)
        action = ActionChains(driver)
        action.move_to_element(elem)
        action.perform()

        elem.click()
        return True
    else:
        if is_warn:
            logging.warning("Element is not found: {xpath}".format(xpath=xpath))
        return False


def is_display(driver, xpath):
    return (len(driver.find_elements(By.XPATH, xpath)) != 0) and (
        driver.find_element(By.XPATH, xpath).is_displayed()
    )


def random_sleep(sec):
    RATIO = 0.8

    time.sleep((sec * RATIO) + (sec * (1 - RATIO) * 2) * random.random())


def wait_patiently(driver, wait, target):
    error = None
    for _ in range(WAIT_RETRY_COUNT + 1):
        try:
            wait.until(target)
            return
        except TimeoutException as e:
            logging.warning(
                "タイムアウトが発生しました．({func} in {file} line {line})".format(
                    func=inspect.stack()[1].function,
                    file=inspect.stack()[1].filename,
                    line=inspect.stack()[1].lineno,
                )
            )
            driver.refresh()
            error = e
            pass
    raise error


def dump_page(driver, index, dump_path):
    name = inspect.stack()[1].function.replace("<", "").replace(">", "")

    dump_path.mkdir(parents=True, exist_ok=True)

    png_path = dump_path / ("{name}_{index:02d}.{ext}".format(name=name, index=index, ext="png"))
    htm_path = dump_path / ("{name}_{index:02d}.{ext}".format(name=name, index=index, ext="htm"))

    driver.save_screenshot(str(png_path))

    with open(str(htm_path), "w", encoding="utf-8") as f:
        f.write(driver.page_source)

    logging.info(
        "page dump: {index:02d} from {func} in {file} line {line}".format(
            index=index,
            func=inspect.stack()[1].function,
            file=inspect.stack()[1].filename,
            line=inspect.stack()[1].lineno,
        )
    )


def clear_cache(driver):
    driver.execute_cdp_cmd("Network.clearBrowserCache", {})


def clean_dump(dump_path, keep_days=1):
    if not dump_path.exists():
        return

    time_threshold = datetime.timedelta(keep_days)

    for item in dump_path.iterdir():
        if not item.is_file():
            continue
        time_diff = datetime.datetime.now() - datetime.datetime.fromtimestamp(item.stat().st_mtime)
        if time_diff > time_threshold:
            logging.info(
                "remove {path} [{day:,} day(s) old].".format(path=item.absolute(), day=time_diff.days)
            )
            item.unlink(missing_ok=True)


def get_memory_info(driver):
    total = subprocess.Popen(
        "smem -t -c pss -P chrome | tail -n 1", shell=True, stdout=subprocess.PIPE
    ).communicate()[0]
    total = int(str(total, "utf-8").strip()) // 1024

    js_heap = driver.execute_script("return window.performance.memory.usedJSHeapSize") // (1024 * 1024)

    return {"total": total, "js_heap": js_heap}


def log_memory_usage(driver):
    mem_info = get_memory_info(driver)
    logging.info(
        "Chrome memory: {memory_total:,} MB (JS: {memory_js_heap:,} MB)".format(
            memory_total=mem_info["total"], memory_js_heap=mem_info["js_heap"]
        )
    )


def warmup(driver, keyword, url_pattern):
    # NOTE: ダミーアクセスを行って BOT ではないと思わせる．(効果なさそう...)
    driver.get("https://www.google.com/")
    time.sleep(3)

    driver.find_element(By.XPATH, '//textarea[@name="q"]').send_keys(keyword)
    driver.find_element(By.XPATH, '//textarea[@name="q"]').send_keys(Keys.ENTER)

    time.sleep(3)

    driver.find_element(
        By.XPATH, '//a[contains(@href, "{url_pattern}")]'.format(url_pattern=url_pattern)
    ).click()

    time.sleep(3)


class browser_tab:
    def __init__(self, driver, url):
        self.driver = driver
        self.url = url

    def __enter__(self):
        self.driver.execute_script("window.open('{url}', '_blank');".format(url=self.url))
        self.driver.switch_to.window(self.driver.window_handles[-1])
        time.sleep(0.1)

    def __exit__(self, exception_type, exception_value, traceback):
        self.driver.close()
        self.driver.switch_to.window(self.driver.window_handles[-1])
        time.sleep(0.1)


if __name__ == "__main__":
    clean_dump()
