"""
presenter.py - News Presentation Agent

This agent handles fetching and presenting news articles to users. It provides
two main capabilities:
  1. Today's News - Fetches headlines across multiple categories (Top Headlines,
     Business, Tech, AI, Canada, China) from NewsAPI
  2. Custom Domain Search - Fetches articles on any user-specified topic

The presenter formats all output in clean Markdown with images for user to read.

"""

# configuration
import os
import json
import datetime
import requests
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv(override=True)

openai_api_key = os.getenv('OPENAI_API_KEY')
news_api_key = os.getenv('NEWS_API_KEY')
brave_api_key = os.getenv("BRAVE_API_KEY")

# Validate API keys on startup
if openai_api_key:
    print(f"OpenAI API Key exists and begins {openai_api_key[:8]}")
else:
    print("OpenAI API Key not set")

if news_api_key:
    print(f"NEWS API Key exists and begins {news_api_key[:8]}")
else:
    print("NEWS API Key not set")

if brave_api_key:
    print(f"Brave Search API Key exists and begins {brave_api_key[:8]}")
else:
    print("Brave Search API Key not set")

MODEL = "gpt-4o-mini"
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
        response = requests.get(url)
        formatted_json = json.dumps(response.json(), indent=2)
        today_news[category] = formatted_json
        print(f"Key: {category}")
        print(f"URL: {url}\n")


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

    urls = {
        f"{domain_name}": f"https://newsapi.org/v2/everything?q={domain_name}&from={cutoff_date}&sortBy=popularity&pageSize=4&language=en&apiKey={news_api_key}"
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


# System prompt

presenter_system_prompt = "You are a an helpful assistant who retreive news article from an API, and present them in an consistent, neat, and organlized markdown format to the user.\n"
presenter_system_prompt += "You can fluently report news in both English and Chinese. You respond in whichever language the user talks to you.\n"

presenter_system_prompt += "This is some information you need to know:\n"
presenter_system_prompt += "You have two responsibilities, 1) report on today's news, 2) report news on a custom domain\n"
presenter_system_prompt += "When reporting, you try to minimize your presence. You just deliver the news in the required format, and no greeting or goodbye should be shown.\n"

# Instructions for today's news reporting
presenter_system_prompt += "Here is what you do for responsibility 1) report on today's news"
presenter_system_prompt += "If user asked for today's news, call get_today_news.\n"
presenter_system_prompt += "You do not provide any greeting or ending, before or after summarizing the articles. If the user asked you in Chinese, you must respond in Chinese with the required markdown format. If the user asked you in English, you must respond in English with the required markdown format.\n"
presenter_system_prompt += "You summarize articles in these 6 category: Top headlines, Business, Tech, AI, Canada, China \n"
presenter_system_prompt += "For each category, please provide exactly two events, where each event has a relavant image along with it.\n"
presenter_system_prompt += "At the end of each category, insert a horizontal rule (`---`) on its own line to separate categories.\n"
presenter_system_prompt += "For example, if user said 'Tell me today's news\n'"
presenter_system_prompt += """ Then you use this Markdown format for each category:

# Top headlines

## Headline: G7 Leaders Conclude 2025 Summit in Italy
Summary: Leaders of the G7 nations wrapped up their annual summit in Apulia, Italy, with a strong focus on Ukraine aid, climate action, and regulating AI development.
Published: July 6, 2025 (The published date)
Source: [BBC News – G7 2025 Summit Highlights] (clickable reference link)
(include image in markdown here)
![G7 Summit](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/G7_Apulia_2025_Leaders.jpg/800px-G7_Apulia_2025_Leaders.jpg)


## Headline: EU Imposes Tariffs on Chinese Electric Vehicles
Summary: The European Union has enacted provisional tariffs on Chinese EVs, citing market distortion from state subsidies. China has threatened retaliation, escalating trade tensions.
Published: July 5, 2025
Source: Reuters – EU Tariffs on Chinese EVs (https://www.reuters.com/world/europe/eu-tariffs-chinese-evs-2025)
![EU-China EV Trade Tensions](https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/European_Union_and_China_flags.jpg/800px-European_Union_and_China_flags.jpg)

---
"""

presenter_system_prompt += "For example, if user said '告诉我今天的新闻'\n"
presenter_system_prompt += """

# 今日头条

## 标题：G7 领导人于意大利结束 2025 年峰会  
摘要：七国集团（G7）领导人在意大利阿普利亚举行的年度峰会上达成多项共识，重点围绕对乌克兰的持续援助、全球气候行动以及人工智能监管框架展开讨论。会议强调国际合作的重要性，以应对地缘政治与科技带来的新挑战。  
发布时间：2025 年 7 月 6 日  
来源：[BBC 新闻 – G7 2025 峰会要点](可点击引用链接)  
（在此处插入 Markdown 图片）  
![G7 峰会](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/G7_Apulia_2025_Leaders.jpg/800px-G7_Apulia_2025_Leaders.jpg)


## 标题：欧盟对中国电动车征收临时关税  
摘要：欧盟宣布对来自中国的电动车征收临时关税，理由是政府补贴导致市场竞争失衡。此举引发中国方面强烈反应，并警告将采取反制措施，令中欧贸易关系面临新的紧张局势。  
发布时间：2025 年 7 月 5 日  
来源：[路透社 – 欧盟对中国电动车征税](https://www.reuters.com/world/europe/eu-tariffs-chinese-evs-2025)  
![欧中电动车贸易摩擦](https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/European_Union_and_China_flags.jpg/800px-European_Union_and_China_flags.jpg)

---
"""

# Instructions for custom domain search
presenter_system_prompt += "\n\n\n Here is what you do for responsibility 2) report on custom domain"
presenter_system_prompt += "If user said ./ domain_name, call custom_domain_search.\n"
presenter_system_prompt += "You do not provide any greeting or ending, before or after summarizing the articles.\n"
presenter_system_prompt += "For custom searched domain, please try to report 4 articles, where each articles has a relavant image along with it.\n"
presenter_system_prompt += """Use this Markdown format for each category:
# {domain_name}

## Headline: G7 Leaders Conclude 2025 Summit in Italy
Summary: Leaders of the G7 nations wrapped up their annual summit in Apulia, Italy, with a strong focus on Ukraine aid, climate action, and regulating AI development.
Published: July 6, 2025 (The published date)
Source: [BBC News – G7 2025 Summit Highlights] (clickable reference link)
(include image in markdown here)
![G7 Summit](https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/G7_Apulia_2025_Leaders.jpg/800px-G7_Apulia_2025_Leaders.jpg)


## Headline: EU Imposes Tariffs on Chinese Electric Vehicles
Summary: The European Union has enacted provisional tariffs on Chinese EVs, citing market distortion from state subsidies. China has threatened retaliation, escalating trade tensions.
Published: July 5, 2025
Source: Reuters – EU Tariffs on Chinese EVs (https://www.reuters.com/world/europe/eu-tariffs-chinese-evs-2025)
![EU-China EV Trade Tensions](https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/European_Union_and_China_flags.jpg/800px-European_Union_and_China_flags.jpg)

---
"""

presenter_system_prompt += "\n\n\n The end goal is that you followed the format when reporting today's news and reporting on custom domain. It is important that if the user asks you in English, then you respond in English with markdown. If the user asks you in Chinese, you respond in Chinese with markdown.\n"


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

        # Generate the final formatted news presentation
        stream = openai.chat.completions.create(
            model=MODEL,
            messages=messages + [
                {"role": "system",
                 "content": "Use the tool result to craft the news in the required markdown format."}
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
