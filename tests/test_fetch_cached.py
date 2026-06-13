import pandas as pd

from stock_strategies import cache


def _patch_api(monkeypatch, rows_by_call):
    """mock _rate_limited_get 回傳每次呼叫對應的 data；記錄呼叫次數。"""
    state = {"n": 0}

    def fake(params, timeout, max_retries):
        i = state["n"]; state["n"] += 1
        return {"status": 200, "data": rows_by_call[min(i, len(rows_by_call) - 1)]}

    monkeypatch.setattr(cache, "_rate_limited_get", fake)
    return state


def test_cache_hit_skips_api(monkeypatch):
    # 新鮮度以 max_date 距今判定（spec §6 / _is_fresh），故用近兩日資料才會命中快取
    today = pd.Timestamp.now().normalize()
    d0 = (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    d1 = today.strftime("%Y-%m-%d")
    start = (today - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    rows = [[{"date": d0, "close": 10}, {"date": d1, "close": 11}]]
    state = _patch_api(monkeypatch, rows)
    df1 = cache.fetch_finmind_cached("TaiwanStockPrice", "2330", start)
    assert len(df1) == 2
    assert state["n"] == 1
    # 第二次：新鮮快取 → 不打 API
    df2 = cache.fetch_finmind_cached("TaiwanStockPrice", "2330", start)
    assert state["n"] == 1  # 沒再呼叫
    assert len(df2) == 2


def test_end_date_filters_future(monkeypatch):
    rows = [[
        {"date": "2024-01-02", "close": 10},
        {"date": "2024-01-05", "close": 12},
        {"date": "2024-01-10", "close": 15},
    ]]
    _patch_api(monkeypatch, rows)
    df = cache.fetch_finmind_cached(
        "TaiwanStockPrice", "2330", "2024-01-01", end_date="2024-01-05"
    )
    assert df["date"].max() <= __import__("pandas").Timestamp("2024-01-05")
    assert len(df) == 2


def test_force_refresh_rehits_api(monkeypatch):
    rows = [[{"date": "2024-01-02", "close": 10}]]
    state = _patch_api(monkeypatch, rows)
    cache.fetch_finmind_cached("TaiwanStockPrice", "2330", "2024-01-01")
    cache.fetch_finmind_cached("TaiwanStockPrice", "2330", "2024-01-01", force_refresh=True)
    assert state["n"] == 2
