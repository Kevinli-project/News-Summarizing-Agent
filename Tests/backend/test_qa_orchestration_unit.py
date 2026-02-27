from __future__ import annotations

import json
from types import SimpleNamespace


def _tool_call(name: str, arguments: dict, call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _chunk(content: str) -> SimpleNamespace:
    class _Delta:
        def __init__(self, text: str):
            self.text = text

        def model_dump(self, exclude_none: bool = True):
            return {"content": self.text}

    return SimpleNamespace(choices=[SimpleNamespace(delta=_Delta(content))])


def _tool_messages(messages: list[object]) -> list[dict]:
    return [msg for msg in messages if isinstance(msg, dict) and msg.get("role") == "tool"]


def test_chat_reroutes_to_find_internet_articles_after_failed_evaluation(
    load_project_module, monkeypatch
):
    question_answer = load_project_module("question_answer")
    qa = question_answer.QA()

    initial_reply = SimpleNamespace(
        tool_calls=[
            _tool_call(
                "visit_website",
                {"url": "https://www.nytimes.com/2026/02/01/world/example.html"},
                "call_visit",
            )
        ]
    )
    rerun_reply = SimpleNamespace(
        tool_calls=[
            _tool_call(
                "find_internet_articles",
                {"query": "new york times paywalled article summary"},
                "call_search",
            )
        ]
    )

    probe_response = SimpleNamespace(choices=[SimpleNamespace(message=initial_reply)])
    create_calls: list[dict] = []

    def fake_create(*args, **kwargs):
        create_calls.append(kwargs)
        if kwargs.get("stream"):
            return iter([_chunk("Summary line 1.\n\n"), _chunk("Summary line 2.")])
        return probe_response

    monkeypatch.setattr(qa.openai.chat.completions, "create", fake_create)
    monkeypatch.setattr(
        qa,
        "evaluate",
        lambda *args, **kwargs: question_answer.Evaluation(
            is_acceptable=False,
            feedback="visit_website should not be used for paywalled sources.",
        ),
    )
    monkeypatch.setattr(
        qa,
        "rerun",
        lambda *args, **kwargs: SimpleNamespace(choices=[SimpleNamespace(message=rerun_reply)]),
    )

    captured_queries: list[str] = []

    def fake_find_internet_articles(query: str) -> str:
        captured_queries.append(query)
        return "Mocked web search summary."

    monkeypatch.setattr(qa, "find_internet_articles", fake_find_internet_articles)
    monkeypatch.setattr(
        qa,
        "lookup_news",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("visit_website should not run after evaluator rejection.")
        ),
    )

    streamed_output = list(qa.chat("Can you explain this NYT article?", history=[]))

    assert captured_queries == ["new york times paywalled article summary"]
    assert streamed_output[-1] == "Summary line 1.\n\nSummary line 2."

    stream_call = next(call for call in create_calls if call.get("stream"))
    tool_messages = _tool_messages(stream_call["messages"])
    assert len(tool_messages) == 1
    tool_payload = json.loads(tool_messages[0]["content"])
    assert tool_payload["query"] == "new york times paywalled article summary"
    assert "Mocked web search summary." in tool_payload["search_results"]


