# mercari_bot

メルカリに出品中のアイテムの価格を値下げするスクリプトです。
下記が設定可能です。

-   値下げする幅
-   値下げを停止する価格

## 準備

Docker を動かせる必要があります。お使いの環境に合わせてインストールしてください。

## 設定

ログイン情報や値下げ内容を `config.yaml` で指定します。

`config.example.yaml` を名前変更して設定してください。
設定方法方はファイルを見ていただけばわかると思います。

## 実行方法

```bash:bash
docker build -t mercari-bot .
docker run --rm -it mercari-bot
```

# ライセンス

Apache License Version 2.0 を適用します．
