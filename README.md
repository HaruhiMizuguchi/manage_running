# manage_running

Stravaのデータエクスポート（ZIP/CSV）から、ランニング記録をローカルで管理するミニアプリです。  
ダイエット（継続走行・消費カロリー・体重）とスピード向上（ペース・5km目標）を意識したダッシュボードを提供します。

## 起動

```bash
sudo apt-get update
sudo apt-get install -y python3.12-venv

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

ブラウザで `http://localhost:8000` を開きます。

## 主な機能

| 画面 | 内容 |
|------|------|
| `/` | 週次距離・ペース推移・体重と走行距離のグラフ、今週の進捗 |
| `/import` | Stravaエクスポート（ZIP/CSV）の取り込み |
| `/runs` | ラン一覧（距離・ペース表示） |
| `/runs/{id}` | ラン詳細 |
| `/weight` | 体重ログ |
| `/goals` | 週間走行距離・5km目標タイムの設定 |

## データ取り込み

1. Stravaの「データエクスポート」を取得
2. ZIP（推奨）を `/import` からアップロード
3. ZIP内の `activities.csv` を自動検出して取り込み
4. 既定では「ランのみ」を取り込み（チェックを外すと全アクティビティも可）
5. 同じ Activity ID は上書き更新

## データ保存先

- デフォルト: `data/runmgr.sqlite3`
- 変更する場合: `RUNMGR_DB_PATH` を設定

## テスト

```bash
. .venv/bin/activate
pytest -q
```
