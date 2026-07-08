# manage_running

Stravaのデータエクスポート（ZIP/CSV）から、ランニング記録をローカルで管理するミニアプリです。

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

## データ取り込み

- Stravaの「データエクスポート」を取得し、ZIP（推奨）を `/import` からアップロードしてください
- ZIP内の `activities.csv` を検出して取り込みます
- 既定では「ランのみ」を取り込みます（チェックを外すと全アクティビティも可）

## データ保存先

- デフォルト: `data/runmgr.sqlite3`
- 変更する場合: `RUNMGR_DB_PATH` を設定してください