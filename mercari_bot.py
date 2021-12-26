#!/usr/bin/env python3
# - coding: utf-8 --
import chromedriver_binary
import coloredlogs
import logging
import logging.handlers
import io
import bz2
import inspect

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import sys
import random
import inspect
import re

import yaml
import pprint
import pathlib
import traceback

LOGIN_URL = "https://jp.mercari.com"
CONFIG_PATH = "config.yml"
LOG_PATH = "log"
CHROME_DATA_PATH = "chrome_data"
PRICE_DOWN_STEP = 100
PRICE_THRESHOLD = 3000
DUMP_PATH = "debug"
LOG_FORMAT = (
    "%(asctime)s %(levelname)s [%(filename)s:%(lineno)s %(funcName)s] %(message)s"
)


class GZipRotator:
    def namer(name):
        return name + ".bz2"

    def rotator(source, dest):
        with open(source, "rb") as fs:
            with bz2.open(dest, "wb") as fd:
                fd.writelines(fs)
        os.remove(source)


def logger_init():
    coloredlogs.install(fmt=LOG_FORMAT)

    log_path = pathlib.Path(LOG_PATH)
    os.makedirs(str(log_path), exist_ok=True)

    logger = logging.getLogger()
    log_handler = logging.handlers.RotatingFileHandler(
        str(log_path / "mercari_bot.log"),
        encoding="utf8",
        maxBytes=1 * 1024 * 1024,
        backupCount=10,
    )
    log_handler.formatter = logging.Formatter(
        fmt=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"
    )
    log_handler.namer = GZipRotator.namer
    log_handler.rotator = GZipRotator.rotator

    logger.addHandler(log_handler)


def get_abs_path(path):
    return str(pathlib.Path(os.path.dirname(__file__), path))


def load_config():
    with open(get_abs_path(CONFIG_PATH)) as file:
        return yaml.safe_load(file)


def click_xpath(driver, xpath, wait=None):
    if wait is not None:
        wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.find_element_by_xpath(xpath).click()


def expand_shadow_element(driver, element):
    shadow_root = driver.execute_script("return arguments[0].shadowRoot", element)
    return shadow_root


def dump_page(driver, index):
    name = inspect.stack()[1].function.replace("<", "").replace(">", "")
    dump_path = pathlib.Path(DUMP_PATH)

    os.makedirs(str(dump_path), exist_ok=True)

    png_path = dump_path / (
        "{name}_{index:02d}.{ext}".format(name=name, index=index, ext="png")
    )
    htm_path = dump_path / (
        "{name}_{index:02d}.{ext}".format(name=name, index=index, ext="htm")
    )

    driver.save_screenshot(str(png_path))

    with open(str(htm_path), "w") as f:
        f.write(driver.page_source)


def login(driver, wait, config):
    driver.get(LOGIN_URL)

    time.sleep(1)  # NOTE: これを削ると NG になる...

    wait.until(
        lambda x: x.find_elements_by_xpath('//mer-text[contains(text(), "ログイン")]')
        or x.find_elements_by_xpath('//mer-text[contains(text(), "アカウント")]')
        or x.find_elements_by_xpath('//button[contains(text(), "はじめる")]')
    )

    if len(driver.find_elements_by_xpath('//button[contains(text(), "はじめる")]')) != 0:
        click_xpath(driver, '//button[contains(text(), "はじめる")]')

    # NOTE: 「アカウント」がある場合は，ログイン済み
    if len(driver.find_elements_by_xpath('//mer-text[contains(text(), "アカウント")]')) != 0:
        return

    click_xpath(driver, '//mer-text[contains(text(), "ログイン")]', wait)
    click_xpath(driver, '//span[contains(text(), "メールアドレスでログイン")]', wait)

    wait.until(
        EC.presence_of_element_located((By.XPATH, '//mer-heading[@title-label="ログイン"]'))
    )

    driver.find_element_by_xpath('//input[@name="email"]').send_keys(config["user"])
    driver.find_element_by_xpath('//input[@name="password"]').send_keys(config["pass"])
    click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, '//mer-heading[@title-label="電話番号の確認"]')
        )
    )

    code = input("認証番号: ")
    driver.find_element_by_xpath('//input[@name="code"]').send_keys(code)
    click_xpath(driver, '//button[contains(text(), "認証して完了する")]', wait)

    wait.until(
        EC.element_to_be_clickable((By.XPATH, '//mer-text[contains(text(), "アカウント")]'))
    )


