from pathlib import Path

import pandas as pd
import pytest

import main
from src import MovieStorage


def test_movies_persist(client, test_storage, uploaded_movies):
    second_storage = MovieStorage(test_storage.db_path)

    df = second_storage.get()
    assert len(df) == 20
    assert second_storage.count_movies() == 20
    assert list(df.columns) == ["title", "release_year", "rating", "genre"]

    original = pd.read_csv(Path("fixtures") / "sample_movies.csv")
    assert df["title"].fillna("").tolist() == original["title"].fillna("").tolist()

    stored_ids = [row["id"] for row in second_storage.select_columns(["title"], limit=100)]
    response = client.get("/movies", params={"limit": 100})
    assert response.status_code == 200
    api_ids = [row["id"] for row in response.json()["data"]]

    assert stored_ids == list(range(1, 21))
    assert api_ids == list(range(1, 21))


def test_cache_and_processing(client, uploaded_movies, processing_body):
    first_100 = client.get("/movies", params={"limit": 100})
    first_1 = client.get("/movies", params={"limit": 1})
    assert first_100.status_code == 200
    assert first_1.status_code == 200
    assert main.cache.get(100) == first_100.json()
    assert main.cache.get(1) == first_1.json()

    repeat_100 = client.get("/movies", params={"limit": 100})
    assert repeat_100.status_code == 200
    assert repeat_100.json() == first_100.json()

    processed = client.post("/movies/process", json=processing_body)
    assert processed.status_code == 200
    body = processed.json()
    assert body["validation_rows_removed"] == 0
    expected_report = {
        "rows_before": 20,
        "rows_after": 16,
        "rows_removed": 4,
        "columns_before": 4,
        "columns_after": 4,
        "columns_removed": 0,
    }
    for key, value in expected_report.items():
        assert body["cleaning_report"][key] == value
    assert main.cache.get(100) is None
    assert main.cache.get(1) is None

    after = client.get("/movies", params={"limit": 100})
    assert after.status_code == 200
    after_body = after.json()
    assert after_body["total_rows"] == 16
    assert len(after_body["data"]) == 16
    titles = [movie["title"] for movie in after_body["data"]]
    assert titles == [f"Movie {letter}" for letter in "ABCDEFGHIJKLMNOP"]
    assert [movie["id"] for movie in after_body["data"]] == list(range(1, 17))
    assert main.cache.get(100) == after_body


def test_cache_hit_skips_database(client, uploaded_movies, monkeypatch):
    first = client.get("/movies", params={"limit": 100})
    assert first.status_code == 200

    def fail_if_called(*args, **kwargs):
        pytest.fail("Database was queried on a cache hit")

    monkeypatch.setattr(main.storage, "select_columns", fail_if_called)
    monkeypatch.setattr(main.storage, "count_movies", fail_if_called)

    second = client.get("/movies", params={"limit": 100})
    assert second.status_code == 200
    assert second.json() == first.json()