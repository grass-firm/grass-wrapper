import duckdb
from pathlib import Path
import pandas as pd


class DuckDBClient:
    def __init__(self, db_path: str | Path = "data/grass.duckdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))

    def query(self, sql: str) -> pd.DataFrame:
        """Run a SQL query and return a DataFrame."""
        return self.conn.execute(sql).fetchdf()

    def insert_dataframe(self, table_name: str, df: pd.DataFrame, mode: str = "append"):
        """Insert or overwrite a pandas DataFrame into a DuckDB table."""
        if mode == "overwrite":
            self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        self.conn.register("tmp_df", df)
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM tmp_df LIMIT 0")
        self.conn.execute(f"INSERT INTO {table_name} SELECT * FROM tmp_df")
        self.conn.unregister("tmp_df")

    def vacuum(self):
        """Run VACUUM to compact the database file."""
        self.conn.execute("VACUUM")

    def close(self):
        self.conn.close()