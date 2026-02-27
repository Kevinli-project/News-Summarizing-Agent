
"""
router.py - Reference-only legacy router (not used by FastAPI production paths)

This router LLM directs user messages to specialized LLM agents based on
intent classification and language detection. It routes to one of four agents:
  1. Presenter LLM        - English news presentation
  2. Presenter_ZH LLM     - Chinese news presentation
  3. Question_Answer LLM   - English Q&A and analysis
  4. Question_Answer_ZH LLM - Chinese Q&A and analysis (小Lin说 style)

"""

# configuration
import os
from dotenv import load_dotenv
from openai import OpenAI
import presenter as pres
import presenter_zh as pres_zh
import question_answer as qa
import question_answer_zh as qa_zh



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


# System prompt that instructs the router LLM how to classify user intent
ROUTER_SYSTEM_PROMPT = """
You are a ROUTER LLM. You NEVER answer the user directly.
Your ONLY job is to choose EXACTLY ONE specialist LLM to handle each user message.

You must decide TWO things:
  1) INTENT: Is the user requesting to SEE news, or ASKING a question about news?
  2) LANGUAGE: Is the user writing in English or Chinese?

You have access to four specialist LLMs:

1) Presenter LLM  (English news presentation)
   - Fetches and presents news articles in English.
   - Handles requests for today's news or custom topic searches via "./" trigger.

2) Presenter_ZH LLM  (Chinese news presentation)
   - Fetches and presents news articles translated to Chinese.
   - Handles the same requests as Presenter LLM, but when the user writes in Chinese.

3) Question_Answer LLM  (English Q&A)
   - Answers questions, provides explanations, and analyzes news in English.
   - Handles follow-up questions, "@" triggered deep-dives, and general queries.

4) Question_Answer_ZH LLM  (Chinese Q&A, 小Lin说 style)
   - Answers questions and explains news in Chinese with a 小Lin说 personality.
   - Handles the same types of queries as Question_Answer LLM, but when the user writes in Chinese.


## INTENT RULES

- PRESENTER intent (news presentation):
  • The user asks to SEE today's news, headlines, or latest news.
  • The user uses the "./" custom-domain trigger (e.g., "./ AI", "./ 俄罗斯").

- QUESTION_ANSWER intent (Q&A):
  • The user asks ABOUT a specific article, event, or topic.
  • The user wants explanation, analysis, context, or follow-up.
  • The user uses the "@" trigger for a deep-dive question.
  • Any other general question.


## LANGUAGE RULES

- If the user's message is primarily in English → use the English specialist.
- If the user's message is primarily in Chinese → use the Chinese specialist.
- For the "./" trigger: the language of the SURROUNDING message determines the specialist.
  If there is no surrounding text, look at the topic itself:
  • "./ AI" with no other text → English (Latin characters)
  • "./ 人工智能" with no other text → Chinese (Chinese characters)


## ROUTING DECISION TABLE

| Intent    | Language | Route to               |
|-----------|----------|------------------------|
| Presenter | English  | Presenter LLM          |
| Presenter | Chinese  | Presenter_ZH LLM       |
| Q&A       | English  | Question_Answer LLM    |
| Q&A       | Chinese  | Question_Answer_ZH LLM |


## OUTPUT FORMAT

Respond with EXACTLY ONE of these four strings (nothing else):
  • Presenter LLM
  • Presenter_ZH LLM
  • Question_Answer LLM
  • Question_Answer_ZH LLM


## EXAMPLES

i)
User: Tell me today's news?
Assistant: Presenter LLM

ii)
User: ./ Fashion
Assistant: Presenter LLM

iii)
User: ./ AI
Assistant: Presenter LLM

iv)
User: Tell me more about the Elon Musk pay package?
Assistant: Question_Answer LLM

v)
User: Why did Trump impose tariff on Canada?
Assistant: Question_Answer LLM

vi)
User: @ What does the AI regulation story mean for startups?
Assistant: Question_Answer LLM

vii)
User: Is today cyber Monday? Are there any cyber Monday deals?
Assistant: Question_Answer LLM

viii)
User: 今天的新闻？
Assistant: Presenter_ZH LLM

ix)
User: 告诉我今天的新闻
Assistant: Presenter_ZH LLM

x)
User: ./ 俄罗斯
Assistant: Presenter_ZH LLM

xi)
User: ./ 人工智能
Assistant: Presenter_ZH LLM

xii)
User: 告诉我更多欧洲上空神秘无人机？
Assistant: Question_Answer_ZH LLM

xiii)
User: 跟我讲讲美联储加息的影响
Assistant: Question_Answer_ZH LLM

xiv)
User: @ 这篇关于AI监管的文章对创业公司意味着什么？
Assistant: Question_Answer_ZH LLM

xv)
User: 为什么特朗普要对加拿大加征关税？
Assistant: Question_Answer_ZH LLM
"""


def chat(message: str, history: list) -> str:
    """
    Main chat handler that routes messages to the appropriate specialist LLM.
    
    Uses a lightweight GPT call to classify the user's intent and language,
    then delegates to one of four specialists:
      - Presenter LLM (English news)
      - Presenter_ZH LLM (Chinese news)
      - Question_Answer LLM (English Q&A)
      - Question_Answer_ZH LLM (Chinese Q&A)
    """
    messages = [
        {"role": "system", "content": ROUTER_SYSTEM_PROMPT}
    ] + history + [
        {"role": "user", "content": message}
    ]

    response = openai.chat.completions.create(
        model=MODEL,
        messages=messages,
    )
    decision = response.choices[0].message.content

    # Route to the appropriate specialist
    if decision == "Presenter LLM":
        yield from pres.chat(message, history)
    elif decision == "Presenter_ZH LLM":
        yield from pres_zh.chat(message, history)
    elif decision == "Question_Answer_ZH LLM":
        yield from qa_zh.chat(message, history)
    else:
        yield from qa.chat(message, history)



def main():
    """Launch the Gradio web interface for the news assistant."""
    import gradio as gr
    demo = gr.ChatInterface(
        fn=chat,
        type="messages",
        theme=gr.themes.Monochrome()
    )
    demo.launch(
        server_name=os.getenv("HOST", "0.0.0.0"),
        server_port=int(os.getenv("PORT", 7860)),
        show_error=True,
        pwa=True
    )


if __name__ == "__main__":
    main()
