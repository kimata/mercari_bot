#!/usr/bin/env python3
# - coding: utf-8 --
from webdriver_manager.chrome import ChromeDriverManager
import coloredlogs
import logging
import logging.handlers
import io
import bz2
import inspect
import subprocess

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
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
import urllib.request

LOGIN_URL = "https://jp.mercari.com"
CONFIG_PATH = "config.yml"
LOG_PATH = "log"
CHROME_DATA_PATH = "chrome_data"
DUMP_PATH = "debug"
DATA_PATH = "data"
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


def random_sleep(sec):
    time.sleep(sec + sec / 2.0 * random.random())


def get_abs_path(path):
    return str(pathlib.Path(os.path.dirname(__file__), path))


def load_config():
    with open(get_abs_path(CONFIG_PATH)) as file:
        return yaml.safe_load(file)


def click_xpath(driver, xpath, wait=None):
    if wait is not None:
        wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.find_element(By.XPATH, xpath).click()


def get_memory_info(driver):
    total = subprocess.Popen(
        "smem -t -c pss -P chrome | tail -n 1", shell=True, stdout=subprocess.PIPE
    ).communicate()[0]
    total = int(str(total, "utf-8").strip()) // 1024

    js_heap = driver.execute_script(
        "return window.performance.memory.usedJSHeapSize"
    ) // (1024 * 1024)

    return {"total": total, "js_heap": js_heap}


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
        EC.presence_of_element_located((By.XPATH, "//mer-navigation-top-menu-item"))
    )

    if len(driver.find_elements(By.XPATH, '//button[contains(text(), "はじめる")]')) != 0:
        click_xpath(driver, '//button[contains(text(), "はじめる")]')

    menu_label = driver.find_elements(
        By.XPATH, "//mer-menu/mer-navigation-top-menu-item/span"
    )
    if (len(menu_label) != 0) and (menu_label[0].text == "アカウント"):
        return

    click_xpath(
        driver, '//mer-navigation-top-menu-item/span[contains(text(), "ログイン")]', wait
    )
    click_xpath(driver, '//span[contains(text(), "メールアドレスでログイン")]', wait)

    wait.until(
        EC.presence_of_element_located((By.XPATH, '//mer-heading[@title-label="ログイン"]'))
    )

    driver.find_element(By.XPATH, '//input[@name="email"]').send_keys(config["user"])
    driver.find_element(By.XPATH, '//input[@name="password"]').send_keys(config["pass"])
    click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, '//mer-heading[@title-label="電話番号の確認"]')
        )
    )

    code = input("認証番号: ")
    driver.find_element(By.XPATH, '//input[@name="code"]').send_keys(code)
    click_xpath(driver, '//button[contains(text(), "認証して完了する")]', wait)

    wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                '//mer-menu/mer-navigation-top-menu-item/span[contains(text(), "アカウント")]',
            )
        )
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

    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)

    return driver


