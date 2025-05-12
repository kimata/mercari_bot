# mercari_bot

メルカリに出品中のアイテムの価格を値下げするスクリプトです。
下記が設定可能です。

-   値下げする幅
-   値下げを停止する価格


## 動作環境

基本的には，Python と Selenium が動作する環境であれば動作します。
下記の環境での動作を確認しています。

- Linux (Ubuntu 24.04)
- Kubernetes

## 設定

同封されている `config.example.yaml` を `config.yaml` に名前変更して，下記の部分を書き換えます。

```yaml:config.yaml
profile:
    - name: Profile 1
      line:
          user: LINE のユーザ ID
          pass: LINE のログインパスワード
```

メルカリに LINE アカウントでログインするため、LINE にログインするのに必要な情報を指定します。
(一度パスコードでログインできるようにした場合、メルカリにメールアドレスとパスワードではログインできなくなります)

ログインに関する認証コードのやり取りを Slack で行いたい場合は、下記の部分もコメントアウトを解除した上で書き換えてください。
コメントアウトしたままだと、標準入出力経由でやり取りする動作になります。

```yaml:config.yaml
slack:
    bot_token: xoxp-XXXXXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    from: Mercari Bot
    info:
        channel:
            name: "#mercari"
    captcha:
        channel:
            name: "#captcha"
            id: XXXXXXXXXXX
    error:
        channel:
            name: "#error"
            id: XXXXXXXXXXX
        interval_min: 180
```

## 動かし方

### Linux の場合

#### 準備

```bash:bash
sudo apt install docker
```

#### 実行

```bash:bash
docker compose run --build --rm mercari-bot
```

#### Docker を使いたくない場合

[Rye](https://rye.astral.sh/) と Google Chrome がインストールされた環境であれば，
下記のようにして Docker を使わずに実行できます．

```
rye sync
rye run python src/app.py
```

### Kubernetes の場合

Kubernetes で CronJob を使って定期的に実行するため設定ファイルが `kubernetes/mercari-bot.yaml` に入っていますので，
適宜カスタマイズして使っていただければと思います。

# ライセンス

Apache License Version 2.0 を適用します。
