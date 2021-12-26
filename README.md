# mercari_bot

メルカリに出品中のアイテムの価格を値下げするスクリプトです．
下記が設定可能です．

- 値下げする幅
- 値下げを停止する価格

## 準備

必要なモジュールをインストールします．

```
sudo apt install python3-selenium
sudo apt install python3-coloredlogs
pip3 install chromedriver-binary==95.0.4638.69.0
```

`chromedriver-binary` のバージョンをしているのは，
現時点('21/12/26)だと最新バージョンにバグがあるためです．

## 実行方法

`./mercari_bot.py`

# ライセンス

Apache License Version 2.0 を適用します．
