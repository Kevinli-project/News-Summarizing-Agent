"""
main.py - FastAPI backend for the News Feed app

Endpoints:
  GET  /           Health check
  GET  /api/news   Structured news cards (LLM-enhanced JSON)
  POST /api/chat   SSE streaming chat
"""

import sys
import os
import json
import time
import logging
import threading
from typing import Literal

# Add the project root (parent of backend/) to sys.path
# so we can import presenter/question_answer modules.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv
from openai import OpenAI
import presenter as pres
import presenter_zh as pres_zh
import question_answer as qa
import question_answer_zh as qa_zh

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(override=True)

openai_client = OpenAI()
MODEL = "gpt-4.1-mini"

app = FastAPI(title="News Feed API")

DEFAULT_CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
MAX_MESSAGE_CHARS = 4000
MAX_ASSISTANT_MESSAGE_CHARS = 16000
MAX_QUERY_CHARS = 200
MAX_HISTORY_ITEMS = 40

# ---------------------------------------------------------------------------
# In-memory cache for news cards (per language)
# ---------------------------------------------------------------------------

NEWS_CACHE: dict[str, dict] = {}
_cache_lock = threading.Lock()  # Lock to prevent concurrent refresh attempts

def parse_cors_origins() -> list[str]:
    """Parse comma-separated CORS origins from env."""
    raw = os.getenv("CORS_ORIGINS", "")
    if not raw:
        return DEFAULT_CORS_ORIGINS
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    # Keep only explicit http(s) origins; reject wildcard/empty entries.
    valid = [origin for origin in origins if origin.startswith(("http://", "https://"))]
    return valid or DEFAULT_CORS_ORIGINS


