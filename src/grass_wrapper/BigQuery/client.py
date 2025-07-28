"""
BigQuery クライアント

認証
----
- **Application Default Credentials (ADC)** を利用する前提。  
  例）`GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json python app.py`
- `credentials_path` を渡せばサービスアカウント JSON を直接指定できます。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from google.cloud import bigquery
from google.api_core.exceptions import NotFound
from google.cloud.bigquery import job as bq_job  # for precise typing
from google.cloud.bigquery import TimePartitioning

__all__ = ["BigQuery"]


class BigQuery:
    """
    Parameters
    ----------
    project_id : str
        GCP プロジェクト ID。
    credentials_path : str | Path | None, optional
        サービスアカウント JSON のパス。省略時は ADC を使用。
    default_location : str | None, optional
        すべてのジョブで使うロケーション（例: "US"）。未指定なら API デフォルト。
    """

    def __init__(
        self,
        *,
        project_id: str,
        credentials_path: str | Path | None = None,
        default_location: str | None = None,
    ) -> None:
        if not project_id:
            raise ValueError("project_id is required when instantiating BigQuery client.")

        if credentials_path:
            credentials_path = Path(credentials_path).expanduser().resolve()
            self._client = bigquery.Client.from_service_account_json(
                credentials_path, project=project_id
            )
        else:
            # ADC (Application Default Credentials)
            self._client = bigquery.Client(project=project_id)

        self._location = default_location

    # ------------------------------------------------------------------ #
    # Public Methods
    # ------------------------------------------------------------------ #

    def upload_rows(
        self,
        *,
        dataset: str,
        table: str,
        rows: Iterable[dict[str, Any]],
        write_disposition: str = "WRITE_APPEND",
        schema: list[bigquery.SchemaField] | None = None,
        time_partitioning: TimePartitioning | None = None,
        clustering_fields: list[str] | None = None,
    ) -> bigquery.LoadJob:
        """
        BigQuery テーブルへ `list[dict]` をロードする汎用ユーティリティ。

        Parameters
        ----------
        dataset : str
            データセット ID。
        table : str
            テーブル ID。
        rows : Iterable[dict]
            挿入する行データ。
        write_disposition : {"WRITE_APPEND", "WRITE_TRUNCATE", "WRITE_EMPTY"}, default "WRITE_APPEND"
            BigQuery の書き込みモード。
        schema : list[bigquery.SchemaField] | None, optional
            スキーマを明示指定したい場合に渡す。None の場合は `autodetect=True`。
        time_partitioning : bigquery.TimePartitioning | None, optional
            テーブルの時間パーティショニング設定。指定しない場合は None。
        clustering_fields : list[str] | None, optional
            クラスタリングに使うフィールド名のリスト。指定しない場合は None。
        """
        if write_disposition not in {
            "WRITE_APPEND",
            "WRITE_TRUNCATE",
            "WRITE_EMPTY",
        }:
            raise ValueError(
                "write_disposition must be one of "
                "'WRITE_APPEND', 'WRITE_TRUNCATE', or 'WRITE_EMPTY'"
            )

        table_ref = f"{self._client.project}.{dataset}.{table}"

        # テーブル存在チェック（無ければ load_job で自動生成）
        try:
            self._client.get_table(table_ref)
        except NotFound:
            pass

        job_config = bigquery.LoadJobConfig(
            write_disposition=write_disposition,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            autodetect=schema is None,
            schema=schema,
            time_partitioning=time_partitioning,
            clustering_fields=clustering_fields,
        )

        load_job = self._client.load_table_from_json(
            list(rows),
            destination=table_ref,
            job_config=job_config,
            location=self._location,
        )
        load_job.result()
        return load_job

    def upload_rows_if_absent(
        self,
        *,
        dataset: str,
        table: str,
        rows: Iterable[dict[str, Any]],
        key_fields: list[str],
        temp_dataset: str | None = None,
        time_partitioning: TimePartitioning | None = None,
        clustering_fields: list[str] | None = None,
        schema: list[bigquery.SchemaField] | None = None,
    ) -> bq_job.QueryJob:
        """
        `key_fields` 複合キーで既存行を判定し、未存在行だけを INSERT するヘルパー。

        Notes
        -----
        1. rows を同一 project 内の一時テーブルへロード
        2. MERGE で target へ upsert (NOT MATCHED THEN INSERT)
        3. 一時テーブルを削除

        Parameters
        ----------
        dataset : str
            データセット ID。
        table : str
            テーブル ID。
        rows : Iterable[dict]
            挿入する行データ。
        key_fields : list[str]
            複合キーとして使うカラム名のリスト。
        temp_dataset : str | None, optional
            一時テーブルを作成するデータセット。None の場合は dataset と同じ。
        time_partitioning : bigquery.TimePartitioning | None, optional
            対象テーブルの時間パーティショニング設定。指定しない場合は None。
        clustering_fields : list[str] | None, optional
            対象テーブルのクラスタリングフィールド名のリスト。指定しない場合は None。
        schema : list[bigquery.SchemaField] | None, optional
            スキーマを明示指定したい場合に渡す。None の場合は `autodetect=True`。
        """
        from uuid import uuid4

        if not key_fields:
            raise ValueError("key_fields must contain at least one column name.")

        tmp_dataset = temp_dataset or dataset
        tmp_table = f"tmp_{table}_{uuid4().hex[:8]}"

        self.upload_rows(
            dataset=tmp_dataset,
            table=tmp_table,
            rows=rows,
            write_disposition="WRITE_TRUNCATE",
            schema=schema,
            time_partitioning=None,
            clustering_fields=None,
        )

        tmp_ref = f"{self._client.project}.{tmp_dataset}.{tmp_table}"
        target_ref = f"{self._client.project}.{dataset}.{table}"

        try:
            self._client.get_table(target_ref)
        except NotFound:
            # create empty table with desired schema & partitioning
            table_obj = bigquery.Table(target_ref, schema=schema or [])
            if time_partitioning:
                table_obj.time_partitioning = time_partitioning
            if clustering_fields:
                table_obj.clustering_fields = clustering_fields
            self._client.create_table(table_obj)

        on_clause = " AND ".join([f"T.{c}=S.{c}" for c in key_fields])

        merge_sql = f"""
        MERGE `{target_ref}` AS T
        USING `{tmp_ref}`   AS S
        ON {on_clause}
        WHEN NOT MATCHED THEN
          INSERT ROW
        """

        job = self._client.query(merge_sql, location=self._location)
        job.result()

        self._client.delete_table(tmp_ref, not_found_ok=True)
        return job