def item_save(driver, wait, config, item):
    logging.info("出品情報の保存を行います．")
    item_path = pathlib.Path(DATA_PATH) / item["id"]
    os.makedirs(str(item_path), exist_ok=True)

    thumb_elem_list = driver.find_elements(By.XPATH, "//mer-item-thumbnail")
    for i, thumb_elem in enumerate(thumb_elem_list[: len(thumb_elem_list) // 2]):
        thumb_url = thumb_elem.get_attribute("src")
        thumb_path = item_path / (str(i) + ".jpg")
        if not thumb_path.exists():
            logging.info(
                "Save {url} to {path}".format(url=thumb_url, path=str(thumb_path))
            )
            urllib.request.urlretrieve(thumb_url, str(thumb_path))
            random_sleep(1)

    desc_root = driver.find_element(By.XPATH, "//mer-show-more").shadow_root

    desc_path = str(item_path / "desc.txt")
    logging.info("Save content to {path}".format(path=desc_path))
    desc = desc_root.find_element(By.CSS_SELECTOR, "div.content").text

    shipping = driver.find_element(By.XPATH, '//span[@data-testid="配送の方法"]').text.split(
        "\n"
    )[0]

    item["desc"] = desc
    item["shipping"] = shipping

    info_path = str(item_path / "info.yml")
    logging.info("Save info to {path}".format(path=info_path))

    with open(info_path, mode="w") as f:
        yaml.dump(
            item, f, default_flow_style=False, encoding="utf-8", allow_unicode=True
        )


def item_price_down(driver, wait, config, item):
    logging.info(
        "{down_step}円の値下げを行います．".format(down_step=config["price"]["down_step"])
    )
    if item["is_stop"] != 0:
        logging.info("公開停止中のため，スキップします．")
        return

    if item["price"] < config["price"]["threshold"]:
        logging.info("現在価格が{price:,}円のため，スキップします．".format(price=item["price"]))
        return

    click_xpath(driver, '//mer-button[@data-testid="checkout-button"]')
    wait.until(EC.title_contains("商品の情報を編集"))
    wait.until(EC.presence_of_element_located((By.XPATH, '//input[@name="price"]')))

    # NOTE: 梱包・発送たのメル便の場合は送料を取得
    if (
        len(driver.find_elements(By.XPATH, '//mer-price[@data-testid="shipping-fee"]'))
        != 0
    ):
        shipping_fee = int(
            driver.find_element(
                By.XPATH, '//mer-price[@data-testid="shipping-fee"]'
            ).get_attribute("value")
        )
    else:
        shipping_fee = 0

    price = item["price"] - shipping_fee

    if price < config["price"]["threshold"]:
        logging.info(
            "現在価格が{price:,}円 (送料: {shipping:,}円) のため，スキップします．".format(
                price=price, shipping=shipping_fee
            )
        )
        return

    cur_price = int(
        driver.find_element(By.XPATH, '//input[@name="price"]').get_attribute("value")
    )
    if cur_price != price:
        raise RuntimeError("ページ遷移中に価格が変更されました．")

    new_price = int((price - config["price"]["down_step"]) / 10) * 10  # 10円単位に丸める
    driver.find_element(By.XPATH, '//input[@name="price"]').send_keys(
        Keys.CONTROL + "a"
    )
    driver.find_element(By.XPATH, '//input[@name="price"]').send_keys(Keys.BACK_SPACE)
    driver.find_element(By.XPATH, '//input[@name="price"]').send_keys(new_price)
    click_xpath(driver, '//button[contains(text(), "変更する")]')

    wait.until(EC.title_contains(re.sub(" +", " ", item["name"])))

    wait.until(EC.presence_of_element_located((By.XPATH, "//mer-price")))

    new_total_price = int(
        driver.find_element(By.XPATH, "//mer-price").get_attribute("value")
    )

    if new_total_price != (new_price + shipping_fee):
        raise RuntimeError("編集後の価格が意図したものと異なっています．")

    logging.info(
        "価格を変更しました．({total:,}円 -> {new_total:,}円)".format(
            total=item["price"], new_total=new_total_price
        )
    )


def parse_item(driver, index):
    item_root = driver.find_element(
        By.XPATH,
        '//mer-list[@data-testid="listed-item-list"]/mer-list-item['
        + str(index)
        + "]//mer-item-object",
    ).shadow_root

    item_url = driver.find_element(
        By.XPATH,
        '//mer-list[@data-testid="listed-item-list"]/mer-list-item['
        + str(index)
        + "]//a",
    ).get_attribute("href")
    item_id = item_url.split("/")[-1]

    name = item_root.find_element(By.CSS_SELECTOR, "div.container").get_attribute(
        "aria-label"
    )
    price = int(
        item_root.find_element(By.CSS_SELECTOR, "mer-price").get_attribute("value")
    )
    is_stop = 0
    if len(item_root.find_elements(By.CSS_SELECTOR, "div.content > mer-text")) != 0:
        is_stop = 1

    try:
        view = int(
            item_root.find_element(
                By.CSS_SELECTOR, "mer-icon-eye-outline + span.icon-text"
            ).text
        )
    except:
        view = 0

    return {
        "id": item_id,
        "name": name,
        "price": price,
        "view": view,
        "is_stop": is_stop,
    }


def iter_items_on_display(driver, wait, config, item_func_list):
    click_xpath(
        driver, '//mer-navigation-top-menu-item/span[contains(text(), "アカウント")]', wait
    )
    click_xpath(driver, '//a[contains(text(), "出品した商品")]', wait)

    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, '//mer-list[@data-testid="listed-item-list"]/mer-list-item')
        )
    )

    item_count = len(
        driver.find_elements(
            By.XPATH, '//mer-list[@data-testid="listed-item-list"]/mer-list-item'
        )
    )

    logging.info("{item_count}個の出品があります．".format(item_count=item_count))

    list_url = driver.current_url
    for i in range(1, item_count + 1):
        item = parse_item(driver, i)

        logging.info(
            "{name} [{id}] [{price:,}円] [{view:,} view] を処理します．".format(
                id=item["id"], name=item["name"], price=item["price"], view=item["view"]
            )
        )

        driver.execute_script("window.scrollTo(0, 0);")
        item_link = driver.find_element(
            By.XPATH,
            '//mer-list[@data-testid="listed-item-list"]/mer-list-item['
            + str(i)
            + "]//a",
        )
        # NOTE: アイテムにスクロールしてから，ヘッダーに隠れないようちょっと前に戻す
        item_link.location_once_scrolled_into_view
        driver.execute_script("window.scrollTo(0, window.pageYOffset - 200);")
        item_link.click()

        wait.until(EC.title_contains(re.sub(" +", " ", item["name"])))

        for item_func in item_func_list:
            item_func(driver, wait, config, item)

        random_sleep(4)
        driver.get(list_url)
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//mer-list[@data-testid="listed-item-list"]/mer-list-item')
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
    iter_items_on_display(driver, wait, config, [item_save, item_price_down])

    mem_info = get_memory_info(driver)
    logging.info(
        "Chrome memory: {memory_total:,} MB (JS: {memory_js_heap:,} MB)".format(
            memory_total=mem_info["total"], memory_js_heap=mem_info["js_heap"]
        )
    )
except:
    logging.error("URL: {url}".format(url=driver.current_url))
    logging.error(traceback.format_exc())
    dump_page(driver, int(random.random() * 100))

driver.close()
driver.quit()

logging.info("完了しました．")
