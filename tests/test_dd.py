from grass_wrapper.DuckDB import DuckDBClient
import pandas as pd
from pathlib import Path


def test_duckdb_basic(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"
    client = DuckDBClient(db_path)

    df = pd.DataFrame({"symbol": ["BTCUSDT", "ETHUSDT"], "price": [69000, 3700]})
    client.insert_dataframe("tickers", df)

    result = client.query("SELECT COUNT(*) AS n FROM tickers").iloc[0]["n"]
    assert result == 2

    client.close()