def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--lang=ja-JP")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        '--user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36"'
    )
    options.add_argument("--user-data-dir=" + get_abs_path(CHROME_DATA_PATH))

    driver = webdriver.Chrome(options=options)

    return driver


def iter_items_on_display(driver, wait, item_func):
    click_xpath(driver, '//mer-text[contains(text(), "アカウント")]')
    click_xpath(driver, '//a[contains(text(), "出品した商品")]', wait)

    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, '//mer-list[@data-testid="listed-item-list"]/mer-list-item')
        )
    )

    item_count = len(
        driver.find_elements_by_xpath(
            '//mer-list[@data-testid="listed-item-list"]/mer-list-item'
        )
    )

    logging.info("{item_count}個の出品があります．".format(item_count=item_count))

    list_url = driver.current_url
    for i in range(1, item_count):
        item_root = expand_shadow_element(
            driver,
            driver.find_element_by_xpath(
                '//mer-list[@data-testid="listed-item-list"]/mer-list-item['
                + str(i)
                + "]//mer-item-object"
            ),
        )

        name = item_root.find_element_by_css_selector("div.container").get_attribute(
            "aria-label"
        )
        price = int(
            item_root.find_element_by_css_selector("mer-price").get_attribute("value")
        )

        driver.find_element_by_xpath(
            '//mer-list[@data-testid="listed-item-list"]/mer-list-item['
            + str(i)
            + "]//a"
        ).click()

        wait.until(EC.title_contains(re.sub(" +", " ", name)))

        logging.info("{name} を処理します．".format(name=name))
        item_func(driver, wait, name, price)

        time.sleep(4 + (6 * random.random()))
        driver.get(list_url)
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//mer-list[@data-testid="listed-item-list"]/mer-list-item')
            )
        )


def item_price_down(driver, wait, name, total_price):
    if total_price < PRICE_THRESHOLD:
        logging.info("現在価格が{price:,}円のため，スキップします．".format(price=total_price))
        return

    click_xpath(driver, '//mer-button[@data-testid="checkout-button"]')
    wait.until(EC.title_contains("商品の情報を編集"))
    wait.until(EC.presence_of_element_located((By.XPATH, '//input[@name="price"]')))

    # NOTE: 梱包・発送たのメル便の場合は送料を取得
    if (
        len(driver.find_elements_by_xpath('//mer-price[@data-testid="shipping-fee"]'))
        != 0
    ):
        shipping_fee = int(
            driver.find_element_by_xpath(
                '//mer-price[@data-testid="shipping-fee"]'
            ).get_attribute("value")
        )
    else:
        shipping_fee = 0

    price = total_price - shipping_fee

    if price < PRICE_THRESHOLD:
        logging.info(
            "現在価格が{price:,}円 (送料: {shipping:,}円) のため，スキップします．".format(
                price=price, shipping=shipping_fee
            )
        )
        return

    cur_price = int(
        driver.find_element_by_xpath('//input[@name="price"]').get_attribute("value")
    )
    if cur_price != price:
        raise RuntimeError("ページ遷移中に価格が変更されました．")

    new_price = int((price - PRICE_DOWN_STEP) / 10) * 10  # 10円単位に丸める
    driver.find_element_by_xpath('//input[@name="price"]').send_keys(Keys.CONTROL + "a")
    driver.find_element_by_xpath('//input[@name="price"]').send_keys(Keys.BACK_SPACE)
    driver.find_element_by_xpath('//input[@name="price"]').send_keys(new_price)
    click_xpath(driver, '//button[contains(text(), "変更する")]')

    wait.until(EC.title_contains(re.sub(" +", " ", name)))

    wait.until(EC.presence_of_element_located((By.XPATH, "//mer-price")))

    new_total_price = int(
        driver.find_element_by_xpath("//mer-price").get_attribute("value")
    )

    if new_total_price != (new_price + shipping_fee):
        raise RuntimeError("編集後の価格が意図したものと異なっています．")

    logging.info(
        "価格を変更しました．({total:,}円 -> {new_total:,}円)".format(
            total=total_price, new_total=new_total_price
        )
    )


os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))

logger_init()

logging.info("開始します．")

config = load_config()
driver = create_driver()

wait = WebDriverWait(driver, 5)

try:
    login(driver, wait, config)
    iter_items_on_display(driver, wait, item_price_down)
except Exception as e:
    logging.error("URL: {url}".format(url=driver.current_url))
    logging.error(e.message)
    logging.error(traceback.format_exc())
    dump_page(driver, int(random.random() * 100))

driver.close()
driver.quit()

logging.info("完了しました．")
