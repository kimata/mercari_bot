# 🛍️ mercari-bot

メルカリ出品アイテムの自動価格調整システム

[![Docker](https://github.com/kimata/mercari-bot/actions/workflows/docker.yaml/badge.svg)](https://github.com/kimata/mercari-bot/actions/workflows/docker.yaml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## 📋 概要

メルカリに出品中のアイテムの価格を自動的に値下げするボットです。お気に入り数やアイテムの価格に応じて、戦略的な価格調整を行い、商品の売れやすさを向上させます。

### 主な特徴

- 💰 **自動価格調整** - 設定した条件に基づいて自動的に値下げ
- ❤️ **お気に入り連動** - お気に入り数に応じた値下げ戦略
- 🎯 **柔軟な設定** - 値下げ幅、最低価格の細かい設定が可能
- 👥 **複数アカウント対応** - 複数のプロファイルで同時運用
- 📊 **履歴管理** - 値下げ履歴と効果の記録
- 📱 **通知機能** - Slack/メール連携によるリアルタイム通知
- 🔐 **セキュア認証** - LINE経由の安全なログイン処理
- 🎵 **CAPTCHA対応** - 音声認証の自動処理機能

## 🖼️ スクリーンショット

<details>
<summary>実行画面とログの例</summary>

※ スクリーンショットは準備中です

</details>

## 🏗️ システム構成

### アプリケーション
- **言語**: Python 3.10+
- **自動化**: Selenium WebDriver
- **音声処理**: SpeechRecognition + pydub
- **画像処理**: Pillow
- **設定管理**: YAML + JSON Schema

### インフラ
- **コンテナ**: Docker / Docker Compose
- **オーケストレーション**: Kubernetes (CronJob)
- **パッケージ管理**: Rye / Poetry

## 🚀 セットアップ

### 必要な環境

- Python 3.10以上
- Google Chrome（ローカル実行の場合）
- Docker（推奨）

### 1. リポジトリのクローン

```bash
git clone https://github.com/kimata/mercari-bot.git
cd mercari-bot
```

### 2. 設定ファイルの準備

```bash
cp config.example.yaml config.yaml
```

`config.yaml` を編集して、必要な情報を設定：

```yaml
profile:
    - name: Profile 1
      line:
          user: LINE のユーザ ID
          pass: LINE のログインパスワード
      price_down:
          step: 100           # 値下げ幅（円）
          threshold: 1000     # この価格以下には値下げしない
          favorite:
              count: 3        # お気に入り数がこの値以上なら値下げ
```

### 3. 通知設定（オプション）

Slack通知を使用する場合：

```yaml
slack:
    bot_token: xoxp-XXXXXXXXXXXX-XXXXXXXXXXXX...
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

## 💻 実行方法

### Docker を使用する場合（推奨）

```bash
# 単発実行
docker compose run --build --rm mercari-bot

# デーモンとして実行
docker compose up -d
```

### Docker を使用しない場合

#### Rye を使用（推奨）

```bash
# Ryeのインストール（未インストールの場合）
curl -sSf https://rye.astral.sh/get | bash

# 依存関係のインストールと実行
rye sync
rye run python src/app.py
```

#### Poetry を使用（代替）

```bash
# Poetryのインストール（未インストールの場合）
pip install poetry

# 依存関係のインストールと実行
poetry install
poetry run python src/app.py
```

### コマンドラインオプション

```bash
# デバッグモード
rye run python src/app.py --debug

# 特定プロファイルのみ実行
rye run python src/app.py --profile "Profile 1"

# ドライラン（実際に値下げせず確認のみ）
rye run python src/app.py --dry-run
```

## ☸️ Kubernetes デプロイ

CronJobとして定期実行する設定：

```bash
# 設定ファイルを環境に合わせて編集
vim kubernetes/mercari-bot.yaml

# デプロイ
kubectl apply -f kubernetes/mercari-bot.yaml
```

デフォルトでは1日2回（9:00と21:00）実行されます。

## 🔧 高度な設定

### 値下げ戦略のカスタマイズ

`config.yaml` で詳細な値下げ戦略を設定できます：

```yaml
price_down:
    update_interval:
        day: 7              # 最後の更新から何日経過したら値下げ対象とするか
    step: 100               # 基本の値下げ幅
    threshold: 1000         # 最低価格
    favorite:
        count: 3            # お気に入り数の閾値
        step_ratio: 2.0     # お気に入りが多い場合の値下げ幅倍率
```

### プロキシ設定

企業ネットワーク等でプロキシが必要な場合：

```yaml
proxy:
    http: http://proxy.example.com:8080
    https: http://proxy.example.com:8080
```

## 🧪 開発

### テスト実行

```bash
# ユニットテスト
rye run pytest

# 特定のテストファイル
rye run pytest tests/test_mercari.py

# カバレッジレポート付き
rye run pytest --cov=src --cov-report=html
```

### コード品質チェック

```bash
# フォーマット
rye run black src/

# リント
rye run flake8 src/
```

## 📊 CI/CD

GitHub Actions による自動化：
- Dockerイメージのビルドとプッシュ
- 依存関係の自動更新（Renovate）
- セキュリティスキャン

## ⚠️ 注意事項

- メルカリの利用規約を遵守してご使用ください
- 過度な自動化は制限される可能性があります
- LINE認証情報は安全に管理してください
- 本番環境では必ずdry-runで動作確認を行ってください

## 🤝 コントリビューション

プルリクエストを歓迎します！バグ報告や機能要望は[Issues](https://github.com/kimata/mercari-bot/issues)までお願いします。

1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add some amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## 📝 ライセンス

このプロジェクトは Apache License Version 2.0 のもとで公開されています。

---

<div align="center">

**⭐ このプロジェクトが役に立った場合は、Star をお願いします！**

[🐛 Issue 報告](https://github.com/kimata/mercari-bot/issues) | [💡 機能リクエスト](https://github.com/kimata/mercari-bot/issues/new) | [📖 Wiki](https://github.com/kimata/mercari-bot/wiki)

</div>
