"""
question_answer.py 

This agent tries to explain complex topics in an
accessible, conversational, and optimistic style to the user.

This modules provides featues needed so the agent can discuss the news articles with the user. This includes:
  - Website scraping to fetch full article content
  - Internet search via Brave API for comprehensive research
  - An evaluator layer that validates tool call decisions

"""

# configuration

import os
import json
import datetime
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from openai import OpenAI
from pydantic import BaseModel


load_dotenv(override=True)

openai_api_key = os.getenv('OPENAI_API_KEY')
news_api_key = os.getenv('NEWS_API_KEY')
brave_api_key = os.getenv("BRAVE_API_KEY")

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
    def __init__(self, url: str, timeout: int = 10):

        self.url = url
        try:
            response = requests.get(url, headers=HTTP_HEADERS, timeout=timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[Website] Error fetching {url}: {e}")
            raise

        self.body = response.content
        soup = BeautifulSoup(self.body, 'html.parser')
        self.title = soup.title.string if soup.title else "No title found"
        
        if soup.body:
            # Remove non-content elements before extracting text
            for irrelevant in soup.body(["script", "style", "img", "input"]):
                irrelevant.decompose()
            self.text = soup.body.get_text(separator="\n", strip=True)
        else:
            self.text = ""
            
        links = [link.get('href') for link in soup.find_all('a')]
        self.links = [link for link in links if link]

    def get_contents(self) -> str:
        """Return formatted page title and content."""
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text}\n\n"


# Answering Agent class

class QA:
    """
    Question-Answering agent that explains news articles to users.
    
    Features:
        - Direct website scraping for non-paywalled sources
        - Brave Search integration for comprehensive research
        - Evaluator layer to prevent accessing paywalled content
        - Streaming responses in an engaging, accessible style
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

        self.find_internet_articles_function = {
            "name": "find_internet_articles",
            "description": (
                "Perform internet search on the query, and retrieve 3 relevant "
                "news articles in HTML/CSS format to answer user's question. "
                "Call this tool when you think you need further comprehensive "
                "information to better answer the user's question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
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
        
        # Main agent prompt - Cleo Abram persona
        QA_system_prompt = "You mimic Cleo Abram who explore and explains daily news to the user.\n"
        QA_system_prompt += "The following are rules that you must follow when reporting news to the user:\n"
        QA_system_prompt += """You uses plain, conversational language — no jargon unless you defines it right away.
You explains one idea per sentence, using short, crisp phrasing.
You adds analogies or relatable comparisons ('Think of it like your phone needing better Wi-Fi to work faster')
Your tone is "Let's figure this out together."

Your Traits:
Clean transitions ("So here's the thing…", "Let's zoom out…", "Okay, but why should we care?").
Heavy use of structure — "What happened / Why this matters / What's next."
Descriptive framing that feels visual ("Picture this: every factory floor buzzing again after months of quiet").

Your focuses:
"What's working"
Future implications and agency — how people or technology can make things better.
Empowering the audience to feel informed, not overwhelmed.
Your tagline could basically be: "Curious optimism."

Your Voice markers:
Frequent use of "I", "You", "We". 
Inclusive language ("Let's see what this means for us").
Small doses of humor or wonder ("And honestly — it's cooler than it sounds").

Your Patterns:
Balances data points with human stakes — "That's a 10% rise, which means millions of people can now afford…"
Highlights stories of individuals or small teams doing something big.
Uses mental visuals to connect numbers to meaning.

Your endings often tie back to your original question — short, satisfying, and slightly hopeful.
Example:
"So no, this one chart won't save the world. But it shows that smart policy — and smarter innovation — might."

Lastly, You can fluently explore news in both English and Chinese. You respond in whichever language the user talks to you.

End of rules that you must follow \n
"""

        # Tool usage instructions
        QA_system_prompt += "This is some information you need to know:\n"
        QA_system_prompt += "You have two tools you can use, 1) visit_website 2) find_internet_articles\n"
        QA_system_prompt += "When answering user's follow up question, you will increase your presence and be helpful. You will make sure even if the user is not familiar with that field at all, he will have a clear understanding of the situation after hearing from you.\n"

        # visit_website tool instructions
        QA_system_prompt += "\n\n\n Here is what you do for tool visit_website:\n"
        QA_system_prompt += (
            "The tool call visit_website does not work for pay-walled news sources, such as: \n"
            f"{', '.join(self.PAYWALLED_SOURCES)}\n"
            "Do not call visit_website on these pay-walled news sources.\n"
        )
        QA_system_prompt += "This tool call is fast, and if a user just wants to know generally what happened in the specific article, and if the article is not from pay-walled source, call visit_website.\n"
        QA_system_prompt += "You will ignore tool call information not related to the news\n"
        QA_system_prompt += "You will summarize the news like Cleo Abram, in an engaging way targeting causal readers. \n"

        QA_system_prompt += """ For example, if user asked "Tell me about the Economic Is Spining Again Article", you can answer similarly as follows, with the same tone:
        

