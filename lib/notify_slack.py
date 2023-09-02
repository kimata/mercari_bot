#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import pathlib
import tempfile
import threading

import footprint
import slack_sdk

# NOTE: テスト用
notify_hist = []

ERROR_NOTIFY_FOOTPRINT = pathlib.Path(os.path.dirname(__file__)).parent / "data" / "error_notify"

SIMPLE_TMPL = """\
[
    {{
        "type": "header",
    "text": {{
            "type": "plain_text",
        "text": "{title}",
            "emoji": true
        }}
    }},
    {{
        "type": "section",
        "text": {{
            "type": "mrkdwn",
        "text": {message}
    }}
    }}
]
"""
interval_check_lock = threading.Lock()


def format_simple(title, message):
    return {
        "text": message,
        "json": json.loads(SIMPLE_TMPL.format(title=title, message=json.dumps(message))),
    }


def send(token, ch_name, message):
    try:
        client = slack_sdk.WebClient(token=token)
        client.chat_postMessage(
            channel=ch_name,
            text=message["text"],
            blocks=message["json"],
        )
    except slack_sdk.errors.SlackClientError as e:
        logging.warning(e)


def split_send(token, ch_name, title, message, formatter=format_simple):
    LINE_SPLIT = 20

    logging.info("Post slack channel: {ch_name}".format(ch_name=ch_name))

    message_lines = message.splitlines()
    for i in range(0, len(message_lines), LINE_SPLIT):
        send(
            token,
            ch_name,
            formatter(title, "\n".join(message_lines[i : i + LINE_SPLIT])),
        )


def info(token, ch_name, name, message, formatter=format_simple):
    title = "Info: " + name
    split_send(token, ch_name, title, message, formatter)


def interval_check(interval_min):
    return footprint.elapsed(ERROR_NOTIFY_FOOTPRINT) > interval_min * 60


def interval_clear():
    footprint.clear(ERROR_NOTIFY_FOOTPRINT)


def error_img(token, ch_id, title, img, text):
    client = slack_sdk.WebClient(token=token)

    with tempfile.TemporaryDirectory() as dname:
        img_path = os.path.join(dname, "error.png")
        img.save(img_path)

        try:
            client.files_upload_v2(channel=ch_id, file=img_path, title=title, initial_comment=text)
        except slack_sdk.errors.SlackApiError as e:
            logging.warning(e.response["error"])


def error(
    token,
    ch_name,
    name,
    message,
    interval_min=60,
    formatter=format_simple,
):
    title = "Error: " + name

    hist_add(message)

    if not interval_check(interval_min):
        logging.warning("Interval is too short. Skipping.")
        return

    split_send(token, ch_name, title, message, formatter)

    footprint.update(ERROR_NOTIFY_FOOTPRINT)


def error_with_image(
    token,
    ch_name,
    ch_id,
    name,
    message,
    attatch_img,
    interval_min=10,
    formatter=format_simple,
):  # def error_with_image
    title = "Error: " + name

    hist_add(message)

    if not interval_check(interval_min):
        logging.warning("Interval is too short. Skipping.")
        return

    split_send(token, ch_name, title, message, formatter)

    if attatch_img is not None:
        assert ch_id is not None
        error_img(token, ch_id, title, attatch_img["data"], attatch_img["text"])

    footprint.update(ERROR_NOTIFY_FOOTPRINT)


# NOTE: テスト用
def hist_clear():
    global notify_hist

    notify_hist = []


# NOTE: テスト用
def hist_add(message):
    global notify_hist

    notify_hist.append(message)


# NOTE: テスト用
def hist_get():
    global notify_hist

    return notify_hist


if __name__ == "__main__":
    import os
    import sys

    import logger
    import PIL.Image
    from config import load_config

    logger.init("test", level=logging.INFO)
    logging.info("Test")

    # NOTE: Slack の環境に合わせて書き換える
    test_ch_name = "#test"
    test_ch_id = "C058PTZG13L"

    config = load_config()
    if "SLACK" not in config:
        logging.warning("Slack の設定が記載されていません．")
        sys.exit(-1)

    client = slack_sdk.WebClient(token=config["SLACK"]["BOT_TOKEN"])

    img = PIL.Image.open(pathlib.Path(os.path.dirname(__file__), config["WEATHER"]["ICON"]["THERMO"]["PATH"]))
    if "INFO" in config["SLACK"]:
        info(
            config["SLACK"]["BOT_TOKEN"],
            test_ch_name,
            os.path.basename(__file__),
            "メッセージ\nメッセージ",
        )

    if "ERROR" in config["SLACK"]:
        error(
            config["SLACK"]["BOT_TOKEN"],
            test_ch_name,
            os.path.basename(__file__),
            "エラーメッセージ",
            0,
        )

    if "ERROR" in config["SLACK"]:
        error_with_image(
            config["SLACK"]["BOT_TOKEN"],
            test_ch_name,
            test_ch_id,
            os.path.basename(__file__),
            "エラーメッセージ",
            {"data": img, "text": "エラー時のスクリーンショット"},
            0,
        )
