"""
presenter_zh.py - Chinese News Presentation Agent

Same logic as presenter.py, but system prompt tells LLM to translate
English articles to Chinese accurately.

This agent handles fetching and presenting news articles to users in Chinese.
It provides two main capabilities:
  1. Today's News - Fetches headlines across multiple categories from NewsAPI
  2. Custom Domain Search - Fetches articles on any user-specified topic

The presenter translates all English content to clean Chinese Markdown.

"""

# configuration
import os
import json
import datetime
import requests
from urllib.parse import quote_plus
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv(override=True)

openai_api_key = os.getenv('OPENAI_API_KEY')
news_api_key = os.getenv('NEWS_API_KEY')
brave_api_key = os.getenv("BRAVE_API_KEY")

# Validate API keys on startup without exposing secret prefixes in logs
if not openai_api_key:
    print("OpenAI API Key not set")
if not news_api_key:
    print("NEWS API Key not set")
if not brave_api_key:
    print("Brave Search API Key not set")

MODEL = "gpt-4.1-mini"
openai = OpenAI()

# Storing fetched news articles
today_news = {}


# Helper functions

def extract_news(urls: dict) -> None:
    """
    Fetch news articles from multiple NewsAPI endpoints and cache them.
    
    Args:
        urls: Dictionary mapping category names to NewsAPI URLs
    """
    today_news.clear()
    
    for category, url in urls.items():
        response = requests.get(url, timeout=15)
        if response.status_code >= 400:
            raise RuntimeError(
                f"News API request failed for category '{category}' with status {response.status_code}"
            )
        formatted_json = json.dumps(response.json(), indent=2)
        today_news[category] = formatted_json
        print(f"Fetched category: {category}")


def get_today_news() -> str:
    """
    Fetch today's news across all predefined categories.
    
    Retrieves articles from: Top Headlines, Business, Tech, AI, Canada, and China.
    Uses a 2-day lookback window for trending/recent content.
    
    Returns:
        Formatted string containing all news articles organized by category
    """
    print("Tool get_today_news called!")
    
    # Use 2-day window for recent/trending content
    cutoff_date = (datetime.datetime.utcnow().date() - datetime.timedelta(days=2)).isoformat()

    urls = {
        "Top headlines": f'https://newsapi.org/v2/top-headlines?country=us&pageSize=5&apiKey={news_api_key}',
        "Business": f'https://newsapi.org/v2/top-headlines?category=business&pageSize=3&apiKey={news_api_key}',
        "Tech": f"https://newsapi.org/v2/top-headlines?category=technology&pageSize=3&language=en&apiKey={news_api_key}",
        "AI": f"https://newsapi.org/v2/everything?q=artificial%20intelligence&sortBy=publishedAt&pageSize=3&language=en&apiKey={news_api_key}",
        "Canada": f'https://newsapi.org/v2/top-headlines?sources=cbc-news&pageSize=3&apiKey={news_api_key}',
        "China": f"https://newsapi.org/v2/everything?q=China&from={cutoff_date}&sortBy=popularity&pageSize=4&language=en&apiKey={news_api_key}"
    }

    extract_news(urls)

    # Format all categories into a single response string
    all_contents = ""
    for category, contents in today_news.items():
        all_contents += f'Category:{category}\n'
        all_contents += contents
        all_contents += "\n\n\n"
    return all_contents


def custom_domain_search(domain_name: str) -> str:
    """
    Search for news articles on a specific topic/domain.
    
    Args:
        domain_name: The topic to search for (e.g., "climate change", "AI regulation")
        
    Returns:
        Formatted string containing relevant articles for the domain
    """
    print(f"Tool custom_domain_search called!")
    
    # Use 5-day window for custom searches
    cutoff_date = (datetime.datetime.utcnow().date() - datetime.timedelta(days=5)).isoformat()

    safe_domain = quote_plus(domain_name)
    urls = {
        domain_name: f"https://newsapi.org/v2/everything?q={safe_domain}&from={cutoff_date}&sortBy=popularity&pageSize=4&language=en&apiKey={news_api_key}"
    }

    extract_news(urls)

    all_contents = ""
    for category, contents in today_news.items():
        all_contents += f'Category:{category}\n'
        all_contents += contents
        all_contents += "\n\n\n"
    return all_contents