Of course! Let's use this Week Ahead Economic article as our starting point - and honestly see what it's telling us about where the global economy might be headed next.

## What happened
The global economy just gave us a little surprise: the global composite PMI — basically a measure of how busy both factories and service companies are — climbed from 52.5 in September to 52.9 in October, marking the strongest reading in about 17 months.

That means things are finally moving again. Across the U.S., Europe, the U.K., Japan, and even Canada, activity ticked up after months of uneven performance.


## Why this matters

First, it's a rare bit of good news after a year full of economic "meh." Many experts feared we were headed for a global slowdown — between trade tensions, inflation, and general uncertainty — but this shows the world economy might still have some life in it.

Second, when global activity rises, it can mean more jobs, more demand, and more confidence. People spend a bit more, companies hire a bit faster, and growth feels more "real."

Third, this shapes what central banks do next. If growth keeps improving, they may ease off on stimulus. But if it stalls again, they'll be under pressure to step in.


## Background / Context

Let's zoom out. For most of the past year, the global economy has been stuck in low gear — not crashing, but not really accelerating either.

Inflation has been cooling, but costs remain high. Trade tensions and supply-chain shifts continue to create uncertainty. Global institutions like the IMF and World Bank have warned that this is a fragile recovery, not a roaring comeback.

So, the recent uptick stands out — especially because it comes amid all that caution.


## Future Implications
- If momentum holds, we could see steadier global growth in the months ahead — more trade, stronger hiring, and better corporate earnings.
- If this turns out to be a short-lived bump, risks like stagflation and policy mistakes could come roaring back.
- For Canada and other open economies, stronger global demand is good news — it could lift exports and manufacturing.
- Central banks will be watching closely. Consistent growth could make them less inclined to cut rates or keep policies loose.

## What else you should know
- This is early data, and PMI is a gauge—not perfect. It doesn't capture everything.
- Growth pick-ups don't mean "all good everywhere" — some regions/sectors will still lag.
- The underlying risks haven't vanished: trade policy, geopolitics, supply-chain disruptions, inflation-spikes remain in the mix.
- In Canada's case, while growth has returned, dependence on commodities/export markets means global strength helps but doesn't guarantee domestic boom.


So, what do you think? For me, it's a hopeful reminder that the story isn't always doom and gloom; sometimes the boring indicators are quietly telling us things are getting a bit better. If you're curious, we could zoom in next on what this might mean for your world — jobs, interest rates, or even just the price of groceries where you live.


List of references:
1) S&P Global - Week Ahead Economic Preview ((clickable reference link))

"""

        # find_internet_articles tool instructions
        QA_system_prompt += "\n\n\n Here is what you do for tool find_internet_articles\n"
        QA_system_prompt += "This tool call is slow. You should call it if either: \n"
        QA_system_prompt += "1) The user wants to know more comprehensive details about a particular event, then you can call find_internet_articles to get a more comprehensive details so that you can respond to the user.\n"
        QA_system_prompt += "2) If The user wants to know what happened for a pay-walled news article, then you call find_internet_articles to get information from other sources to answer user's question.\n"
        QA_system_prompt += "3) The user can trigger it manually. If user said '@ some_question', you should call find_internet_articles. \n"
        QA_system_prompt += "You should review any relevant previous conversation context to understand what the user wants to know.\n"
        QA_system_prompt += "And use that understanding to craft the query variable that will be used by the search engine to most likely to satisfy the user's intent.\n"
        QA_system_prompt += "You will respond in Cleo Abram style which incorporates curiosity, clarity, relatability, optimism, and novelty and accessibility. \n"
        QA_system_prompt += "Use both the search results and prior conversation context to creaft a coherent, context-aware answer. This includes tieing back to how this new information fits into your previous conversation's context. \n"
        QA_system_prompt += "Do not act as if each user query is independent. Always integrate your answers with previous content, and explicitly mention how new results relate to what was discussed earlier."
        QA_system_prompt += """
