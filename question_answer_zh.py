"""
question_answer_zh.py - Chinese Q&A Agent (小Lin说 style)

Same logic as question_answer.py, with changes to:
1. QA system prompt - Chinese, 小Lin说 personality
2. find_internet_articles tool - tells LLM to translate Chinese to English queries
3. Phase 2A system message - Chinese

"""

# configuration

import os
import json
import datetime
import asyncio
import requests
import aiohttp
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from openai import OpenAI
from pydantic import BaseModel


load_dotenv(override=True)

openai_api_key = os.getenv('OPENAI_API_KEY')
news_api_key = os.getenv('NEWS_API_KEY')
brave_api_key = os.getenv("BRAVE_API_KEY")

if not openai_api_key:
    print("OpenAI API Key not set")
if not news_api_key:
    print("NEWS API Key not set")
if not brave_api_key:
    print("Brave Search API Key not set")

MODEL = "gpt-4.1-mini"

# Standard browser headers to avoid being blocked by websites
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/117.0.0.0 Safari/537.36"
}


# Pydantic, structured outputs for the evaluator

class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str

# Utility class for fetching and parsing web page content
class Website:
    """
    A utility class to represent a Website that we have scraped.
    
    Uses async for fetching:
    - __init__ only stores data (no fetching)
    - fetch() is an async class method that does the actual work
    - Use: site = await Website.fetch(session, url)
    """

    def __init__(self, url: str, title: str, text: str, links: list):
        """Store pre-fetched data. Don't call directly - use fetch()."""
        self.url = url
        self.title = title
        self.text = text
        self.links = links

    @staticmethod
    def _parse_html(html: str):
        """Parse HTML content into title, text, and links."""
        soup = BeautifulSoup(html, 'html.parser')
        title = soup.title.string if soup.title else "No title found"
        
        if soup.body:
            for irrelevant in soup.body(["script", "style", "img", "input"]):
                irrelevant.decompose()
            text = soup.body.get_text(separator="\n", strip=True)
        else:
            text = ""
        
        links = [link.get('href') for link in soup.find_all('a')]
        links = [link for link in links if link]
        
        return title, text, links

    @classmethod
    async def fetch(cls, session, url: str, timeout: int = 10):
        """Async factory method - fetches URL and returns a Website instance."""
        try:
            async with session.get(url, headers=HTTP_HEADERS, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                response.raise_for_status()
                html = await response.text()
            
            title, text, links = cls._parse_html(html)
            return cls(url, title, text, links)
        
        except Exception as e:
            print(f"[Website] Error fetching {url}: {e}")
            raise

    def get_contents(self) -> str:
        """Return formatted page title and content."""
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text}\n\n"


# Async helpers for parallel fetching

async def _fetch_websites_parallel(urls: list, timeout: int = 10) -> list:
    """Fetch multiple URLs in parallel using Website.fetch()."""
    async with aiohttp.ClientSession() as session:
        tasks = [_fetch_one_safe(session, url, timeout) for url in urls]
        return await asyncio.gather(*tasks)


async def _fetch_one_safe(session, url: str, timeout: int = 10):
    """Fetch one URL using Website.fetch(), with error handling."""
    try:
        site = await Website.fetch(session, url, timeout)
        return {"site": site, "error": None}
    except Exception as e:
        return {"site": None, "error": str(e), "url": url}


async def _lookup_news_async(url: str) -> str:
    """Async helper for lookup_news - fetches a single URL."""
    async with aiohttp.ClientSession() as session:
        site = await Website.fetch(session, url, timeout=10)
        return site.get_contents()


# Chinese Answering Agent class

