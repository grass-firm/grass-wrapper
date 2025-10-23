# grass-wrapper

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/grass-wrapper.svg)](https://pypi.org/project/grass-wrapper/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/grass-labs/grass-wrapper/actions/workflows/ci.yml/badge.svg)](https://github.com/grass-labs/grass-wrapper/actions)

</div>

`grass-wrapper` は **Python 3.10+** で動作する汎用ユーティリティ集です。  
時系列 API からのデータ取得／加工、**ローカル（DuckDB）** および **Google BigQuery** への高速ロードをシンプルな API で提供します。

---

## Features

| Module | What you get |
|--------|--------------|
| **`grass_wrapper.CoinGlass`** | REST クライアント生成とエンドポイントラッパー<br>例: `get_fr_ohlc_history()` で funding-rate OHLC を取得 |
| **`grass_wrapper.Bybit`** | **Bybit V5 API クライアント**<br>• `get_tickers()` — 最新ティッカー取得<br>• `get_kline()` — 任意足のローソク足取得<br>• `get_positions()` / `get_orders()` — ポジション・注文情報取得 |
| **`grass_wrapper.BigQuery`** | 軽量ラッパークラス **`BigQuery`**<br>• `upload_rows()` — `list[dict]` をロード<br>• `upload_rows_if_absent()` — 一意キー重複チェック付きロード（初回に `PARTITION BY` / `CLUSTER BY` を自動設定） |
| **`grass_wrapper.DuckDB`** | ローカル高速ストレージ **`DuckDBClient`**<br>• `.insert_dataframe()` — `pandas.DataFrame` を保存<br>• `.query()` — SQLで即時クエリ（バックテスト・長期保存に最適） |

---

## Installation

```bash
pip install grass-wrapper
```

開発者向け:

```bash
git clone https://github.com/grass-labs/grass-wrapper.git
cd grass-wrapper
pip install -e .[dev]   # includes pytest, ruff, black
```

---

## Quick Start

```python
from grass_wrapper.CoinGlass.client import CoinGlass
from grass_wrapper.BigQuery.client import BigQuery
from grass_wrapper.Bybit.client import Bybit
from grass_wrapper.DuckDB.client import DuckDBClient

# API クライアント
cg = CoinGlass()                               # CG_API_KEY は環境変数から読む
byb = Bybit(api_key="...", api_secret="...")   # Bybit V5 REST

# ストレージ
bq = BigQuery(project_id="my-gcp-project")     # 認証は ADC 前提
duck = DuckDBClient("data/grass.duckdb")       # ローカル DuckDB ファイルに保存

# 例: Bybit ティッカーを取得して DuckDB に保存
tickers = byb.get_tickers(category="linear")
import pandas as pd
df = pd.DataFrame(tickers)
duck.insert_dataframe("bybit_tickers", df)

# 例: DuckDB からクエリ
res = duck.query("SELECT * FROM bybit_tickers ORDER BY updatedTime DESC LIMIT 5")
print(res)
```

---

## Requirements

- Python ≥ 3.10
- `requests` ≥ 2.32
- `google-cloud-bigquery` ≥ 3.35
- `duckdb` ≥ 1.4.0
- CoinGlass API key (`CG_API_KEY`)
- Bybit API key/secret（V5）

> BigQuery は ADC（Application Default Credentials）または Service Account JSON に対応。

---

## Contributing

1. Fork & clone this repo  
2. `pip install -e .[dev]`  
3. `ruff check . && pytest -q`  
4. Make a PR against `main`

We ♥ contributions — issues, docs, tests, new features!

---

## License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.