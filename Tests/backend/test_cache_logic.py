from __future__ import annotations

from fastapi import Response


class CapturedBackgroundTasks:
    def __init__(self):
        self.tasks: list[tuple] = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))


def test_cache_hit_schedules_one_refresh_and_reschedules_after_task_completes(
    backend_main, monkeypatch
):
    fetch_calls: list[str] = []
    cached_payload = {"categories": [{"name": "Top headlines", "articles": []}]}
    refreshed_payload = {"categories": [{"name": "Top headlines", "articles": [{"title": "New"}]}]}

    def fake_fetch_news_cards(lang: str):
        fetch_calls.append(lang)
        return refreshed_payload if len(fetch_calls) > 1 else cached_payload

    monkeypatch.setattr(backend_main, "fetch_news_cards", fake_fetch_news_cards)

    first_bg = CapturedBackgroundTasks()
    first_result = backend_main.get_news(
        response=Response(),
        background_tasks=first_bg,
        lang="en",
        refresh=False,
    )

    assert first_result == cached_payload
    assert fetch_calls == ["en"]
    assert first_bg.tasks == []

    second_bg = CapturedBackgroundTasks()
    second_result = backend_main.get_news(
        response=Response(),
        background_tasks=second_bg,
        lang="en",
        refresh=False,
    )

    assert second_result == cached_payload
    assert fetch_calls == ["en"]
    assert len(second_bg.tasks) == 1

    task_fn, task_args, task_kwargs = second_bg.tasks[0]
    assert task_fn is backend_main.refresh_cache_background
    assert task_args == ("en",)
    assert task_kwargs == {}

    # Simulate background task completion (which should reset is_refreshing to False).
    task_fn(*task_args, **task_kwargs)

    assert backend_main.NEWS_CACHE["en"]["data"] == refreshed_payload
    assert backend_main.NEWS_CACHE["en"]["is_refreshing"] is False

    # A later cache hit should schedule exactly one new background refresh.
    third_bg = CapturedBackgroundTasks()
    third_result = backend_main.get_news(
        response=Response(),
        background_tasks=third_bg,
        lang="en",
        refresh=False,
    )
    assert third_result == refreshed_payload
    assert len(third_bg.tasks) == 1
    assert third_bg.tasks[0][1] == ("en",)
    assert fetch_calls == ["en", "en"]


def test_refresh_true_forces_blocking_refresh_and_updates_cache(backend_main, monkeypatch):
    backend_main.NEWS_CACHE["en"] = {
        "data": {"categories": [{"name": "Old", "articles": []}]},
        "fetched_at": 0.0,
        "is_refreshing": True,
    }
    forced_payload = {"categories": [{"name": "Forced", "articles": []}]}

    monkeypatch.setattr(backend_main, "fetch_news_cards", lambda lang: forced_payload)

    bg = CapturedBackgroundTasks()
    result = backend_main.get_news(
        response=Response(),
        background_tasks=bg,
        lang="en",
        refresh=True,
    )

    assert result == forced_payload
    assert bg.tasks == []
    assert backend_main.NEWS_CACHE["en"]["data"] == forced_payload
    assert backend_main.NEWS_CACHE["en"]["is_refreshing"] is False


def test_background_refresh_failure_resets_flag_and_allows_retry(backend_main, monkeypatch):
    backend_main.NEWS_CACHE["en"] = {
        "data": {"categories": [{"name": "Top headlines", "articles": []}]},
        "fetched_at": 0.0,
        "is_refreshing": True,
    }

    def boom(_lang: str):
        raise RuntimeError("upstream failure")

    monkeypatch.setattr(backend_main, "fetch_news_cards", boom)

    backend_main.refresh_cache_background("en")
    assert backend_main.NEWS_CACHE["en"]["is_refreshing"] is False

    bg = CapturedBackgroundTasks()
    result = backend_main.get_news(
        response=Response(),
        background_tasks=bg,
        lang="en",
        refresh=False,
    )

    assert result == {"categories": [{"name": "Top headlines", "articles": []}]}
    assert len(bg.tasks) == 1
    assert bg.tasks[0][1] == ("en",)


def test_cache_isolation_between_languages(backend_main, monkeypatch):
    backend_main.NEWS_CACHE["en"] = {
        "data": {"categories": [{"name": "EN", "articles": []}]},
        "fetched_at": 0.0,
        "is_refreshing": False,
    }
    backend_main.NEWS_CACHE["zh"] = {
        "data": {"categories": [{"name": "ZH", "articles": []}]},
        "fetched_at": 0.0,
        "is_refreshing": False,
    }

    monkeypatch.setattr(
        backend_main,
        "fetch_news_cards",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("fetch_news_cards should not run on cache-hit isolation test.")
        ),
    )

    en_bg = CapturedBackgroundTasks()
    en_result = backend_main.get_news(
        response=Response(),
        background_tasks=en_bg,
        lang="en",
        refresh=False,
    )

    assert en_result["categories"][0]["name"] == "EN"
    assert len(en_bg.tasks) == 1
    assert en_bg.tasks[0][1] == ("en",)
    assert backend_main.NEWS_CACHE["zh"]["is_refreshing"] is False

    zh_bg = CapturedBackgroundTasks()
    zh_result = backend_main.get_news(
        response=Response(),
        background_tasks=zh_bg,
        lang="zh",
        refresh=False,
    )

    assert zh_result["categories"][0]["name"] == "ZH"
    assert len(zh_bg.tasks) == 1
    assert zh_bg.tasks[0][1] == ("zh",)