class QA:
    """
    Chinese Question-Answering agent (小Lin说 style).
    
    Same architecture as the English QA class, with:
    - Chinese system prompt (小Lin说 personality)
    - find_internet_articles tool tells LLM to translate Chinese queries to English
    - Phase 2A system message in Chinese
    """

    # Known paywalled sources that require alternative approaches
    PAYWALLED_SOURCES = {
        "The New York Times",
        "The Washington Post",
        "The Wall Street Journal"
    }

    def __init__(self):
        """Initialize the QA agent with tools, prompts, and API clients."""
        self.openai = OpenAI()
        self.brave_api_key = brave_api_key

        # Define available tools
        self._setup_tools()
        
        # Build system prompts
        self._setup_prompts()

    def _setup_tools(self):
        """Configure the OpenAI function calling schemas."""
        self.website_function = {
            "name": "visit_website",
            "description": (
                "Visit a website to fetch its HTML to answer client's question. "
                "Call this function when client asked you for more information "
                "about a particular article. "
                f"However, Do NOT call this tool for pay-walled news sources such as: "
                f"{', '.join(self.PAYWALLED_SOURCES)}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The correct URL from the source section"
                    }
                },
                "required": ["url"]
            }
        }

        # CHANGED: Added instruction to translate Chinese queries to English
        self.find_internet_articles_function = {
            "name": "find_internet_articles",
            "description": (
                "Perform internet search on the query, and retrieve 3 relevant "
                "news articles to answer user's question. "
                "Call this tool when you need further comprehensive information. "
                "IMPORTANT: The search engine only works with English queries. "
                "If the user's question is in Chinese, you MUST translate it to an English query before calling this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query, must be in English"
                    }
                },
                "required": ["query"]
            }
        }

        self.QA_tools = [
            {"type": "function", "function": self.website_function},
            {"type": "function", "function": self.find_internet_articles_function},
        ]

    def _setup_prompts(self):
        """Build the system prompts for the QA agent and evaluator."""
        
        # CHANGED: Chinese system prompt with 小Lin说 personality
        self.QA_system_prompt = """你是一位模仿「小Lin说」风格的中文新闻解读助手。你的任务是用中文向用户解释新闻事件。

你的数据源是英文新闻。你需要将获取到的英文内容消化理解后，用小Lin说的风格向用户解释。

## 小Lin说的风格规则

语言风格：
- 用大白话讲复杂的事情，不用术语，如果必须用就立刻解释（比如"PMI——简单说就是衡量经济活不活跃的指标"）
- 句子短，一句话一个意思
- 善于用生活化的比喻（"这就好比你家楼下的超市突然涨价了，你自然会少买一点"）
- 偶尔带一点幽默感和亲切感
- 充满活力， 让用户在轻松的氛围中了解新闻

表达习惯：
- 喜欢用"简单来说"、"换句话说"、"说白了就是"来过渡
- 会说"这件事为什么重要呢？"来引导读者思考
- 善用结构化表达："发生了什么 / 为什么重要 / 接下来会怎样"
- 经常说"我们来看看"、"我们来聊聊"，有互动感
- 结尾经常用一句话总结，让人觉得"哦，原来是这么回事"

背景解释：
- 假设用户对新闻事件没有任何背景知识
- 提到人物时简要说明身份（如"马斯克，就是特斯拉和SpaceX的老板"）
- 提到事件时简要交代来龙去脉
- 用数据时要联系到普通人的生活（"涨了10%，意味着你每个月可能要多花好几百块"）

## 你有两个工具可以使用

1) visit_website - 访问一个网页获取内容
2) find_internet_articles - 在互联网搜索相关文章

重要：这两个工具获取的都是英文内容。你需要理解英文内容后，用中文小Lin说风格向用户解释。

### 关于 visit_website
- 这个工具速度快，适合用户只是想大概了解某篇文章讲了什么
- 不能用于付费墙新闻源（如 The New York Times, The Washington Post, The Wall Street Journal）
- 遇到付费墙来源，必须用 find_internet_articles 代替

### 关于 find_internet_articles
- 这个工具速度较慢，但信息更全面
- 以下情况使用：
  1) 用户想深入了解某个事件的详细情况
  2) 文章来自付费墙来源
  3) 用户用 @ 触发
- 重要：搜索引擎只支持英文。如果用户用中文提问，你必须将问题翻译为英文作为 query 参数

## 回答格式

用以下结构回答：

## 发生了什么
（简要说明事件）

## 为什么重要
（解释影响和意义）

## 背景
（交代来龙去脉）

## 接下来会怎样
（未来影响和展望）

## 你还应该知道的
（补充信息）

参考来源：
1) [来源名 - 文章标题](链接URL)


比如： 
用户问：跟我讲讲美联储突然"踩刹车"的新闻？

你可以这样回答：

## 美联储突然"踩刹车"：2026年的第一场货币悬疑剧
哈喽大家好，我是小Lin！

今天要跟大家聊一个金融界的"大消息"。如果你最近在关注自己的房贷、车贷，或者发现手里的股票波动有点大，那接下来的内容你一定要听。我们要聊的主角，就是那个掌握着全球"钱袋子"阀门的机构——**美联储**（简单说，就是美国的中央银行，全世界最有钱的"家长"）。



## 一、 发生了什么？
简单来说，美联储刚刚开了个会，决定**维持利率不变**。

目前的利率水平在 **3.5% 到 3.75%** 之间。
* **动作：** 停下了去年连续降息的脚步。
* **状态：** 观察。

这就好比你家楼下的超市，之前几个月一直在搞"大促销"降价，大家都以为本月还要再便宜五毛钱，结果老板突然把价格牌收起来了，说："先不降了，我得看看隔壁老王家是不是还要涨价。"



## 二、 这件事为什么重要呢？
因为美联储的每一个动作，都直接影响到你口袋里的钱：

1. **借钱的成本：** 利率不降，意味着如果你想贷款买房或者买车，利息暂时不会再变便宜了。
2. **股市的脸色：** 华尔街的那些投资大佬们原本都在欢呼"快降息！快撒钱！"，结果美联储这一停，大家的热情就被泼了一盆冷水，股市自然会有点"小情绪"。
3. **经济的信号：** 美联储不降息，说明他们觉得现在的通货膨胀（就是物价上涨）还是有点"黏人"，像粘在鞋底的口香糖，甩不掉。



## 三、 我们来看看背景
我们要先认识一个人：**鲍威尔**，也就是美联储的主席，金融圈的"总舵手"。

* **去年的剧本：** 2025年下半年，因为经济有点疲软，美联储连续降了三次息，大家本来都习惯了这种"发红包"的节奏。
* **现在的纠结：** 现在的美国经济处于一个很尴尬的阶段：一方面，大家找工作好像没以前那么容易了；另一方面，买东西还是贵。
* **美联储的逻辑：**说白了，美联储现在的核心逻辑就是在"保增长"和"压物价"之间找平衡。如果利息降得太快，物价可能又会反弹，到时候想压都压不住；但如果一直维持高利息，企业借钱太贵，大家可能就要面临失业。所以，鲍威尔现在选择了最稳妥的做法：先停下来，看看最新的经济数据到底怎么走，再做下一步决定。



## 四、 展望：接下来会怎样？
这件事最精彩的部分在于，**鲍威尔的任期在今年 5 月就要结束了！**

1. **"老司机"要退休：** 鲍威尔在 5 月份就要光荣退休了。换个新老板，美联储的脾气可能会大变。
2. **下次降息什么时候？** 市场现在预测，下一次"发红包"可能要等到 6 月份左右了。
3. **不确定性：** 现在的感觉就是大家都在等一个信号。如果物价能听话一点降下来，那下半年我们可能还能见到利率再降一点。



**一句话总结：美联储觉得现在的物价还没彻底"老实"，所以决定先按住降息的按钮，等 5 月换了新老板再说！**
怎么样，是不是觉得这些高大上的金融词汇其实也就那么回事？如果你还想了解更多关于**全球贸易战**或者**AI如何改变我们钱包**的内容，记得告诉我哦！



## 一般流程

通常的使用流程是：先有新闻呈现给用户，用户会问关于某条新闻的问题。
- 一般性的问题，调用 visit_website 就够了（如果不是付费墙来源）
- 如果是付费墙来源，必须调用 find_internet_articles
- 如果用户想深入了解，或者问题本身很复杂，用 find_internet_articles 获取更全面的信息
- 结合搜索结果和之前的对话内容来回答，不要把每次提问当成独立的问题
- 如果使用了来源，在最后用Markdown可点击链接格式列出参考来源，如 [来源名 - 文章标题](URL)。如果没有使用来源，不要编造

## 最终目标

你必须始终用中文回复，始终保持小Lin说的风格。让用户感觉像在听一个聪明的朋友给自己讲新闻。
"""

        # Evaluator prompt (stays English - internal use only)
        self.evaluator_system_prompt = (
            f"You are an evaluator that decides whether the LLM's list of tool calls are acceptable. "
            f"You are provided the Agent's tool call decision. Your task is to decide whether the Agent's tool call decision breaks any rule. "
            f"The Agent is playing the role of news reporter and is explaining the news to the user. "
            f"The Agent has been provided two tool calls available. 1) visit_website, and 2) find_internet_articles.\n"
            f"The Agent has been instructed NOT to call visit_website on any pay-walled news source such as: "
            f"{', '.join(self.PAYWALLED_SOURCES)} or any other known pay-walled news source.\n"
            f"Instead, the Agent should call the tool find_internet_articles with a modified query variable to search the internet on this topic.\n"
            f"With this context, paying attention to the website link, please evaluate the list of tool call decisions, "
            f"replying if any of the tool-calls broke the rule, and specify find_internet_articles should be used for those as your feedback."
        )

 # Tool implementation methods

    def lookup_news(self, url: str) -> str:
        """
        Fetch and extract content from a news article URL.
        Uses async internally for consistency with find_internet_articles.
        """
        print(f"Tool visit_website called!")
        try:
            result = asyncio.run(_lookup_news_async(url))
            return result
        except Exception:
            return f"This website {url} cannot be fetched, possibly because it is paywalled."

    def brave_news_search_filtered_strict(
        self,
        query: str,
        count: int = 10,
        offset: int = 0,
        search_lang: str = "en",
    ) -> dict:
        """
        Search for news articles using the Brave Search API.
        
        Filters results to only include actual news articles (type: "news_result").
        """
        url = "https://api.search.brave.com/res/v1/news/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.brave_api_key,
        }
        params = {
            "q": query,
            "count": count,
            "offset": offset,
            "search_lang": search_lang,
        }
        
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        # Filter to only actual news results
        results = data.get("results", [])
        filtered = [r for r in results if r.get("type") == "news_result"]
        data["results"] = filtered
        
        return data

    def get_links(self, query: str) -> dict:
        """
        Use LLM to select the best articles from search results.
        
        Searches Brave, then asks GPT to pick the 3 most relevant non-paywalled
        articles from trusted sources.
        """
        link_system_prompt = (
            "You are provided with a list of articles in json format related to a query. "
            "You are able to decide which of the 3 articles is most relevant to user's query. "
            f"Do not pick articles from pay-walled sources such as:\n"
            f"{', '.join(self.PAYWALLED_SOURCES)}\n"
            "Please preferably choose articles from well known trusted source like BBC News, CBC News, "
            "TIME magazine.\n"
        )
        link_system_prompt += "You should respond in JSON as in this example:\n"
        link_system_prompt += """
        {
            "links": [
                {"title": "Trump says Israel, Hamas signed off on first phase of Gaza deal", "url": "https://www.reuters.com/world/middle-east/trump-says-israel-hamas-signed-off-gaza-deal-2025-10-08/"},
                {"title": "Israel and Hamas Have Agreed to the 'First Phase' of a Peace Deal. Here's What We Know", "url": "https://time.com/7324580/gaza-deal-israel-hamas-trump-netanyahu-palestine-hostages/"}
            ]
        }
        """

        user_prompt = f"Here is the user's query: {query} \n\n For context, the current date is {datetime.datetime.utcnow().date()}\n"
        user_prompt += (
            f"Please choose 3 of the following articles which are most relevant to what user is asking for. \n"
            "Please try to pick articles from a well known trusted source\n"
            f"It is mandatory that You NOT pick any articles from pay-walled sources such as:\n"
            f"{', '.join(self.PAYWALLED_SOURCES)}\n"
            "Please respond in JSON format.\n\n"
        )

        news_results = self.brave_news_search_filtered_strict(query, count=8)
        news_json = json.dumps(news_results, indent=2)
        user_prompt += news_json

        response = self.openai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": link_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        
        result = response.choices[0].message.content
        return json.loads(result)

    def find_internet_articles(self, query: str) -> str:
        """
        Search the internet and compile content from multiple articles.
        Now fetches all URLs in parallel using async for ~3x speedup.
        """
        news_data = self.get_links(query)
        links = news_data.get("links", [])
        summary = f"The user's question is: {query}\n\n"
        
        # Extract URLs and fetch ALL in parallel
        urls = [link.get("url") for link in links if link.get("url")]
        results = asyncio.run(_fetch_websites_parallel(urls))
        
        # Build summary from results (order is preserved)
        for link, result in zip(links, results):
            title = link.get("title", "No title")
            url = link.get("url", "No URL")
            summary += "Here is one relevant article\n"
            summary += f"Title of this article is: {title}\n"
            summary += f"URL: {url}\n"
            
            if result["error"] is not None or result["site"] is None:
                summary += f"This website {url} cannot be fetched: {result.get('error', 'Unknown error')}\n"
            else:
                summary += result["site"].get_contents()
            
            summary += "-" * 50 + "\n"
            
        return summary

    def handle_tool_call(self, message) -> list:
        """
        Execute tool calls and return formatted results.
        """
        tool_calls = message.tool_calls
        results = []
        
        for tool_call in tool_calls:
            if tool_call.function.name == "visit_website":
                arguments = json.loads(tool_call.function.arguments)
                url = arguments.get("url")
                web_content = self.lookup_news(url)
                response = {
                    "role": "tool",
                    "content": json.dumps({"url": url, "web_content": web_content}),
                    "tool_call_id": tool_call.id,
                }
            elif tool_call.function.name == "find_internet_articles":
                arguments = json.loads(tool_call.function.arguments)
                query = arguments.get("query")
                search_results = self.find_internet_articles(query)
                response = {
                    "role": "tool",
                    "content": json.dumps(
                        {"query": query, "search_results": search_results}
                    ),
                    "tool_call_id": tool_call.id,
                }
            else:
                continue
            results.append(response)
            
        return results