def test_chat_happy_path_uses_visit_website_when_evaluator_accepts(
    load_project_module, monkeypatch
):
    question_answer = load_project_module("question_answer")
    qa = question_answer.QA()

    assistant_with_visit_call = SimpleNamespace(
        tool_calls=[_tool_call("visit_website", {"url": "https://example.com/news"}, "call_visit")]
    )
    probe_response = SimpleNamespace(choices=[SimpleNamespace(message=assistant_with_visit_call)])
    create_calls: list[dict] = []

    def fake_create(*args, **kwargs):
        create_calls.append(kwargs)
        if kwargs.get("stream"):
            return iter([_chunk("Explainer paragraph.\n\n"), _chunk("Closing line.")])
        return probe_response

    visited_urls: list[str] = []

    monkeypatch.setattr(qa.openai.chat.completions, "create", fake_create)
    monkeypatch.setattr(
        qa,
        "evaluate",
        lambda *args, **kwargs: question_answer.Evaluation(is_acceptable=True, feedback="ok"),
    )
    monkeypatch.setattr(
        qa,
        "rerun",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("rerun should not be called when evaluator accepts tool call.")
        ),
    )
    monkeypatch.setattr(
        qa,
        "lookup_news",
        lambda url: visited_urls.append(url) or "Fetched article contents.",
    )
    monkeypatch.setattr(
        qa,
        "find_internet_articles",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("find_internet_articles should not run in visit_website happy path.")
        ),
    )

    streamed_output = list(qa.chat("Explain this linked article.", history=[]))

    assert visited_urls == ["https://example.com/news"]
    assert streamed_output[-1] == "Explainer paragraph.\n\nClosing line."

    stream_call = next(call for call in create_calls if call.get("stream"))
    tool_messages = _tool_messages(stream_call["messages"])
    assert len(tool_messages) == 1
    tool_payload = json.loads(tool_messages[0]["content"])
    assert tool_payload["url"] == "https://example.com/news"
    assert tool_payload["web_content"] == "Fetched article contents."


def test_chat_no_tool_path_streams_direct_answer(load_project_module, monkeypatch):
    question_answer = load_project_module("question_answer")
    qa = question_answer.QA()

    probe_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None))])
    create_calls: list[dict] = []

    def fake_create(*args, **kwargs):
        create_calls.append(kwargs)
        if kwargs.get("stream"):
            return iter([_chunk("Direct answer from model.")])
        return probe_response

    monkeypatch.setattr(qa.openai.chat.completions, "create", fake_create)
    monkeypatch.setattr(
        qa,
        "evaluate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("evaluate should not be called on no-tool path.")
        ),
    )
    monkeypatch.setattr(
        qa,
        "handle_tool_call",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("handle_tool_call should not run on no-tool path.")
        ),
    )

    streamed_output = list(qa.chat("What does this mean in simple terms?", history=[]))

    assert streamed_output == ["Direct answer from model."]
    assert len(create_calls) == 2
    assert create_calls[1].get("stream") is True
    assert all(msg["role"] != "tool" for msg in create_calls[1]["messages"])


def test_chat_can_use_find_internet_articles_without_rerun(load_project_module, monkeypatch):
    question_answer = load_project_module("question_answer")
    qa = question_answer.QA()

    assistant_with_search_call = SimpleNamespace(
        tool_calls=[
            _tool_call(
                "find_internet_articles",
                {"query": "latest AI chip export policy impacts"},
                "call_search",
            )
        ]
    )
    probe_response = SimpleNamespace(choices=[SimpleNamespace(message=assistant_with_search_call)])
    create_calls: list[dict] = []

    def fake_create(*args, **kwargs):
        create_calls.append(kwargs)
        if kwargs.get("stream"):
            return iter([_chunk("Search-backed answer.")])
        return probe_response

    captured_queries: list[str] = []

    monkeypatch.setattr(qa.openai.chat.completions, "create", fake_create)
    monkeypatch.setattr(
        qa,
        "evaluate",
        lambda *args, **kwargs: question_answer.Evaluation(is_acceptable=True, feedback="ok"),
    )
    monkeypatch.setattr(
        qa,
        "lookup_news",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("lookup_news should not run when tool call is find_internet_articles.")
        ),
    )
    monkeypatch.setattr(
        qa,
        "find_internet_articles",
        lambda query: captured_queries.append(query) or "Search result corpus.",
    )

    streamed_output = list(qa.chat("Give me a broader context.", history=[]))

    assert captured_queries == ["latest AI chip export policy impacts"]
    assert streamed_output == ["Search-backed answer."]

    stream_call = next(call for call in create_calls if call.get("stream"))
    tool_messages = _tool_messages(stream_call["messages"])
    assert len(tool_messages) == 1
    tool_payload = json.loads(tool_messages[0]["content"])
    assert tool_payload["query"] == "latest AI chip export policy impacts"
    assert tool_payload["search_results"] == "Search result corpus."
