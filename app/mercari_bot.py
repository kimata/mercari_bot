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

import logger
import mercari_price_down
import notify_mail
import notify_slack
from config import load_config

args = docopt(__doc__)

config_file = args["-c"]
notify_log = args["-l"]
mode = {"debug": args["-d"]}

log_str_io = logger.init("bot.mercari.inventory", level=logging.INFO, is_str_log=True)

logging.info("Start.")

config = load_config()

ret_code = 0
for profile in config["profile"]:
    ret_code += mercari_price_down.execute(config, profile, mode)

if notify_log:
    if "mail" in config:
        notify_mail.send(config, "<br />".join(log_str_io.getvalue().splitlines()), is_log_message=False)
    if "slack" in config:
        notify_slack.info(
            config["slack"]["bot_token"],
            config["slack"]["info"]["channel"]["name"],
            "Mercari price change",
            log_str_io.getvalue(),
        )


logging.info("Finish.")

sys.exit(ret_code)