# Evaluator methods
    def _evaluator_user_prompt(self, reply, message: str, history: list) -> str:
        user_prompt = f"Here's the conversation between the User and the Agent: \n\n{history}\n\n"
        user_prompt += f"Here's the latest message from the User: \n\n{message}\n\n"
        user_prompt += f"Here's the latest response from the Agent: \n\n{reply}\n\n"
        user_prompt += "Please evaluate the response, replying with whether it is acceptable and your feedback."
        return user_prompt

    def evaluate(self, reply, message: str, history: list) -> Evaluation:
        """
        Evaluate whether the agent's tool call decision is acceptable.
        """
        print("Evaluating tool call decision...")
        messages = [
            {"role": "system", "content": self.evaluator_system_prompt},
            {"role": "user", "content": self._evaluator_user_prompt(reply, message, history)}
        ]
        response = self.openai.chat.completions.parse(
            model=MODEL,
            messages=messages,
            response_format=Evaluation
        )
        return response.choices[0].message.parsed

    def rerun(self, reply, message: str, history: list, feedback: str):
        """
        Re-run the agent with feedback about why the previous attempt was rejected.
        
        Adds the rejected attempt to conversation history so the LLM can see what it tried before.
        """
        updated_system_prompt = self.QA_system_prompt + "\n\n## Previous answer rejected\nYou just tried to reply, but the quality control rejected your reply.\n"
        updated_system_prompt += f"## Your attempted answer:\n{reply}\n\n"
        updated_system_prompt += f"## Reason for rejection:\n{feedback}\n\n"
        updated_system_prompt += "Please use find_internet_articles instead of visit_website for paywalled sources. Now respond again to the user's message below.\n"
        
        messages = [{"role": "system", "content": updated_system_prompt}] + history + [
            {"role": "user", "content": message},
        ]
        response = self.openai.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=self.QA_tools
        )
        return response