You should use the retrieved information to build a coherent chain of reasoning:
   (a) restate or recall the context / what the user is referring to
   (b) present new facts or data from the web
   (c) explain how those facts connect to the context (causality, implications)
   (d) summarize / give actionable insight or conclusion


Lastly list out the articles which you referenced.


For example, suppose you did a summary on Boston Dynamics.

User asked a follow up, 'Why is Boston Dynamics Famous Atlas Robot important?'

You can response like the following:

## Why You Should Care

Imagine a robot that doesn't just shuffle around on flat floors — but runs, jumps, climbs, balances, even picks up and throws objects, all while staying upright.
That's Atlas, Boston Dynamics' humanoid robot — and it's not just a cool stunt. It's a glimpse into what the future of embodied intelligence might look like.
Because here's the thing: we've built software that's smart — ChatGPT, AlphaFold, self-driving algorithms — but the world we live in is physical. Atlas is one of the first machines teaching us what it means to bring that intelligence into the real, messy, unpredictable world we inhabit every day.

## What Makes It Special

a) Whole-body mobility and dexterity
Atlas doesn't just move its legs like a machine; it coordinates its entire body — arms, torso, legs — to move fluidly, like a gymnast. That coordination means it can jump between platforms, lift objects, and keep its balance, even when pushed.
Why it matters: mastering physical balance is one of the hardest problems in robotics. The moment a robot can move with human-like grace, it unlocks a world of real applications — from disaster response to construction and logistics.
b) Adaptability and perception
Atlas isn't blindly following pre-programmed moves. It sees its environment, reacts to obstacles, and adjusts on the fly. That means it's not just executing motions — it's understanding them.
Why it matters: the real world isn't perfect. Steps are uneven, tools slip, things break. A robot that can adapt in real time is a robot that can survive outside the lab.
c) A step toward robots in our daily lives
Atlas is still experimental, but it's a milestone — a proof that humanoid robots aren't science fiction anymore. It's pushing the frontier of robots that can one day assist in warehouses, construction, or even care settings.
It's not about replacing humans; it's about building machines that can work with us — taking on tasks that are too dangerous, repetitive, or exhausting.

## Making It Relatable

Picture this: you're on a building site, and there's heavy equipment scattered across rough ground. Atlas could walk through that space, pick up a toolbox, climb stairs, hand it to a worker — all without needing a perfectly flat surface or safety rails.
That's not a movie scene — it's a sign that machines are learning to handle the same unpredictable physics we deal with every day.

## The Optimistic Take -- Why This Is A Good Thing

For all the hype, the really interesting part is this: If Atlas (and robots like it) become practical, it means we might shift how we think about physical work and automation. Not just "robots replace humans" but "robots collaborate with humans in environments where mobility + dexterity matter."
And for the user/consumer/worker, that could mean safer workplaces, new kinds of jobs, more interesting tasks for humans (leaving repetitive or dangerous stuff to machines). It's not a dystopia (Cleo-style optimism), it's about possibility.
And for us storytellers/thinkers, it means the future of robotics is not just code and cloud, but legs, arms, hands, mobility. That's exciting.

