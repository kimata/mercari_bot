#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time
import inspect
import pathlib
import os

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC


def click_xpath(driver, xpath, wait=None, move=False, is_warn=True):
    if wait is not None:
        wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        time.sleep(0.5)

    if len(driver.find_elements(By.XPATH, xpath)) != 0:
        elem = driver.find_element(By.XPATH, xpath)
        action = ActionChains(driver)
        action.move_to_element(elem)
        action.perform()

        elem.click()
        return True
    else:
        if is_warn:
            logging.warning("Element is not found: {xpath}".format(xpath=xpath))
        return False


def is_display(driver, xpath):
    return (len(driver.find_elements(By.XPATH, xpath)) != 0) and (
        driver.find_element(By.XPATH, xpath).is_displayed()
    )


def dump_page(driver, dump_path, index):
    name = inspect.stack()[1].function.replace("<", "").replace(">", "")
    dump_path = pathlib.Path(dump_path)

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