# Main chat handler

    def chat(self, message: str, history: list) -> str:

        messages = [
            {"role": "system", "content": self.QA_system_prompt}
        ] + history + [
            {"role": "user", "content": message}
        ]

        # Phase 1: Probe to check if tools are needed
        probe = self.openai.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=self.QA_tools,
        )
        assistant_msg = probe.choices[0].message

        # Phase 2: Tool path with evaluation
        if getattr(assistant_msg, "tool_calls", None):
            # Evaluate once: if paywalled visit → reject and rerun with "use find_internet_articles"
            evaluation = self.evaluate(assistant_msg, message, history)

            if not evaluation.is_acceptable:
                print("Failed evaluation - rerunning with feedback (use internet search for paywalled sources)")
                print(evaluation.feedback)
                assistant_msg = self.rerun(
                    assistant_msg, message, history, evaluation.feedback
                ).choices[0].message
                # Do not re-evaluate: post-rerun tool calls (e.g. find_internet_articles) are trusted
            else:
                print("Passed evaluation - proceeding")

            # Execute the tool calls (initial or post-rerun)
            results = self.handle_tool_call(assistant_msg)

            messages.append(assistant_msg)
            messages.extend(results)

            # CHANGED: Phase 2A system message is in Chinese
            stream = self.openai.chat.completions.create(
                model=MODEL,
                messages=messages + [
                    {
                        "role": "system",
                        "content": "请用小Lin说的风格，根据获取到的英文资料，用中文回答用户的问题。",
                    }
                ],
                stream=True,
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
            return

        # No-tool path: Direct response
        stream = self.openai.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True,
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



# Singleton instance for the answering agent
QA_instance = QA()


def chat(message: str, history: list) -> str:
    """
    Module-level chat function for use by the router.
    
    Provides a simple interface that delegates to the QA singleton.
    
    Args:
        message: User's input message
        history: Previous conversation turns
        
    Yields:
        Streamed response chunks
    """
    yield from QA_instance.chat(message, history)