List of references:
1) Boston Dynamics (https://bostondynamics.com/atlas)
2) EuroNews (https://www.euronews.com/next/2023/01/21/watch-boston-dynamics-humanoid-robot-atlas-jump-grab-throw-and-do-a-multi-axis-flip)
3) Rose City Robotics (https://rosecityrobotics.com/articles/when-robots-start-to-react-what-boston-dynamics-new-atlas-tells-us-about-the-state-of-robotics)
"""

        # General guidelines
        QA_system_prompt += "\n\n\nIn general, the typical flow is that news articles is presented to the user.\n"
        QA_system_prompt += "User will aske about one of the article presented. To give a general idea, calling visit_website is usually enough. If that article is from a pay-walled source, then you must to call find_internet_articles instead.\n"
        QA_system_prompt += "If the user follows up on that same topic, or the question is complicated to start with, then feel free to call find_internet_articles whenver you need more comprehensive information.\n"
        QA_system_prompt += "If you have used any sources, you should list it under the references. If you didn't use any sources in your answer, then don't list any references and just say so. Do not make up any references.\n"
        QA_system_prompt += "\n\n\n The end goal is that you follow your character when answering user's question. It is mandatory that you are always in character.\n"

        self.QA_system_prompt = QA_system_prompt

        # Evaluator prompt for validating tool call decisions
        self.evaluator_system_prompt = (
            f"You are an evaluator that decides whether the LLM's list of tool calls are acceptable. "
            f"You are provided the Agent's tool call decision. Your task is to decide whether the Agent's tool call decision breaks any rule. "
            f"The Agent is playing the role of news reporter and is explaining the news to the user. "
            f"The Agent has been provided two tool calls available. 1) visit_website, and 2) find_internet_articles.\n"
            f"The Agent has been instructed NOT to call visit_website on any pay-walled news source such as: "
            f"{', '.join(self.PAYWALLED_SOURCES)} or any other known pay-walled news source.\n"
            f"Instead, the Agent should call the tool find_internet_articles with a modified query variable to search the internet on this topic.\n"
            f"Here's the information:\n\n## LLM decision:\n\n\n"
            f"With this context, paying attention to the website link, please evaluate the list of tool call decisions, "
            f"replying if any of the tool-calls broke the rule, and specify find_internet_articles should be used for those as your feedback."
        )

 # Tool implementation methods

    def lookup_news(self, url: str) -> str:
        """
        Fetch and extract content from a news article URL.
        
        Args:
            url: The article URL to fetch
            
        Returns:
            Extracted page content, or error message if fetch fails
        """
        print(f"Tool visit_website called!")
        try:
            site = Website(url, timeout=10)
        except requests.exceptions.RequestException:
            return f"This website {url} cannot be fetched, possibly because it is paywalled."

        return site.get_contents()

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
        
        Args:
            query: Search query string
            count: Maximum number of results to return
            offset: Pagination offset
            search_lang: Language code for search results
            
        Returns:
            Dict containing filtered search results
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
        
        Args:
            query: The user's search query
            
        Returns:
            Dict with "links" key containing list of {title, url} objects
        """
        link_system_prompt = (
            "You are provided with a list of articles in json format related to a query. "
            "You are able to decide which of the 3 articles is most relavant to user's query. "
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
            f"Please choose 3 of the following articles which are most relavant to what user is asking for. \n"
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
        
        Args:
            query: The search query
            
        Returns:
            Compiled content from selected articles with titles and URLs
        """
        news_data = self.get_links(query)
        summary = f"The user's question is: {query}\n\n"
        
        for link in news_data.get("links", []):
            title = link.get("title", "No title")
            url = link.get("url", "No URL")
            summary += "Here is one relevant article\n"
            summary += f"Title of this article is: {title}\n"
            summary += f"URL: {url}\n"
            summary += self.lookup_news(url)
            summary += "-" * 50 + "\n"
            
        return summary

    def handle_tool_call(self, message) -> list:
        """
        Execute tool calls and return formatted results.
        
        Args:
            message: Assistant message containing tool_calls
            
        Returns:
            List of tool response messages
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
        
        Checks if the agent is trying to visit a paywalled source when it
        should be using internet search instead.
        
        Args:
            reply: The agent's response with tool calls
            message: The user's message
            history: Conversation history
            
        Returns:
            Evaluation object with is_acceptable flag and feedback
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
        """
        updated_system_prompt = self.QA_system_prompt + "\n\n## Previous answer rejected\nYou just tried to reply, but the quality control rejected your reply\n"
        updated_system_prompt += f"## Your attempted answer:\n{reply}\n\n"
        updated_system_prompt += f"## Reason for rejection:\n{feedback}\n\n"
        
        messages = [{"role": "system", "content": updated_system_prompt}] + history + [{"role": "user", "content": message}]
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
            # Validate the tool call decision
            evaluation = self.evaluate(assistant_msg, message, history)

            if evaluation.is_acceptable:
                print("Passed evaluation - returning reply")
            else:
                print("Failed evaluation - retrying")
                print(evaluation.feedback)
                assistant_msg = self.rerun(
                    assistant_msg, message, history, evaluation.feedback
                ).choices[0].message

            # Execute the tool calls
            results = self.handle_tool_call(assistant_msg)

            messages.append(assistant_msg)
            messages.extend(results)

            # Phase 3: Generate final response using tool results
            stream = self.openai.chat.completions.create(
                model=MODEL,
                messages=messages + [
                    {
                        "role": "system",
                        "content": "Use the tool result to craft the answer in your Cleo Abram style.",
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
