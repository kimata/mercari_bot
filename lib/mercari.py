#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import random
import re
import time
import traceback

import captcha
import captcha_slack
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium_util import click_xpath, dump_page, random_sleep

RETRY_COUNT = 3

LOGIN_URL = "https://jp.mercari.com"
ITEM_XPATH = '//div[@data-testid="listed-item-list"]/div[@data-testid="merListItem-container"]'


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


def execute_item(driver, wait, profile, mode, index, item_func_list):
    item = parse_item(driver, index)

    logging.info(
        "{name} [{id}] [{price:,}円] [{view:,} view] を処理します．".format(
            id=item["id"], name=item["name"], price=item["price"], view=item["view"]
        )
    )

    driver.execute_script("window.scrollTo(0, 0);")
    item_link = driver.find_element(
        By.XPATH,
        ITEM_XPATH + "[" + str(index) + "]//a",
    )
    # NOTE: アイテムにスクロールしてから，ヘッダーに隠れないようちょっと前に戻す
    item_link.location_once_scrolled_into_view
    driver.execute_script("window.scrollTo(0, window.pageYOffset - 200);")
    item_link.click()

    wait.until(EC.title_contains(re.sub(" +", " ", item["name"])))

    item_url = driver.current_url

    fail_count = 0
    for item_func in item_func_list:
        while True:
            try:
                item_func(driver, wait, profile, mode, item)
                break
            except TimeoutException:
                fail_count += 1

                if fail_count > RETRY_COUNT:
                    raise

                logging.warning("タイムアウトしたので，リトライします．")

                if driver.current_url != item_url:
                    driver.back()
                    time.sleep(1)
                if driver.current_url != item_url:
                    driver.get(item_url)
                random_sleep(5)


def iter_items_on_display(driver, wait, profile, mode, item_func_list):
    click_xpath(
        driver,
        '//button[@data-testid="account-button"]',
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
        execute_item(driver, wait, profile, mode, i, item_func_list)

        if mode["debug"]:
            break

        random_sleep(10)
        driver.get(list_url)
        wait.until(EC.presence_of_element_located((By.XPATH, ITEM_XPATH)))


def login_impl(config, driver, wait, profile):
    logging.info("ログインを行います．")
    driver.get(LOGIN_URL)

    wait.until(EC.presence_of_element_located((By.XPATH, '//div[@class="merNavigationTopMenu"]')))
    time.sleep(1)

    click_xpath(driver, '//button[contains(text(), "はじめる")]')
    time.sleep(1)

    account_button = driver.find_elements(
        By.XPATH,
        '//button[@data-testid="account-button"]',
    )

    if len(account_button) != 0:
        logging.info("既にログイン済みでした．")
        return

    click_xpath(
        driver,
        '//button[contains(text(), "ログイン")]',
        wait,
    )

    wait.until(EC.presence_of_element_located((By.XPATH, '//h1[contains(text(), "ログイン")]')))

    driver.find_element(By.XPATH, '//input[@name="emailOrPhone"]').send_keys(profile["user"])
    driver.find_element(By.XPATH, '//input[@name="password"]').send_keys(profile["pass"])

    click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    time.sleep(2)
    if len(driver.find_elements(By.XPATH, '//div[@id="recaptchaV2"]')) != 0:
        logging.warning("画像認証が要求されました．")
        captcha.resolve_mp3(driver, wait)
        logging.warning("画像認証を突破しました．")
        click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(EC.presence_of_element_located((By.XPATH, '//h1[contains(text(), "電話番号の確認")]')))

    logging.info("認証番号の対応を行います．")
    if "slack" in config:
        ts = captcha_slack.send_request(
            config["slack"]["bot_token"],
            config["slack"]["captcha"]["channel"]["id"],
            "CAPTCHA",
            "SMS で送られてきた認証番号を入力してください",
        )

        code = captcha_slack.recv_response(
            config["slack"]["bot_token"], config["slack"]["captcha"]["channel"]["id"], "text", ts
        )
    else:
        code = input("SMS で送られてきた認証番号を入力してください: ")

    driver.find_element(By.XPATH, '//input[@name="code"]').send_keys(code)
    click_xpath(driver, '//button[contains(text(), "認証して完了する")]', wait)

    wait.until(EC.presence_of_all_elements_located)
    time.sleep(5)

    driver.get(LOGIN_URL)

    time.sleep(1)
    wait.until(EC.presence_of_element_located((By.XPATH, '//div[@class="merNavigationTopMenu"]')))

    wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                '//button[@data-testid="account-button"]',
            )
        )
    )
    logging.info("ログインに成功しました．")


def login(config, driver, wait, profile):
    try:
        login_impl(config, driver, wait, profile)
    except:
        logging.error(traceback.format_exc())
        dump_page(driver, int(random.random() * 100))
        # NOTE: 1回だけリトライする
        logging.error("ログインをリトライします．")
        time.sleep(10)
        login_impl(config, driver, wait, profile)
        pass


def warmup(driver):
    logging.info("ウォームアップを行います．")

    # NOTE: 自動処理の最初の方にエラーが発生することが多いので，事前にアクセスしておく
    driver.get(LOGIN_URL)
    time.sleep(3)
    driver.refresh()
    time.sleep(3)