CORS_ORIGINS = parse_cors_origins()
logger.info("Configured CORS origins: %s", CORS_ORIGINS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# JSON schema for OpenAI structured outputs (strict mode)
# ---------------------------------------------------------------------------

NEWS_CARD_SCHEMA = {
    "name": "news_cards",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "categories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "articles": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "summary": {"type": "string"},
                                    "image": {
                                        "anyOf": [
                                            {"type": "string"},
                                            {"type": "null"},
                                        ]
                                    },
                                    "url": {"type": "string"},
                                    "source": {"type": "string"},
                                    "published": {"type": "string"},
                                },
                                "required": ["title", "summary", "image", "url", "source", "published"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["name", "articles"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["categories"],
        "additionalProperties": False,
    },
}


# ---------------------------------------------------------------------------
# System prompts for structured JSON card output
# ---------------------------------------------------------------------------

CARD_PROMPT_EN = """\
You are a news data processor. You receive raw NewsAPI JSON organized by category.
Your job is to select the best articles and output structured JSON for a news card UI.

## Rules

- For each category, select up to 2 of the most newsworthy articles.
- Skip any article whose title contains "[Removed]" or that is missing a title.
- Keep the original category ordering.

### Title style
- Make the article title more readable (e.g. break up long strings, avoid jargon where a plain word works) while still sounding like a news headline. Remove any trailing " - Source Name" suffix (e.g. " - BBC News"). Keep it concise.

### Summary style
- Assume the reader has no background knowledge. When mentioning people, briefly state who they are (e.g. "Musk (Tesla CEO)"); when mentioning events, briefly give context so anyone can understand what the article is about.

### Field mapping

| Output field | How to produce it |
|---|---|
| `title` | Use the article's `title`. Apply the title style above. |
| `summary` | Write a short card summary: 1–3 sentences, at most ~25 words. If `description` is long, condense it; if short or null, draft from `title` and `content`. Never paste long paragraphs. Follow the summary style above. |
| `image` | Use `urlToImage` directly. If null or empty, set to `null`. |
| `url` | Use `url` directly. |
| `source` | Use `source.name` directly. |
| `published` | Extract the date from `publishedAt` and format as "Mon DD, YYYY" (e.g. "Jul 6, 2025"). |

## Example

Given raw NewsAPI input for the "Top headlines" category, you would produce:

{
  "categories": [
    {
      "name": "Top headlines",
      "articles": [
        {
          "title": "G7 Leaders Conclude 2025 Summit in Italy",
          "summary": "Leaders of the G7 nations wrapped up their annual summit in Apulia, Italy, with a strong focus on Ukraine aid, climate action, and regulating AI development.",
          "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/G7_Apulia_2025_Leaders.jpg/800px-G7_Apulia_2025_Leaders.jpg",
          "url": "https://www.bbc.com/news/world-europe-g7-summit-2025",
          "source": "BBC News",
          "published": "Jul 6, 2025"
        },
        {
          "title": "EU Imposes Tariffs on Chinese Electric Vehicles",
          "summary": "The European Union has enacted provisional tariffs on Chinese EVs, citing market distortion from state subsidies. China has threatened retaliation, escalating trade tensions.",
          "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/European_Union_and_China_flags.jpg/800px-European_Union_and_China_flags.jpg",
          "url": "https://www.reuters.com/world/europe/eu-tariffs-chinese-evs-2025",
          "source": "Reuters",
          "published": "Jul 5, 2025"
        }
      ]
    }
  ]
}

Note how each title is clean (no " - BBC News" suffix), each summary is 1-3 informative sentences, and image/url/source/published come directly from the raw data.
"""

CARD_PROMPT_ZH = """\
你是一个新闻数据处理助手。你接收英文 NewsAPI 的原始 JSON 数据（按分类组织），
需要将内容翻译为中文并输出结构化 JSON，供新闻卡片 UI 使用。

## 翻译原则

- 准确传达原文的核心信息，但不需要逐字翻译。
- 用通顺自然的中文表达，让中文读者一看就能理解。
- 来源名称翻译为中文（如 BBC News → BBC新闻，Reuters → 路透社，The Guardian → 卫报，The Washington Post → 华盛顿邮报，CNN → CNN）。

### 标题规范
- 尽量不用标点符号，通过精简措辞来压缩含义。
- 用叠加短语的方式表达，去掉多余的虚词和连接词。
- 原标题太长时可以适当省略。
- 风格正式，像正规新闻编辑室出品。
- 在适当位置添加空格以提高可读性：例如："孟加拉大选首投结束 选民盼民主回归"（在"结束"和"选民"之间加空格）。

### 摘要规范
- 句子简单易懂，不要使用复杂的长句。
- 假设读者没有任何背景知识。提到人物时简要说明身份（如"马斯克（特斯拉CEO）"），提到事件时简要交代背景。
- 专有名词使用中文通用译名（Donald Trump → 特朗普，European Union → 欧盟，Federal Reserve → 美联储）。
- 遇到专业术语用简短括号注释（如"PMI（衡量经济活跃程度的指标）"）。

### 分类名称翻译
- Top headlines → 今日头条
- Business → 商业
- Tech → 科技
- AI → 人工智能
- Canada → 加拿大
- China → 中国

## 规则

- 每个分类选取最多 2 篇最有新闻价值的文章。
- 跳过标题包含 "[Removed]" 或缺失标题的文章。
- 保持原始分类顺序。

### 字段映射

| 输出字段 | 处理方式 |
|---|---|
| `title` | 将英文标题翻译为符合中文新闻标题规范的中文标题。去掉末尾的 " - 来源名"。 |
| `summary` | 写简短卡片摘要：1–3 句话，约 25 字以内。若 `description` 很长则压缩；若很短或为空则根据 `title` 和 `content` 撰写。不要照搬长段。 |
| `image` | 直接使用 `urlToImage`。如果为 null 或空，设为 `null`。 |
| `url` | 直接使用 `url`。 |
| `source` | 将 `source.name` 翻译为中文通用译名。 |
| `published` | 从 `publishedAt` 提取日期，格式为「YYYY年 M月 D日」（如「2025年 7月 5日」）。 |

## 示例

以下是 "Top headlines" 分类的期望输出样式：

{
  "categories": [
    {
      "name": "今日头条",
      "articles": [
        {
          "title": "G7领导人在意大利结束2025年峰会",
          "summary": "七国集团（G7）领导人在意大利阿普利亚的年度峰会上达成多项共识，重点讨论了对乌克兰的援助、全球气候行动以及人工智能监管。",
          "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/G7_Apulia_2025_Leaders.jpg/800px-G7_Apulia_2025_Leaders.jpg",
          "url": "https://www.bbc.com/news/world-europe-g7-summit-2025",
          "source": "BBC新闻",
          "published": "2025-07-06"
        },
        {
          "title": "欧盟对中国电动车 征收临时关税",
          "summary": "欧盟宣布对中国电动车征收临时关税，理由是政府补贴导致市场竞争失衡。中国方面表示将采取反制措施，中欧贸易关系面临新的紧张局势。",
          "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/European_Union_and_China_flags.jpg/800px-European_Union_and_China_flags.jpg",
          "url": "https://www.reuters.com/world/europe/eu-tariffs-chinese-evs-2025",
          "source": "路透社",
          "published": "2025-07-05"
        }
      ]
    }
  ]
}

注意示例中：标题简洁无标点，标题适当位置有空格,摘要假设读者无背景知识，来源名翻译为中文通用译名（BBC News → BBC新闻，Reuters → 路透社），image 和 url 直接来自原始数据。
"""


# ---------------------------------------------------------------------------
# Helper: fetch raw news and produce structured card JSON via LLM
# ---------------------------------------------------------------------------

def fetch_news_cards(lang: str = "en") -> dict:
    """
    Fetch news from NewsAPI, then ask the LLM to produce structured card JSON.

    For lang="zh", the LLM translates titles, summaries, source names, and
    category names into Chinese following journalistic conventions.
    """
    # Step 1: Fetch raw news from NewsAPI (always English source data)
    raw_news = pres.get_today_news()

    # Step 2: Pick the right prompt
    system_prompt = CARD_PROMPT_ZH if lang == "zh" else CARD_PROMPT_EN

    # Step 3: Ask LLM to produce structured JSON (strict schema enforcement)
    response = openai_client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_news},
        ],
        response_format={"type": "json_schema", "json_schema": NEWS_CARD_SCHEMA},
        temperature=0.2,
    )

    return json.loads(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Cache management functions
# ---------------------------------------------------------------------------

def refresh_cache_background(lang: str):
    """
    Background task to refresh the news cache for a given language.
    This runs asynchronously and updates the cache when complete.
    """
    try:
        logger.info(f"Background refresh started for lang={lang}")
        result = fetch_news_cards(lang)
        
        with _cache_lock:
            NEWS_CACHE[lang] = {
                "data": result,
                "fetched_at": time.time(),
                "is_refreshing": False,
            }
        logger.info(f"Background refresh completed for lang={lang}")
    except Exception as e:
        logger.error(f"Background refresh failed for lang={lang}: {e}", exc_info=True)
        # On failure, mark as not refreshing so future requests can try again
        with _cache_lock:
            if lang in NEWS_CACHE:
                NEWS_CACHE[lang]["is_refreshing"] = False


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_content_length_by_role(self):
        max_len = MAX_MESSAGE_CHARS if self.role == "user" else MAX_ASSISTANT_MESSAGE_CHARS
        if len(self.content) > max_len:
            raise ValueError(
                f"content too long for role '{self.role}' ({len(self.content)} > {max_len})"
            )
        return self


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)
    lang: Literal["en", "zh"] = "en"

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message cannot be empty")
        return value


class NewsSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    lang: Literal["en", "zh"] = "en"
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query cannot be empty")
        return value


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def health_check():
    return {"status": "ok"}


@app.get("/api/news")
def get_news(
    response: Response,
    background_tasks: BackgroundTasks,
    lang: str = Query("en"),
    refresh: bool = Query(False),
):
    """
    Return structured news card data. ?lang=en (default) or ?lang=zh.
    
    Uses in-memory cache with background refresh:
    - If cache exists: returns immediately and triggers background refresh for next user
    - If cache missing: does blocking fetch (user pays ~20s), stores result, returns it
    """
    if lang not in ("en", "zh"):
        raise HTTPException(status_code=400, detail="lang must be 'en' or 'zh'")

    # Prevent browser/CDN edge caches from pinning stale news responses.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    if refresh:
        logger.info("Forced refresh requested for lang=%s", lang)
        try:
            result = fetch_news_cards(lang)
            with _cache_lock:
                NEWS_CACHE[lang] = {
                    "data": result,
                    "fetched_at": time.time(),
                    "is_refreshing": False,
                }
            logger.info("Forced refresh completed for lang=%s", lang)
            return result
        except Exception as e:
            logger.error("Forced refresh failed for lang=%s: %s", lang, e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to fetch news: {e}")

    with _cache_lock:
        entry = NEWS_CACHE.get(lang)
        
        if entry is not None:
            # Cache exists: return immediately and trigger background refresh if not already refreshing
            logger.info(f"Cache hit for lang={lang}, returning cached data")
            
            if not entry.get("is_refreshing", False):
                entry["is_refreshing"] = True
                background_tasks.add_task(refresh_cache_background, lang)
                logger.info(f"Background refresh scheduled for lang={lang}")
            
            return entry["data"]
    
    # Cache missing: do blocking fetch (user pays the cost)
    logger.info(f"Cache miss for lang={lang}, doing blocking fetch")
    try:
        result = fetch_news_cards(lang)
        
        with _cache_lock:
            NEWS_CACHE[lang] = {
                "data": result,
                "fetched_at": time.time(),
                "is_refreshing": False,
            }
        
        logger.info(f"Blocking fetch completed for lang={lang}, cache updated")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch news for lang={lang}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch news: {e}")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    SSE streaming chat endpoint.

    Accepts { message, history, lang } and streams back text deltas as SSE events.
    Routes by lang: en -> question_answer, zh -> question_answer_zh (no router LLM).

    Event format:
      data: {"delta": "chunk of text"}   -- a new piece of the response
      data: [DONE]                        -- signals the stream is finished
      data: {"error": "message"}          -- if something goes wrong mid-stream
    """
    logger.info(
        "chat request lang=%s message_len=%s history_len=%s",
        request.lang,
        len(request.message),
        len(request.history),
    )

    def event_generator():
        prev = ""
        yield_count = 0
        try:
            history = [turn.model_dump() for turn in request.history]
            stream = qa_zh.chat(request.message, history) if request.lang == "zh" else qa.chat(request.message, history)
            for accumulated in stream:
                delta = accumulated[len(prev):]
                if delta:
                    yield_count += 1
                    yield {"data": json.dumps({"delta": delta}, ensure_ascii=False)}
                prev = accumulated
            logger.info("chat stream finished yield_count=%s total_len=%s", yield_count, len(prev))
            yield {"data": "[DONE]"}
        except Exception as e:
            logger.exception("chat stream error: %s", e)
            yield {"data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


@app.post("/api/news-search")
async def news_search(request: NewsSearchRequest):
    """
    SSE streaming endpoint for news search.
    
    Accepts { query, lang, history } and streams back markdown-formatted news articles.
    Uses presenter's LLM agent flow: formats message as "./ {query}" to trigger custom_domain_search tool.
    Routes by lang: en -> presenter.chat(), zh -> presenter_zh.chat().
    
    The presenter's LLM handles:
    - Translation (Chinese queries -> English for NewsAPI -> Chinese results)
    - Tool call (custom_domain_search)
    - Formatting (raw NewsAPI -> markdown summaries)
    
    Event format:
      data: {"delta": "chunk of text"}   -- a new piece of the response
      data: [DONE]                        -- signals the stream is finished
      data: {"error": "message"}          -- if something goes wrong mid-stream
    """
    # Format message as "./ {query}" to trigger presenter's custom_domain_search tool
    message = f"./ {request.query}"
    
    logger.info(
        "news-search request lang=%s query=%s",
        request.lang,
        request.query[:50] if len(request.query) > 50 else request.query,
    )

    def event_generator():
        prev = ""
        yield_count = 0
        try:
            # Route by lang: presenter.chat() or presenter_zh.chat()
            # Pass empty history since presenter is stateless
            stream = pres_zh.chat(message, []) if request.lang == "zh" else pres.chat(message, [])
            
            for accumulated in stream:
                # Convert accumulated chunks to deltas (same pattern as /api/chat)
                delta = accumulated[len(prev):]
                if delta:
                    yield_count += 1
                    yield {"data": json.dumps({"delta": delta}, ensure_ascii=False)}
                prev = accumulated
            
            logger.info("news-search stream finished yield_count=%s total_len=%s", yield_count, len(prev))
            yield {"data": "[DONE]"}
        except Exception as e:
            logger.exception("news-search stream error: %s", e)
            yield {"data": json.dumps({"error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())
