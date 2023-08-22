#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import logging.handlers

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support import expected_conditions as EC

import time
import os
import sys
import random
import re
import yaml

import pathlib
import traceback
import urllib.request

from selenium_util import (
    create_driver,
    click_xpath,
    wait_patiently,
    dump_page,
    clean_dump,
    random_sleep,
    log_memory_usage,
)
import logger
import notify_mail
import mercari
import notify_slack
from config import load_config

WAIT_TIMEOUT_SEC = 15
WAIT_RETRY_COUNT = 1

DATA_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data"
LOG_PATH = DATA_PATH / "log"

CHROME_DATA_PATH = DATA_PATH / "chrome"
RECORD_PATH = str(DATA_PATH / "record")
DUMP_PATH = str(DATA_PATH / "debug")

DRIVER_LOG_PATH = str(LOG_PATH / "webdriver.log")
HIST_CSV_PATH = str(LOG_PATH / "history.csv")

ITEM_XPATH = '//div[@data-testid="listed-item-list"]/div[@data-testid="merListItem-container"]'

# NOTE: True にすると，最初のアイテムだけ処理され，価格変更も行われない
DEBUG = False


def item_save(driver, wait, profile, item):
    logging.info("出品情報の保存を行います．")
    item_path = pathlib.Path(RECORD_PATH) / item["id"]
    os.makedirs(str(item_path), exist_ok=True)

    thumb_elem_list = driver.find_elements(By.XPATH, "//mer-item-thumbnail")
    for i, thumb_elem in enumerate(thumb_elem_list[: len(thumb_elem_list) // 2]):
        thumb_url = thumb_elem.get_attribute("src")
        thumb_path = item_path / (str(i) + ".jpg")
        if not thumb_path.exists():
            logging.info("Save {url} to {path}".format(url=thumb_url, path=str(thumb_path)))
            urllib.request.urlretrieve(thumb_url, str(thumb_path))
            random_sleep(1)

    desc_root = driver.find_element(By.XPATH, "//mer-show-more").shadow_root

    desc_path = str(item_path / "desc.txt")
    logging.info("Save content to {path}".format(path=desc_path))
    desc = desc_root.find_element(By.CSS_SELECTOR, "div.content").text

    shipping = driver.find_element(By.XPATH, '//span[@data-testid="配送の方法"]').text.split("\n")[0]

    item["desc"] = desc
    item["shipping"] = shipping

    info_path = str(item_path / "info.yml")
    logging.info("Save info to {path}".format(path=info_path))

    with open(info_path, mode="w") as f:
        yaml.dump(item, f, default_flow_style=False, encoding="utf-8", allow_unicode=True)


def item_price_down(driver, wait, profile, item):
    if item["is_stop"] != 0:
        logging.info("公開停止中のため，スキップします．")
        return

    modified_text = driver.find_element(
        By.XPATH,
        '//div[@id="item-info"]//div[contains(@class,"merShowMore")]/following-sibling::p[contains(@class, "merText")]',
    ).text

    if re.compile(r"秒前").search(modified_text):
        modified_hour = 0
    elif re.compile(r"分前").search(modified_text):
        modified_hour = 0
    elif re.compile(r"時間前").search(modified_text):
        modified_hour = int("".join(filter(str.isdigit, modified_text)))
    elif re.compile(r"日前").search(modified_text):
        modified_hour = int("".join(filter(str.isdigit, modified_text))) * 24
    elif re.compile(r"か月前").search(modified_text):
        modified_hour = int("".join(filter(str.isdigit, modified_text))) * 24 * 30
    else:
        modified_hour = -1

    if modified_hour < profile["interval"]["hour"]:
        logging.info("更新してから {hour} 時間しか経過していないため，スキップします．".format(hour=modified_hour))
        return

    logging.info("{down_step}円の値下げを行います．".format(down_step=profile["price"]["down_step"]))

    if item["price"] < profile["price"]["threshold"]:
        logging.info("現在価格が{price:,}円のため，スキップします．".format(price=item["price"]))
        return

    click_xpath(driver, '//div[@data-testid="checkout-button"]')
    wait_patiently(driver, wait, EC.title_contains("商品の情報を編集"))

    # NOTE: 食品などの場合，「出品情報の確認」の表示が出るので，「OK」ボタンを押す
    if len(driver.find_elements(By.XPATH, '//button[contains(text(), "OK")]')) != 0:
        logging.info("「出品情報の確認」を閉じます")
        click_xpath(driver, '//button[contains(text(), "OK")]')

    wait.until(EC.presence_of_element_located((By.XPATH, '//input[@name="price"]')))

    # NOTE: 梱包・発送たのメル便の場合は送料を取得
    if len(driver.find_elements(By.XPATH, '//span[@data-testid="shipping-fee"]')) != 0:
        shipping_fee = int(
            driver.find_element(
                By.XPATH,
                '//span[@data-testid="shipping-fee"]/span[contains(@class, "number")]',
            ).text.replace(",", "")
        )
    else:
        shipping_fee = 0

    price = item["price"] - shipping_fee

    if price < profile["price"]["threshold"]:
        logging.info(
            "現在価格が{price:,}円 (送料: {shipping:,}円) のため，スキップします．".format(price=price, shipping=shipping_fee)
        )
        return

    cur_price = int(driver.find_element(By.XPATH, '//input[@name="price"]').get_attribute("value"))
    if cur_price != price:
        raise RuntimeError("ページ遷移中に価格が変更されました．")

    if not DEBUG:
        new_price = int((price - profile["price"]["down_step"]) / 10) * 10  # 10円単位に丸める
    else:
        new_price = price

    driver.find_element(By.XPATH, '//input[@name="price"]').send_keys(Keys.CONTROL + "a")
    driver.find_element(By.XPATH, '//input[@name="price"]').send_keys(Keys.BACK_SPACE)
    driver.find_element(By.XPATH, '//input[@name="price"]').send_keys(new_price)
    random_sleep(2)
    click_xpath(driver, '//button[contains(text(), "変更する")]')

    time.sleep(1)
    click_xpath(driver, '//button[contains(text(), "このまま出品する")]', is_warn=False)

    wait_patiently(driver, wait, EC.title_contains(re.sub(" +", " ", item["name"])))
    wait_patiently(
        driver,
        wait,
        EC.presence_of_element_located((By.XPATH, '//div[@data-testid="price"]')),
    )

    # NOTE: 価格更新が反映されていない場合があるので，再度ページを取得する
    time.sleep(3)
    driver.get(driver.current_url)
    wait.until(EC.presence_of_element_located((By.XPATH, '//div[@data-testid="price"]')))

    new_total_price = int(
        re.sub(
            ",",
            "",
            driver.find_element(By.XPATH, '//div[@data-testid="price"]/span[2]').text,
        )
    )

    if new_total_price != (new_price + shipping_fee):
        raise RuntimeError(
            "編集後の価格が意図したものと異なっています．(期待値: {exp:,}円, 実際: {act:,}円)".format(
                exp=new_price + shipping_fee, act=new_total_price
            )
        )

    logging.info(
        "価格を変更しました．({total:,}円 -> {new_total:,}円)".format(total=item["price"], new_total=new_total_price)
    )


def parse_item(driver, index):
    item_root = driver.find_element(
        By.XPATH,
        ITEM_XPATH + "[" + str(index) + "]//mer-item-object",
    ).shadow_root

    item_url = driver.find_element(
        By.XPATH,
        ITEM_XPATH + "[" + str(index) + "]//a",
    ).get_attribute("href")
    item_id = item_url.split("/")[-1]

    name = item_root.find_element(By.CSS_SELECTOR, "div.container").get_attribute("aria-label")
    price = int(item_root.find_element(By.CSS_SELECTOR, "mer-price").get_attribute("value"))
    is_stop = 0
    if len(item_root.find_elements(By.CSS_SELECTOR, "span.information-label")) != 0:
        is_stop = 1

    try:
        view = int(item_root.find_element(By.CSS_SELECTOR, "mer-icon-eye-outline + span.icon-text").text)
    except:
        view = 0

    return {
        "id": item_id,
        "name": name,
        "price": price,
        "view": view,
        "is_stop": is_stop,
    }


def iter_items_on_display(driver, wait, profile, item_func_list):
    click_xpath(
        driver,
        '//div[@class="merNavigationTopMenuItem"]//button[contains(text(), "アカウント")]',
        wait,
    )
    click_xpath(driver, '//a[contains(text(), "出品した商品")]', wait)

    wait.until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                ITEM_XPATH,
            )
        )
    )

    time.sleep(1)

    item_count = len(
        driver.find_elements(
            By.XPATH,
            ITEM_XPATH,
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
            ITEM_XPATH + "[" + str(i) + "]//a",
        )
        # NOTE: アイテムにスクロールしてから，ヘッダーに隠れないようちょっと前に戻す
        item_link.location_once_scrolled_into_view
        driver.execute_script("window.scrollTo(0, window.pageYOffset - 200);")
        item_link.click()

        wait.until(EC.title_contains(re.sub(" +", " ", item["name"])))

        for item_func in item_func_list:
            item_func(driver, wait, profile, item)

        random_sleep(4)
        driver.get(list_url)
        wait.until(EC.presence_of_element_located((By.XPATH, ITEM_XPATH)))

        if DEBUG:
            break


def do_work(config, profile):
    driver = create_driver(profile["name"])

    wait = WebDriverWait(driver, WAIT_TIMEOUT_SEC)
    ret_code = -1

    try:
        mercari.warmup(driver)

        mercari.login(config, driver, wait, profile)
        iter_items_on_display(driver, wait, profile, [item_price_down])

        log_memory_usage(driver)

        logging.info("Finish.")
        ret_code = 0
    except:
        logging.error("URL: {url}".format(url=driver.current_url))
        logging.error(traceback.format_exc())

        if "slack" in config:
            notify_slack.error(
                config["slack"]["bot_token"],
                config["slack"]["info"]["channel"],
                traceback.format_exc(),
                config["slack"]["error"]["interval_min"],
            )

        dump_page(driver, int(random.random() * 100))
        clean_dump()

    driver.close()
    driver.quit()

    return ret_code


log_str_io = logger.init("bot.mercari.inventory", level=logging.INFO, is_str_log=True)

logging.info("Start.")

config = load_config()

ret_code = 0
for profile in config["profile"]:
    ret_code += do_work(config, profile)

if "mail" in config:
    notify_mail.send(config, "<br />".join(log_str_io.getvalue().splitlines()), is_log_message=False)
if "slack" in config:
    notify_slack.info(
        config["slack"]["bot_token"],
        config["slack"]["info"]["channel"],
        log_str_io.getvalue(),
    )

sys.exit(ret_code)
