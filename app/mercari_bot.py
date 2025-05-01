#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
メルカリに出品中のアイテムの価格を自動的に値下げします．

Usage:
  mercari_bot.py [-c CONFIG] [-l] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します． [default: config.yaml]
  -l                : 動作ログを Slack やメールで通知します．
  -d                : デバッグモードで動作します．(価格変更は行いません)
"""

import logging
import pathlib
import sys

from docopt import docopt

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import os

import mercari_price_down
import my_lib.config
import my_lib.logger
import my_lib.notify.mail
import my_lib.notify.slack

DATA_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data"


args = docopt(__doc__)

config_file = args["-c"]
notify_log = args["-l"]
mode = {"debug": args["-d"]}

log_str_io = my_lib.logger.init(
    "bot.mercari.inventory", level=logging.INFO, is_str_log=True
)

logging.info("Start.")

config = my_lib.config.load()

ret_code = 0
for profile in config["profile"]:
    ret_code += mercari_price_down.execute(config, profile, DATA_PATH, mode)

if notify_log:
    if "mail" in config:
        my_lib.notify.mail.send(
            config, "<br />".join(log_str_io.getvalue().splitlines())
        )
    if "slack" in config:
        my_lib.notify.slack.info(
            config["slack"]["bot_token"],
            config["slack"]["info"]["channel"]["name"],
            "Mercari price change",
            log_str_io.getvalue(),
        )


logging.info("Finish.")

sys.exit(ret_code)
