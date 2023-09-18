#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
画像 CAPTCHA や SMS 認証を Slack のやり取りで解決します．

Usage:
  captch_slack.py [-c CONFIG]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
"""

import logging
import os
import tempfile
import time

import notify_slack
import slack_sdk

WAIT_SEC = 5


def send_request(token, ch_id, title, message):
    logging.info("CAPTCHA: send request [text]")

    try:
        resp = notify_slack.send(token, ch_id, notify_slack.format_simple(title, message))

        return resp["ts"]
    except slack_sdk.errors.SlackApiError as e:
        logging.warning(e.response["error"])
        return None


def send_challenge_image(token, ch_id, title, img, text):
    logging.info("CAPTCHA: send challenge [image]")

    try:
        client = slack_sdk.WebClient(token=token)

        with tempfile.TemporaryDirectory() as dname:
            img_path = os.path.join(dname, "error.png")
            img.save(img_path)

            resp = client.files_upload_v2(channel=ch_id, file=img_path, title=title, initial_comment=text)

            return resp["files"][0]["id"]
    except slack_sdk.errors.SlackApiError as e:
        logging.warning(e.response["error"])
        return None


def recv_response_image(token, ch_id, file_id, timeout_sec):
    logging.info("CAPTCHA: receive response [image]")

    time.sleep(WAIT_SEC)
    try:
        client = slack_sdk.WebClient(token=token)

        count = 0
        thread_ts = None
        while True:
            resp = client.conversations_history(channel=ch_id, limit=3)

            for message in resp["messages"]:
                if (
                    ("thread_ts" in message)
                    and ("files" in message)
                    and (message["files"][0]["id"] == file_id)
                ):
                    thread_ts = message["thread_ts"]
                    break
            else:
                count += 1
                if count > (timeout_sec / WAIT_SEC):
                    return None
                time.sleep(WAIT_SEC)
                continue
            break

        if thread_ts is None:
            return None

        resp = client.conversations_replies(channel=ch_id, ts=thread_ts)

        return resp["messages"][-1]["text"].strip()
    except slack_sdk.errors.SlackApiError as e:
        logging.warning(e.response["error"])


def recv_response_text(token, ch_id, ts, timeout_sec):
    logging.info("CAPTCHA: receive response [text]")

    time.sleep(WAIT_SEC)
    try:
        client = slack_sdk.WebClient(token=token)

        count = 0
        thread_ts = None
        while True:
            resp = client.conversations_history(channel=ch_id, limit=3)

            for message in resp["messages"]:
                if ("thread_ts" in message) and (message["ts"] == ts):
                    thread_ts = message["thread_ts"]
                    break
            else:
                count += 1
                if count > (timeout_sec / WAIT_SEC):
                    return None
                time.sleep(WAIT_SEC)
                continue
            break

        if thread_ts is None:
            return None

        resp = client.conversations_replies(channel=ch_id, ts=thread_ts)

        return resp["messages"][-1]["text"].strip()
    except slack_sdk.errors.SlackApiError as e:
        logging.warning(e.response["error"])


def recv_response(token, ch_id, mode, target_id, timeout_sec=300):
    if mode == "image":
        return recv_response_image(token, ch_id, target_id, timeout_sec)
    else:
        return recv_response_text(token, ch_id, target_id, timeout_sec)


if __name__ == "__main__":
    import logger
    import PIL.Image
    from config import load_config
    from docopt import docopt

    args = docopt(__doc__)

    logger.init("test", level=logging.INFO)

    config = load_config(args["-c"])

    img = PIL.Image.open("dummy_captcha.png")

    file_id = send_challenge_image(
        config["slack"]["bot_token"],
        config["slack"]["captcha"]["channel"]["id"],
        "Amazon Login",
        img,
        "画像 CAPTCHA",
    )

    captcha = recv_response(
        config["slack"]["bot_token"], config["slack"]["captcha"]["channel"]["id"], "image", file_id
    )
    logging.info("CAPTCHA is '{captcha}'".format(captcha=captcha))

    ts = send_request(
        config["slack"]["bot_token"],
        config["slack"]["captcha"]["channel"]["id"],
        "CAPTCHA",
        "SMS で送られてきた数字を入力してください",
    )

    captcha = recv_response(
        config["slack"]["bot_token"], config["slack"]["captcha"]["channel"]["id"], "text", ts
    )

    logging.info("CAPTCHA is '{captcha}'".format(captcha=captcha))