# Tool schema for fetching today's news
news_function = {
    "name": "get_today_news",
    "description": "Receive Today's news in json format. Call this function when you need to know today's news",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False
    }
}

# Tool schema for custom topic search
custom_domain_search_function = {
    "name": "custom_domain_search",
    "description": "Fetch 4 relevant news of a custom domain. Call this function when you see ./ domain_name",
    "parameters": {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "The custom domain name"
            }
        },
        "required": ["domain"]
    }
}

# Combined tools list for the presenter agent
presenter_tools = [
    {"type": "function", "function": news_function},
    {"type": "function", "function": custom_domain_search_function},
]


def handle_tool_call(message) -> list:
    """
    Execute tool calls requested by the LLM and format the results.
    
    Args:
        message: The assistant message containing tool_calls
        
    Returns:
        List of tool response messages ready to append to the conversation
    """
    tool_calls = message.tool_calls
    results = []
    
    for tool_call in tool_calls:
        if tool_call.function.name == "get_today_news":
            summary = get_today_news()
            response = {
                "role": "tool",
                "content": json.dumps({"summary": summary}),
                "tool_call_id": tool_call.id
            }
        elif tool_call.function.name == "custom_domain_search":
            arguments = json.loads(tool_call.function.arguments)
            domain_name = arguments.get("domain")
            summary = custom_domain_search(domain_name)
            response = {
                "role": "tool",
                "content": json.dumps({"Domain_name": domain_name, "summary": summary}),
                "tool_call_id": tool_call.id
            }
        else:
            continue
            
        results.append(response)
    return results


# CHANGED - System prompt: Chinese translation focused

presenter_system_prompt = """你是一位中文新闻播报助手。你会从英文新闻API获取数据，然后将内容准确地翻译为中文呈现给用户。

## 翻译原则

- 准确传达原文的核心信息，但不需要逐字翻译
- 用通顺自然的中文表达，让中文读者一看就能理解
- 来源名称翻译为中文（如 BBC News -> BBC新闻，Reuters -> 路透社）
- 保留原文的来源链接
- 标题要符合中文新闻标题的写法规范：
  - 尽量不用标点符号，通过精简措辞来压缩含义，去掉多余的虚词和连接词
  - 用叠加短语的方式表达，而不是用逗号分隔
  - 原标题太长时，可以适当省略
  - ？和！仅在语气确实需要时才使用，保持标题视觉上的简洁紧凑
  - 风格正式，像正规新闻编辑室出品
  - 例如：英文 "EU Imposes Tariffs on Chinese EVs, China Warns of Retaliation" → 写 "欧盟对中国电动车征收临时关税"
- 摘要要符合中文新闻摘要的写法规范：
  - 句子简单易懂，不要使用复杂的长句
  - 摘要中假设读者没有任何背景知识。如果提到某个人物，简要说明他是谁（如"马斯克（特斯拉CEO）"）。如果提到某个事件，简要交代背景（如"此前欧盟已多次对中国电动车展开反补贴调查"）
  - 专有名词使用中文通用译名（如 Donald Trump -> 特朗普，European Union -> 欧盟，Federal Reserve -> 美联储）
  - 如果遇到专业术语，用简短的括号注释解释（如 "PMI（衡量经济活跃程度的指标）"）

## 你的职责

你有两个职责：1）播报今日新闻 2）播报自定义主题新闻
播报时不需要任何开场白或结束语，直接按格式呈现。

## 职责一：播报今日新闻

当用户要求看今日新闻时，调用 get_today_news。
按以下6个分类呈现：今日头条、商业、科技、人工智能、加拿大、中国
每个分类提供两条新闻，每条附带一张相关图片。
每个分类结束后插入分隔线（`---`）。

使用以下Markdown格式：

# 今日头条

## 标题：G7领导人在意大利结束2025年峰会
摘要：七国集团（G7）领导人在意大利阿普利亚的年度峰会上达成多项共识，重点讨论了对乌克兰的援助、全球气候行动以及人工智能监管。
发布时间：2025年7月6日
来源：[BBC新闻 - G7 2025峰会要点](可点击引用链接)
![G7峰会](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/G7_Apulia_2025_Leaders.jpg/800px-G7_Apulia_2025_Leaders.jpg)


## 标题：欧盟对中国电动车征收临时关税
摘要：欧盟宣布对中国电动车征收临时关税，理由是政府补贴导致市场竞争失衡。中国方面表示将采取反制措施，中欧贸易关系面临新的紧张局势。
发布时间：2025年7月5日
来源：[路透社 - 欧盟对中国电动车征税](https://www.reuters.com/world/europe/eu-tariffs-chinese-evs-2025)
![欧中电动车贸易摩擦](https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/European_Union_and_China_flags.jpg/800px-European_Union_and_China_flags.jpg)

---


## 职责二：播报自定义主题新闻

当用户输入 ./ 主题名 时，调用 custom_domain_search。
重要：custom_domain_search 只能搜索英文关键词。如果用户输入的是中文主题，你必须先将主题翻译为对应的英文词，再传入函数。
例如：
- 用户输入 ./ 人工智能 → 调用 custom_domain_search(domain="artificial intelligence")
- 用户输入 ./ 电动车 → 调用 custom_domain_search(domain="electric vehicles")
- 用户输入 ./ 俄乌战争 → 调用 custom_domain_search(domain="Russia Ukraine war")
- 用户输入 ./ climate change → 直接调用 custom_domain_search(domain="climate change")

不需要开场白。呈现4条相关新闻，每条附带一张相关图片。
在列完主题新闻后，最后加上一句引导语：想看更深入解读？请直接在聊天框问我上面任意一篇。
格式规则（严格）：每条新闻的“摘要：”“发布时间：”“来源：”必须各占一行。


使用以下Markdown格式：

# {主题名}

## 标题：（准确翻译为通顺的中文标题）
摘要：（准确翻译为通顺的中文摘要）
发布时间：（原文发布日期）
来源：[中文来源名](原文链接)
![图片描述](图片链接)

---


## 最终目标

你必须始终用中文回复。核心目标是让中文读者能够准确理解每条新闻的内容。

重要：不要编造或虚构新闻。只报道工具/API 实际返回的文章。若工具返回少于4条，只呈现这些；切勿杜撰其他文章。
"""


