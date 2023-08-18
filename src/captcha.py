#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import tempfile
import urllib

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

from speech_recognition import Recognizer, AudioFile
import pydub

from selenium_util import click_xpath, is_display
import notify_mail

import pathlib
import os

DATA_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data"
LOG_PATH = DATA_PATH / "log"

CHROME_DATA_PATH = str(DATA_PATH / "chrome")
RECORD_PATH = str(DATA_PATH / "record")
DUMP_PATH = str(DATA_PATH / "debug")


def recog_audio(audio_url):
    mp3_file = tempfile.NamedTemporaryFile(mode="wb", delete=False)
    wav_file = tempfile.NamedTemporaryFile(mode="wb", delete=False)

    try:
        urllib.request.urlretrieve(audio_url, mp3_file.name)

        pydub.AudioSegment.from_mp3(mp3_file.name).export(wav_file.name, format="wav")

        recognizer = Recognizer()
        recaptcha_audio = AudioFile(wav_file.name)
        with recaptcha_audio as source:
            audio = recognizer.record(source)

        return recognizer.recognize_google(audio, language="en-US")
    except:
        raise
    finally:
        os.unlink(mp3_file.name)
        os.unlink(wav_file.name)


def resolve_mp3(driver, wait, config):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[@title="reCAPTCHA"]')))
    click_xpath(
        driver,
        '//span[contains(@class, "recaptcha-checkbox")]',
        move=True,
    )
    driver.switch_to.default_content()
    wait.until(
        EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[contains(@title, "reCAPTCHA による確認")]'))
    )
    wait.until(EC.element_to_be_clickable((By.XPATH, '//div[@id="rc-imageselect-target"]')))
    click_xpath(driver, '//button[contains(@title, "確認用の文字を音声")]', move=True)
    time.sleep(0.5)

    audio_url = driver.find_element(By.XPATH, '//audio[@id="audio-source"]').get_attribute("src")

    text = recog_audio(audio_url)

    input_elem = driver.find_element(By.XPATH, '//input[@id="audio-response"]')
    input_elem.send_keys(text.lower())
    input_elem.send_keys(Keys.ENTER)

    driver.switch_to.default_content()


def resolve_img(driver, wait, config):
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[@title="reCAPTCHA"]')))
    click_xpath(
        driver,
        '//span[contains(@class, "recaptcha-checkbox")]',
        move=True,
    )
    driver.switch_to.default_content()
    wait.until(
        EC.frame_to_be_available_and_switch_to_it((By.XPATH, '//iframe[contains(@title, "reCAPTCHA による確認")]'))
    )
    wait.until(EC.element_to_be_clickable((By.XPATH, '//div[@id="rc-imageselect-target"]')))
    while True:
        # NOTE: 問題画像を切り抜いてメールで送信
        notify_mail.send(
            config,
            "reCAPTCHA",
            png_data=driver.find_element(By.XPATH, "//body").screenshot_as_png,
            is_force=True,
        )
        tile_list = driver.find_elements(
            By.XPATH,
            '//table[contains(@class, "rc-imageselect-table")]//td[@role="button"]',
        )
        tile_idx_list = list(map(lambda elem: elem.get_attribute("tabindex"), tile_list))

        # NOTE: メールを見て人間に選択するべき画像のインデックスを入力してもらう．
        # インデックスは左上を 0 として横方向に 1, 2, ... とする形．
        # 入力を簡単にするため，10以上は a, b, ..., g で指定．
        # 0 は入力の完了を意味する．
        select_str = input("選択タイル(1-9,a-g,end=0): ").strip()

        if select_str == "0":
            if click_xpath(driver, '//button[contains(text(), "スキップ")]', move=True, is_warn=False):
                time.sleep(0.5)
                continue
            elif click_xpath(driver, '//button[contains(text(), "確認")]', move=True, is_warn=False):
                time.sleep(0.5)

                if is_display(driver, '//div[contains(text(), "新しい画像も")]') or is_display(
                    driver, '//div[contains(text(), "もう一度")]'
                ):
                    continue
                else:
                    break
            else:
                click_xpath(driver, '//button[contains(text(), "次へ")]', move=True, is_warn=False)
                time.sleep(0.5)
                continue

        for idx in list(select_str):
            if ord(idx) <= 57:
                idx = ord(idx) - 48
            else:
                idx = ord(idx) - 97 + 10
            if idx >= len(tile_idx_list):
                continue

            click_xpath(
                driver,
                '//table[contains(@class, "rc-imageselect-table")]//td[@tabindex="{index}"]'.format(
                    index=tile_idx_list[idx - 1]
                ),
                move=True,
            )
        time.sleep(0.5)

    driver.switch_to.default_content()
