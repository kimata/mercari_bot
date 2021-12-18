#!/usr/bin/env python3
# - coding: utf-8 --
import chromedriver_binary

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
import click
import time
import os
import sys
import random

import yaml
import pprint
import pathlib


LOGIN_URL = 'https://jp.mercari.com'
CONFIG_PATH = 'config.yml'
CHROME_DATA_PATH = 'chrome_data'
PRICE_DOWN_STEP = 100
PRICE_THRESHOLD = 3000


def get_abs_path(path):
    return str(pathlib.Path(os.path.dirname(__file__), path))


def error(message):
    click.secho('ERROR: ', fg='red', bold=True, nl=False)
    click.secho(message)
    sys.exit(-1)


def info(message):
    click.secho('INFO: ', fg='white', bold=True, nl=False)
    click.secho(message)


def load_config():
    with open(get_abs_path(CONFIG_PATH)) as file:
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

    wait.until(EC.presence_of_element_located(By.XPATH, '//mer-text[contains(text(), "Mercari")]'))
    wait.until(lambda x:
               x.find_elements_by_xpath('//mer-text[contains(text(), "ログイン")]') or
               x.find_elements_by_xpath('//mer-text[contains(text(), "アカウント")]') or
               x.find_elements_by_xpath('//button[contains(text(), "はじめる")]'))

    if len(driver.find_elements_by_xpath('//button[contains(text(), "はじめる")]')) != 0:
        click_xpath(driver, '//button[contains(text(), "はじめる")]')

    # NOTE: 「アカウント」がある場合は，ログイン済み
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
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36"')
    options.add_argument('--user-data-dir=' + get_abs_path(CHROME_DATA_PATH))

    driver = webdriver.Chrome(options=options)

    return driver


def iter_items_on_display(driver, wait, item_func):
    click_xpath(driver, '//mer-text[contains(text(), "アカウント")]')
    click_xpath(driver, '//a[contains(text(), "出品した商品")]', wait)

    wait.until(EC.presence_of_element_located((By.XPATH, '//mer-list[@data-testid="listed-item-list"]/mer-list-item')))

    item_count = len(driver.find_elements_by_xpath('//mer-list[@data-testid="listed-item-list"]/mer-list-item'))

    info('{}個の出品があります'.format(item_count))

    list_url = driver.current_url
    for i in range(1, item_count):
        item_root = expand_shadow_element(
            driver,
            driver.find_element_by_xpath('//mer-list[@data-testid="listed-item-list"]/mer-list-item[' + str(i) + ']//mer-item-object'))


        name = item_root.find_element_by_css_selector('div.container').get_attribute('aria-label')
        price = int(item_root.find_element_by_css_selector('mer-price').get_attribute('value'))

        click.secho('* ', fg='green', bold=True, nl=False)
        click.secho(name)

        driver.find_element_by_xpath('//mer-list[@data-testid="listed-item-list"]/mer-list-item[' + str(i) + ']//a').click()
        wait.until(EC.title_contains(name))
        item_func(driver, wait, name, price)

        time.sleep(4 + (6*random.random()))
        driver.get(list_url)
        wait.until(EC.presence_of_element_located((By.XPATH, '//mer-list[@data-testid="listed-item-list"]/mer-list-item')))

    info('完了')


def item_price_down(driver, wait, name, price):
    if (price < PRICE_THRESHOLD):
        print('  現在価格が{:,}円のため，スキップします．'.format(price))
        return

    click_xpath(driver, '//mer-button[@data-testid="checkout-button"]')
    wait.until(EC.title_contains('商品の情報を編集'))
    wait.until(EC.presence_of_element_located((By.XPATH, '//input[@name="price"]')))

    cur_price = int(driver.find_element_by_xpath('//input[@name="price"]').get_attribute('value'))
    if (cur_price != price):
        error('ページ遷移中に価格が変更されました．')

    new_price = int((price - PRICE_DOWN_STEP) / 10) * 10 # 10円単位に丸める
    driver.find_element_by_xpath('//input[@name="price"]').send_keys(Keys.CONTROL + 'a')
    driver.find_element_by_xpath('//input[@name="price"]').send_keys(Keys.BACK_SPACE)
    driver.find_element_by_xpath('//input[@name="price"]').send_keys(new_price)
    click_xpath(driver, '//button[contains(text(), "変更する")]')

    wait.until(EC.title_contains(name))

    driver.save_screenshot('test1.png')
    wait.until(EC.presence_of_element_located((By.XPATH, '//mer-price')))

    cur_price = int(driver.find_element_by_xpath('//mer-price').get_attribute('value'))

    if (cur_price != new_price):
        error('編集後の価格が意図したものと異なっています．')

    print('  {:,}円 -> {:,}円'.format(price, cur_price))


# NOTE: 端末から実行していない場合は，動き始める前にランダムな時間待つ
if not sys.stdin.isatty():
    time.sleep(600*random.random())

config = load_config()
driver = create_driver()

wait = WebDriverWait(driver, 5)
login(driver, wait, config)

iter_items_on_display(driver, wait, item_price_down)

driver.quit()

sys.exit(0)
