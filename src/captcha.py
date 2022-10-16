#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from selenium_util import click_xpath, is_display
import notifier


def resolve_img(driver, wait, config):
    wait.until(
        EC.frame_to_be_available_and_switch_to_it(
            (By.XPATH, '//iframe[@title="reCAPTCHA"]')
        )
    )
    click_xpath(
        driver,
        '//span[contains(@class, "recaptcha-checkbox")]',
        move=True,
    )
    driver.switch_to.default_content()
    wait.until(
        EC.frame_to_be_available_and_switch_to_it(
            (By.XPATH, '//iframe[contains(@title, "reCAPTCHA による確認")]')
        )
    )
    wait.until(
        EC.element_to_be_clickable((By.XPATH, '//div[@id="rc-imageselect-target"]'))
    )
    while True:
        # NOTE: 問題画像を切り抜いてメールで送信
        notifier.send(
            config,
            "reCAPTCHA",
            png_data=driver.find_element(By.XPATH, "//body").screenshot_as_png,
            is_force=True,
        )
        tile_list = driver.find_elements(
            By.XPATH,
            '//table[contains(@class, "rc-imageselect-table")]//td[@role="button"]',
        )
        tile_idx_list = list(
            map(lambda elem: elem.get_attribute("tabindex"), tile_list)
        )

        # NOTE: メールを見て人間に選択するべき画像のインデックスを入力してもらう．
        # インデックスは左上を 0 として横方向に 1, 2, ... とする形．
        # 入力を簡単にするため，10以上は a, b, ..., g で指定．
        # 0 は入力の完了を意味する．
        select_str = input("選択タイル(1-9,a-g,end=0): ").strip()

        if select_str == "0":
            if click_xpath(
                driver, '//button[contains(text(), "スキップ")]', move=True, is_warn=False
            ):
                time.sleep(1)
                continue
            elif click_xpath(
                driver, '//button[contains(text(), "確認")]', move=True, is_warn=False
            ):
                time.sleep(1)

                if is_display(
                    driver, '//div[contains(text(), "新しい画像も")]'
                ) or is_display(driver, '//div[contains(text(), "もう一度")]'):
                    continue
                else:
                    break
            else:
                click_xpath(
                    driver, '//button[contains(text(), "次へ")]', move=True, is_warn=False
                )
                time.sleep(1)
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
        time.sleep(1)

    driver.switch_to.default_content()
