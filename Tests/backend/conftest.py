from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import openai
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

for candidate in (PROJECT_ROOT, BACKEND_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)


class _NoopCompletions:
    def create(self, *args, **kwargs):
        raise AssertionError("OpenAI completion call must be mocked in tests.")

    def parse(self, *args, **kwargs):
        raise AssertionError("OpenAI parse call must be mocked in tests.")


class DummyOpenAI:
    def __init__(self, *args, **kwargs):
        self.chat = SimpleNamespace(completions=_NoopCompletions())


MODULES_WITH_OPENAI_SINGLETONS = (
    "main",
    "question_answer",
    "question_answer_zh",
    "presenter",
    "presenter_zh",
)


@pytest.fixture
def load_project_module(monkeypatch):
    monkeypatch.setattr(openai, "OpenAI", DummyOpenAI)

    def _load(module_name: str):
        for name in MODULES_WITH_OPENAI_SINGLETONS:
            sys.modules.pop(name, None)
        return importlib.import_module(module_name)

    return _load


@pytest.fixture
def backend_main(load_project_module):
    module = load_project_module("main")
    module.NEWS_CACHE.clear()
    yield module
    module.NEWS_CACHE.clear()
