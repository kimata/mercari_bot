#!/usr/bin/env python3
# - coding: utf-8 --
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import pickle

import yaml
import pprint

LOGIN_URL = 'https://jp.mercari.com'
CONFIG_PATH = 'config.yml'
CHROME_DATA_PATH = 'chrome_data'


def load_config():
    with open(CONFIG_PATH) as file:
        return yaml.safe_load(file)


def click_xpath(driver, xpath, wait=None):
    if wait is not None:
        wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.find_element_by_xpath(xpath).click()


def expand_shadow_element(driver, element):
    shadow_root = driver.execute_script('return arguments[0].shadowRoot', element)
    return shadow_root
    
    
def login(driver, wait, config):
    driver.get(LOGIN_URL)
    
    wait.until(lambda x:
               x.find_elements_by_xpath('//mer-text[contains(text(), "お知らせ")]') or
               x.find_elements_by_xpath('//button[contains(text(), "はじめる")]'))


    if len(driver.find_elements_by_xpath('//button[contains(text(), "はじめる")]')) != 0:
        click_xpath(driver, '//button[contains(text(), "はじめる")]')

    if len(driver.find_elements_by_xpath('//mer-text[contains(text(), "アカウント")]')) != 0:
        return

    click_xpath(driver, '//mer-text[contains(text(), "ログイン")]', wait)
    click_xpath(driver, '//span[contains(text(), "メールアドレスでログイン")]', wait)

    wait.until(EC.presence_of_element_located((By.XPATH, '//mer-heading[@title-label="ログイン"]')))

    driver.find_element_by_xpath('//input[@name="email"]').send_keys(config['user'])
    driver.find_element_by_xpath('//input[@name="password"]').send_keys(config['pass'])
    click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(EC.presence_of_element_located((By.XPATH, '//mer-heading[@title-label="電話番号の確認"]')))

    code = input('認証番号: ')
    driver.find_element_by_xpath('//input[@name="code"]').send_keys(code)
    click_xpath(driver, '//button[contains(text(), "認証して完了する")]', wait)

    wait.until(EC.element_to_be_clickable((By.XPATH, '//mer-text[contains(text(), "アカウント")]')))


def create_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--lang=ja-JP')
    options.add_argument('--window-size=1920,1024')
    options.add_argument('--user-data-dir=' + CHROME_DATA_PATH)

    driver = webdriver.Chrome(options=options)

    return driver


def items_on_display(driver, wait):
    click_xpath(driver, '//mer-text[contains(text(), "アカウント")]')
    click_xpath(driver, '//a[contains(text(), "出品した商品")]', wait)
    wait.until(EC.title_contains('出品した商品'))

    item_count = len(driver.find_elements_by_xpath('//mer-list[@data-testid="listed-item-list"]/mer-list-item'))

    print(item_count)

    for i in range(1, item_count):
        item_root = expand_shadow_element(
            driver,
            driver.find_element_by_xpath('//mer-list[@data-testid="listed-item-list"]/mer-list-item[' + str(i) + ']//mer-item-object'))
        
        pprint.pprint(item_root.find_element_by_css_selector('div.container').get_attribute('aria-label'))
        pprint.pprint(item_root.find_element_by_css_selector('mer-price').get_attribute('value'))
    
    # pprint.pprint(item_count)


config = load_config()
driver = create_driver()

wait = WebDriverWait(driver, 5)
login(driver, wait, config)

items_on_display(driver, wait)

driver.quit()