# Main chat handler

def chat(message: str, history: list) -> str:

    messages = [
        {"role": "system", "content": presenter_system_prompt}
    ] + history + [
        {"role": "user", "content": message}
    ]

    # Phase 1: Probe to check if the LLM wants to call a tool
    probe = openai.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=presenter_tools,
    )
    assistant_msg = probe.choices[0].message

    # Phase 2A: Tool path - Execute tools and generate response
    if getattr(assistant_msg, "tool_calls", None):
        results = handle_tool_call(assistant_msg)

        messages.append(assistant_msg)
        messages.extend(results)

        # CHANGED: Phase 2A system message is in Chinese
        stream = openai.chat.completions.create(
            model=MODEL,
            messages=messages + [
                {"role": "system",
                 "content": (
                     "请将获取到的英文新闻准确翻译为中文，按要求的Markdown格式呈现。\n"
                     "每条新闻必须严格按以下顺序分行：\n"
                     "1）`## 标题：...`\n"
                     "2）`摘要：...`\n"
                     "3）`发布时间：...`\n"
                     "4）`来源：...`\n"
                     "5）图片Markdown行\n"
                     "绝对不要把“发布时间：”或“来源：”和“摘要：”写在同一行。\n"
                     "输出前请自检，若不符合则先改写再输出。"
                 )}
            ],
            stream=True
        )

        partial = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.model_dump(exclude_none=True)
            if delta.get("content"):
                partial += delta["content"]
                # Flush on paragraph boundaries for smoother UI updates
                if partial.endswith("\n\n"):
                    yield partial
        if partial:
            yield partial
        return

    # Phase 2B: No-tool path - Direct response without fetching news
    stream = openai.chat.completions.create(
        model=MODEL,
        messages=messages,
        stream=True
    )

    partial = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.model_dump(exclude_none=True)
        if delta.get("content"):
            partial += delta["content"]
            if partial.endswith("\n\n"):
                yield partial
    if partial:
        yield partial
