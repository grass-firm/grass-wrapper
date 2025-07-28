# tests/test_bq.py
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from grass_wrapper.BigQuery.client import BigQuery


class DummyLoadJob:
    """最低限の stub ― result() が呼ばれたらOKにするだけ"""
    def __init__(self) -> None:
        self.result_called = False

    def result(self) -> None:
        self.result_called = True


class DummyClient:
    """google.cloud.bigquery.Client を丸ごと置き換え"""
    def __init__(self, *_, **__) -> None:
        self.project = "dummy-proj"
        # 呼び出し状況を記録するための変数
        self.loaded_json: list[dict[str, Any]] = []
        self.job_cfg = None

    # ---- BigQuery メソッドのダミー実装 -----------------
    def get_table(self, table_ref: str) -> None:  # 存在チェック用
        # BigQuery API would raise NotFound; upload_list swallows it internally.
        # ここでは何もしないで成功扱いにする
        return None

    def load_table_from_json(
        self,
        rows_json,
        destination: str,
        job_config,
        location=None,
    ):
        self.loaded_json.extend(rows_json)
        self.job_cfg = job_config
        return DummyLoadJob()
    # ---------------------------------------------------


@pytest.fixture()
def patched_bigquery(monkeypatch):
    """
    BigQuery クライアント生成時に DummyClient を返すフィクスチャ。
    """
    dummy = DummyClient()

    import grass_wrapper.BigQuery.client as bq_mod

    # Stub objects that upload_list expects
    mocked_bigquery = SimpleNamespace(
        Client=lambda **_: dummy,
        LoadJobConfig=lambda **kwargs: SimpleNamespace(**kwargs),
        SourceFormat=SimpleNamespace(NEWLINE_DELIMITED_JSON="NEWLINE_DELIMITED_JSON"),
    )

    monkeypatch.setattr(bq_mod, "bigquery", mocked_bigquery)
    return dummy


def test_upload_rows(patched_bigquery):
    bq = BigQuery(project_id="dummy-proj")            # DummyClient が注入される

    rows = [
        {"time": 1, "value": 10},
        {"time": 2, "value": 20},
    ]
    job = bq.upload_rows(dataset="ds", table="tbl", rows=rows)

    # 1) DummyLoadJob の result() が呼ばれたか
    assert isinstance(job, DummyLoadJob)
    assert job.result_called is True

    # 2) 送られた JSON がそのまま渡っているか
    assert patched_bigquery.loaded_json == rows

    # 3) autodetect が True（schema=None のとき）になっているか
    assert getattr(patched_bigquery.job_cfg, "autodetect", False) is True