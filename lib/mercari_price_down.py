#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import logging
import logging.handlers
import os
import pathlib
import random
import re
import time
import traceback

import mercari
import notify_slack
import PIL.Image
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium_util import (
    clean_dump,
    clear_cache,
    click_xpath,
    create_driver,
    dump_page,
    log_memory_usage,
    random_sleep,
    wait_patiently,
)

WAIT_TIMEOUT_SEC = 15
WAIT_RETRY_COUNT = 1

DATA_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data"
DUMP_PATH = DATA_PATH / "debug"

LOG_PATH = DATA_PATH / "log"

CHROME_DATA_PATH = DATA_PATH / "chrome"

DRIVER_LOG_PATH = str(LOG_PATH / "webdriver.log")
HIST_CSV_PATH = str(LOG_PATH / "history.csv")


def get_modified_hour(driver):
    modified_text = driver.find_element(
        By.XPATH,
        '//div[@id="item-info"]//div[contains(@class,"merShowMore")]'
        + '/following-sibling::p[contains(@class, "merText")]',
    ).text

    if re.compile(r"秒前").search(modified_text):
        return 0
    elif re.compile(r"分前").search(modified_text):
        return 0
    elif re.compile(r"時間前").search(modified_text):
        return int("".join(filter(str.isdigit, modified_text)))
    elif re.compile(r"日前").search(modified_text):
        return int("".join(filter(str.isdigit, modified_text))) * 24
    elif re.compile(r"か月前").search(modified_text):
        return int("".join(filter(str.isdigit, modified_text))) * 24 * 30
    else:
        return -1


def get_discount_step(profile, price, shipping_fee, favorite_count):
    for discount_info in reversed(sorted(profile["discount"], key=lambda x: x["favorite_count"])):
        if favorite_count >= discount_info["favorite_count"]:
            if price >= discount_info["threshold"]:
                return discount_info["step"]
            else:
                logging.info(
                    "現在価格が{price:,}円 (送料: {shipping:,}円) のため，スキップします．".format(
                        price=price, shipping=shipping_fee
                    )
                )
                return None

    logging.info("イイねの数({favorite_count})が条件を満たさなかったので，スキップします．".format(favorite_count=favorite_count))
    return None


def execute_item(driver, wait, profile, mode, item):
    if item["is_stop"] != 0:
        logging.info("公開停止中のため，スキップします．")
        return

    modified_hour = get_modified_hour(driver)

    if modified_hour < profile["interval"]["hour"]:
        logging.info("更新してから {hour} 時間しか経過していないため，スキップします．".format(hour=modified_hour))
        return

    favorite_text = driver.find_element(
        By.XPATH,
        '//div[@data-testid="icon-heart-button"]/button',
    ).get_attribute("aria-label")

    if re.search(r"\d+", favorite_text):
        favorite_count = int(favorite_text)
    else:
        favorite_count = 0

    click_xpath(driver, '//div[@data-testid="checkout-button"]')

    wait.until(EC.title_contains("商品の情報を編集"))

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

    cur_price = int(driver.find_element(By.XPATH, '//input[@name="price"]').get_attribute("value"))
    if cur_price != price:
        raise RuntimeError("ページ遷移中に価格が変更されました．")

    discount_step = get_discount_step(profile, price, shipping_fee, favorite_count)
    if discount_step is None:
        return

    if mode["debug"]:
        new_price = price
    else:
        new_price = int((price - discount_step) / 10) * 10  # 10円単位に丸める

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


def execute(config, profile, data_path, mode):
    driver = create_driver(profile["name"], data_path)

    clear_cache(driver)

    wait = WebDriverWait(driver, WAIT_TIMEOUT_SEC)
    ret_code = -1

    try:
        mercari.warmup(driver)

        mercari.login(config, driver, wait, profile)
        mercari.iter_items_on_display(driver, wait, profile, mode, [execute_item])

        log_memory_usage(driver)

        ret_code = 0
    except:
        logging.error("URL: {url}".format(url=driver.current_url))
        logging.error(traceback.format_exc())

        if "slack" in config:
            notify_slack.error_with_image(
                config["slack"]["bot_token"],
                config["slack"]["error"]["channel"]["name"],
                config["slack"]["error"]["channel"]["id"],
                config["slack"]["from"],
                traceback.format_exc(),
                {
                    "data": PIL.Image.open((io.BytesIO(driver.get_screenshot_as_png()))),
                    "text": "エラー時のスクリーンショット",
                },
                interval_min=config["slack"]["error"]["interval_min"],
            )

        dump_page(driver, int(random.random() * 100), DUMP_PATH)
        clean_dump()

    driver.close()
    driver.quit()

    return ret_code
