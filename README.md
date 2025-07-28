

# grass‑wrapper

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/grass-wrapper.svg)](https://pypi.org/project/grass-wrapper/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/grass-labs/grass-wrapper/actions/workflows/ci.yml/badge.svg)](https://github.com/grass-labs/grass-wrapper/actions)

</div>

`grass-wrapper` は **Python 3.10+** で動作する汎用ユーティリティ集です。  
時系列 API からのデータ取得／加工と、Google BigQuery への高速ロードをシンプルな API で提供します。

---

## Features

| Module | What you get |
|--------|--------------|
| **`grass_wrapper.CoinGlass`** | REST クライアント生成とエンドポイントラッパー<br>例: `get_fr_ohlc_history()` で funding‑rate OHLC をリスト取得 |
| **`grass_wrapper.BigQuery`** | 軽量ラッパークラス `BigQuery`<br>• `upload_rows()` — list[dict] をロード<br>• `upload_rows_if_absent()` — 一意キー重複チェック付きロード |
| **Type Hints & Pydantic‑like** | すべての関数が Python typing に対応し、IDE 補完が快適 |
| **パーティション / クラスタ自動生成** | 初回ロード時に `PARTITION BY` と `CLUSTER BY` を自動設定 |

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

cg = CoinGlass()                           # CG_API_KEY は環境変数から読む
bq = BigQuery(project_id="my-gcp-project") # 認証は ADC 前提
```

---

## Requirements

* Python ≥ 3.10
* `google-cloud-bigquery` ≥ 3.35
* `requests` ≥ 2.32
* CoinGlass API key (`CG_API_KEY`)  
  BigQuery は ADC もしくは Service Account JSON に対応

---

## Contributing

1. Fork & clone this repo
2. `pip install -e .[dev]`
3. `ruff check . && pytest -q`
4. Make a PR against `main`

We ♥ contributions — issues, docs, tests, new features!

---

## License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.