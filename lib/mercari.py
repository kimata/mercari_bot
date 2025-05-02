#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import pathlib
import random
import re
import time
import traceback

import my_lib.notify.slack
import my_lib.selenium_util
import my_lib.store.captcha
import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.support
import selenium.webdriver.support.ui

RETRY_COUNT = 3
LINE_LOGIN_TIMEOUT = 30

LOGIN_URL = "https://jp.mercari.com"
ITEM_LIST_XPATH = (
    '//div[@data-testid="listed-item-list"]//div[contains(@class, "merListItem")]'
)

DATA_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data"
DUMP_PATH = DATA_PATH / "debug"


def parse_item(driver, index):
    time.sleep(5)
    item_xpath = ITEM_LIST_XPATH + "[" + str(index) + "]"
    item_url_xpath = item_xpath + "//a"
    item_name_xpath = item_xpath + '//span[contains(@class, "itemLabel")]'
    item_price_xpath = (
        item_xpath + '//span[@class="merPrice"]/span[contains(@class, "number")]'
    )

    # item_price_xpath = (
    #     item_xpath
    #     + '//div[@data-testid="price"]/span[contains(@class, "currency")]/following-sibling::span[1]'
    # )

    item_view_xpath = (
        item_xpath
        + '//mer-icon-eye-outline/following-sibling::span[contains(@class, "iconText")]'
    )
    item_private_xpath = item_xpath + '//span[contains(@class, "informationLabel")]'

    item_url = driver.find_element(
        selenium.webdriver.common.by.By.XPATH, item_url_xpath
    ).get_attribute("href")
    item_id = item_url.split("/")[-1]

    name = driver.find_element(
        selenium.webdriver.common.by.By.XPATH, item_name_xpath
    ).text

    if (
        len(
            driver.find_elements(
                selenium.webdriver.common.by.By.XPATH, item_price_xpath
            )
        )
        == 0
    ):
        driver.refresh()
        time.sleep(5)
        return parse_item(driver, index)

    price = int(
        driver.find_element(
            selenium.webdriver.common.by.By.XPATH, item_price_xpath
        ).text.replace(",", "")
    )
    is_stop = 0

    if (
        len(
            driver.find_elements(
                selenium.webdriver.common.by.By.XPATH, item_private_xpath
            )
        )
        != 0
    ):
        is_stop = 1

    try:
        view = int(
            driver.find_element(
                selenium.webdriver.common.by.By.XPATH, item_view_xpath
            ).text
        )
    except:
        view = 0

    return {
        "id": item_id,
        "url": item_url,
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
        selenium.webdriver.common.by.By.XPATH,
        ITEM_LIST_XPATH + "[" + str(index) + "]//a",
    )
    # NOTE: アイテムにスクロールしてから，ヘッダーに隠れないようちょっと前に戻す
    item_link.location_once_scrolled_into_view
    driver.execute_script("window.scrollTo(0, window.pageYOffset - 200);")
    item_link.click()

    wait.until(
        selenium.webdriver.support.expected_conditions.title_contains(
            re.sub(" +", " ", item["name"])
        )
    )

    item_url = driver.current_url

    fail_count = 0
    for item_func in item_func_list:
        while True:
            try:
                item_func(driver, wait, profile, mode, item)
                fail_count = 0
                break
            except selenium.common.exceptions.TimeoutException:
                fail_count += 1

                if fail_count > RETRY_COUNT:
                    raise

                logging.warning("タイムアウトしたので，リトライします．")

                if driver.current_url != item_url:
                    driver.back()
                    time.sleep(1)
                if driver.current_url != item_url:
                    driver.get(item_url)
                my_lib.selenium_util.random_sleep(5)

        time.sleep(10)


def expand_all(driver, wait):
    MORE_BUTTON_XPATH = (
        '//div[contains(@class, "merButton")]/button[contains(text(), "もっと見る")]'
    )

    while (
        len(
            driver.find_elements(
                selenium.webdriver.common.by.By.XPATH, MORE_BUTTON_XPATH
            )
        )
        != 0
    ):
        my_lib.selenium_util.click_xpath(driver, MORE_BUTTON_XPATH, wait)

        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_all_elements_located
        )
        time.sleep(2)


def iter_items_on_display(driver, wait, profile, mode, item_func_list):
    my_lib.selenium_util.click_xpath(
        driver,
        '//button[@data-testid="account-button"]',
        wait,
    )
    my_lib.selenium_util.click_xpath(driver, '//a[contains(text(), "出品した商品")]', wait)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                ITEM_LIST_XPATH,
            )
        )
    )

    time.sleep(1)

    expand_all(driver, wait)

    item_count = len(
        driver.find_elements(
            selenium.webdriver.common.by.By.XPATH,
            ITEM_LIST_XPATH,
        )
    )

    logging.info("{item_count}個の出品があります．".format(item_count=item_count))

    list_url = driver.current_url
    for i in range(1, item_count + 1):
        execute_item(driver, wait, profile, mode, i, item_func_list)

        if mode["debug"]:
            break

        my_lib.selenium_util.random_sleep(10)
        driver.get(list_url)
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (selenium.webdriver.common.by.By.XPATH, ITEM_LIST_XPATH)
            )
        )

        expand_all(driver, wait)


