#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from selenium_util import click_xpath, dump_page
import captcha
import random

LOGIN_URL = "https://jp.mercari.com"


def login_impl(config, driver, wait, profile):
    logging.info("ログインを行います．")
    driver.get(LOGIN_URL)

    wait.until(EC.presence_of_element_located((By.XPATH, '//div[@class="merNavigationTopMenuItem"]')))

    time.sleep(1)

    click_xpath(driver, '//button[contains(text(), "はじめる")]')

    time.sleep(1)

    menu_label = driver.find_elements(
        By.XPATH,
        '//div[@class="merNavigationTopMenuItem"]//button[contains(text(), "アカウント")]',
    )

    if len(menu_label) != 0:
        logging.info("既にログイン済みでした．")
        return

    click_xpath(
        driver,
        '//div[@class="merNavigationTopMenuItem"]//button[contains(text(), "ログイン")]',
        wait,
    )
    logging.info("メール・電話番号でログインします．")
    click_xpath(driver, '//span[contains(text(), "メール・電話番号でログイン")]', wait)

    wait.until(EC.presence_of_element_located((By.XPATH, '//mer-heading[@title-label="ログイン"]')))

    driver.find_element(By.XPATH, '//input[@name="emailOrPhone"]').send_keys(profile["user"])
    driver.find_element(By.XPATH, '//input[@name="password"]').send_keys(profile["pass"])

    click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    time.sleep(2)
    if len(driver.find_elements(By.XPATH, '//div[@id="recaptchaV2"]')) != 0:
        logging.warning("画像認証が要求されました．")
        captcha.resolve_mp3(driver, wait, config)
        logging.warning("画像認証を突破しました．")
        click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(EC.presence_of_element_located((By.XPATH, '//mer-heading[@title-label="電話番号の確認"]')))

    logging.info("認証番号の入力を待ちます．")
    code = input("認証番号: ")
    driver.find_element(By.XPATH, '//input[@name="code"]').send_keys(code)
    click_xpath(driver, '//button[contains(text(), "認証して完了する")]', wait)

    wait.until(EC.presence_of_all_elements_located)
    time.sleep(5)

    driver.get(LOGIN_URL)

    wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                '//div[@class="merNavigationTopMenuItem"]//button[contains(text(), "アカウント")]',
            )
        )
    )
    logging.info("ログインに成功しました．")


def login(config, driver, wait, profile):
    try:
        login_impl(config, driver, wait, profile)
    except:
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
