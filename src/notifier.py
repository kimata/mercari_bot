#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import smtplib
import pathlib
from email.mime.text import MIMEText
import logging

INTERVAL_MIN = 60 * 8

STAT_DIR_PATH = pathlib.Path("/dev/shm")
STAT_PATH_NOTIFY = STAT_DIR_PATH / "notify_mail"


def send_impl(config, message):
    smtp = smtplib.SMTP("smtp.gmail.com", 587)
    smtp.starttls()
    smtp.login(config["mail"]["user"], config["mail"]["pass"])

    msg = MIMEText(message, "html")
    msg["Subject"] = config["mail"]["subject"]
    msg["To"] = config["mail"]["to"]
    msg["From"] = config["mail"]["from"]

    smtp.send_message(msg)

    logging.info("sendmail")

    smtp.quit()


def send(config, message, is_log_message=True):
    if is_log_message:
        logging.info("notify: {message}".format(message=message))

    if (
        STAT_PATH_NOTIFY.exists()
        and ((time.time() - STAT_PATH_NOTIFY.stat().st_mtime) / 60) < INTERVAL_MIN
    ):
        return
    send_impl(config, message)

    STAT_PATH_NOTIFY.touch()


if __name__ == "__main__":
    from config import load_config

    config = load_config()

    send(config, "Testです")