def login_via_line(config, driver, wait, profile):
    my_lib.selenium_util.click_xpath(
        driver, '//button[span[contains(text(), "LINEでログイン")]]', wait
    )

    wait.until(
        selenium.webdriver.support.expected_conditions.title_contains("LINE Login")
    )

    if my_lib.selenium_util.xpath_exists(driver, '//input[@name="tid"]'):
        my_lib.selenium_util.input_xpath(
            driver, '//input[@name="tid"]', profile["line"]["user"]
        )
        my_lib.selenium_util.input_xpath(
            driver, '//input[@name="tpasswd"]', profile["line"]["pass"]
        )
        my_lib.selenium_util.click_xpath(
            driver, '//button[contains(text(), "ログイン")]', wait
        )
    else:
        my_lib.selenium_util.click_xpath(
            driver, '//button[.//span[normalize-space()="ログイン"]]', wait
        )

    time.sleep(1)

    if "LINE Login" in driver.title:
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_all_elements_located
        )
        code = driver.find_element(
            selenium.webdriver.common.by.By.XPATH, '//p[contains(@class, "Number")]'
        ).text

        my_lib.notify.slack.info(
            config["slack"]["bot_token"],
            config["slack"]["captcha"]["channel"]["name"],
            "LINE ログイン",
            f"LINE アプリで認証番号「{code}」を入力してください。",
        )
        logging.warning("LINE アプリで認証番号「%s」を入力してください。", code)

        login_wait = selenium.webdriver.support.ui.WebDriverWait(
            driver, LINE_LOGIN_TIMEOUT
        )
        login_wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (
                    selenium.webdriver.common.by.By.XPATH,
                    '//h1[contains(text(), "電話番号の確認")]',
                )
            )
        )


def login_impl(config, driver, wait, profile):
    logging.info("ログインを行います．")
    driver.get(LOGIN_URL)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//div[@class="merNavigationTopMenu"]',
            )
        )
    )
    time.sleep(1)

    my_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "はじめる")]')
    time.sleep(1)

    account_button = driver.find_elements(
        selenium.webdriver.common.by.By.XPATH,
        '//button[@data-testid="account-button"]',
    )

    if len(account_button) != 0:
        logging.info("既にログイン済みでした．")
        return

    my_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (selenium.webdriver.common.by.By.XPATH, '//h1[contains(text(), "ログイン")]')
        )
    )

    login_via_line(config, driver, wait, profile)

    # time.sleep(2)
    # if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, '//div[@id="recaptchaV2"]')) != 0:
    #     logging.warning("画像認証が要求されました．")
    #     captcha.resolve_mp3(driver, wait)
    #     logging.warning("画像認証を突破しました．")
    #     click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (selenium.webdriver.common.by.By.XPATH, '//h1[contains(text(), "電話番号の確認")]')
        )
    )

    logging.info("認証番号の対応を行います．")

    if "slack" in config:
        ts = my_lib.store.captcha.send_request_text_slack(
            config["slack"]["bot_token"],
            config["slack"]["captcha"]["channel"]["name"],
            "CAPTCHA",
            "SMS で送られてきた認証番号を入力してください",
        )
        code = my_lib.store.captcha.recv_response_text_slack(
            config["slack"]["bot_token"],
            config["slack"]["captcha"]["channel"]["id"],
            ts,
        )
    else:
        code = input("SMS で送られてきた認証番号を入力してください: ")

    driver.find_element(
        selenium.webdriver.common.by.By.XPATH, '//input[@name="code"]'
    ).send_keys(code)
    my_lib.selenium_util.click_xpath(
        driver, '//button[contains(text(), "認証して完了する")]', wait
    )

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_all_elements_located
    )
    time.sleep(5)

    driver.get(LOGIN_URL)

    time.sleep(1)
    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//div[@class="merNavigationTopMenu"]',
            )
        )
    )

    wait.until(
        selenium.webdriver.support.expected_conditions.element_to_be_clickable(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//button[@data-testid="account-button"]',
            )
        )
    )
    logging.info("ログインに成功しました．")
    my_lib.selenium_util.dump_page(driver, int(random.random() * 100), DUMP_PATH)


def login(config, driver, wait, profile):
    try:
        login_impl(config, driver, wait, profile)
    except:
        logging.error(traceback.format_exc())
        my_lib.selenium_util.dump_page(driver, int(random.random() * 100), DUMP_PATH)
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
