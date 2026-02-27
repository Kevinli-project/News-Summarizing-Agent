from __future__ import annotations

import json
from types import SimpleNamespace


def test_fetch_news_cards_uses_en_prompt_and_schema(backend_main, monkeypatch):
    mocked_cards = {
        "categories": [
            {
                "name": "Top headlines",
                "articles": [
                    {
                        "title": "Mock headline",
                        "summary": "Mock summary for integration test.",
                        "image": None,
                        "url": "https://example.com/article",
                        "source": "Example News",
                        "published": "Feb 26, 2026",
                    }
                ],
            }
        ]
    }

    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(mocked_cards)))]
    )
    captured_args: dict = {}
    raw_news_payload = "raw-news-json-from-presenter"

    def fake_create(**kwargs):
        captured_args.update(kwargs)
        return fake_response

    monkeypatch.setattr(backend_main.pres, "get_today_news", lambda: raw_news_payload)
    monkeypatch.setattr(backend_main.openai_client.chat.completions, "create", fake_create)

    result = backend_main.fetch_news_cards("en")

    assert result == mocked_cards
    assert captured_args["response_format"]["type"] == "json_schema"
    assert captured_args["response_format"]["json_schema"] == backend_main.NEWS_CARD_SCHEMA
    assert captured_args["messages"][0]["content"] == backend_main.CARD_PROMPT_EN
    assert captured_args["messages"][1]["content"] == raw_news_payload

    assert isinstance(result.get("categories"), list)
    first_category = result["categories"][0]
    assert set(first_category.keys()) == {"name", "articles"}

    article = first_category["articles"][0]
    assert set(article.keys()) == {"title", "summary", "image", "url", "source", "published"}
    assert isinstance(article["title"], str)
    assert isinstance(article["summary"], str)
    assert isinstance(article["url"], str)
    assert isinstance(article["source"], str)
    assert isinstance(article["published"], str)
    assert article["image"] is None or isinstance(article["image"], str)


def test_fetch_news_cards_uses_zh_prompt_when_lang_is_zh(backend_main, monkeypatch):
    mocked_cards = {"categories": []}
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(mocked_cards)))]
    )
    captured_args: dict = {}

    monkeypatch.setattr(backend_main.pres, "get_today_news", lambda: "raw-news")
    monkeypatch.setattr(
        backend_main.openai_client.chat.completions,
        "create",
        lambda **kwargs: captured_args.update(kwargs) or fake_response,
    )

    result = backend_main.fetch_news_cards("zh")

    assert result == mocked_cards
    assert captured_args["messages"][0]["content"] == backend_main.CARD_PROMPT_ZH
    assert captured_args["response_format"]["json_schema"] == backend_main.NEWS_CARD_SCHEMA


def test_fetch_news_cards_raises_on_invalid_json_from_model(backend_main, monkeypatch):
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="{invalid-json"))]
    )
    monkeypatch.setattr(backend_main.pres, "get_today_news", lambda: "raw-news")
    monkeypatch.setattr(
        backend_main.openai_client.chat.completions,
        "create",
        lambda **kwargs: fake_response,
    )

    try:
        backend_main.fetch_news_cards("en")
        raise AssertionError("Expected JSON parsing to fail for invalid model output.")
    except json.JSONDecodeError:
        pass
