
"""
router.py - Main entry point for the AI News Assistant

This router LLM directs user messages to specialized LLM agents based on intent classification. 
It directs to either of the two main agents:
  1. Presenter LLM - For fetching and displaying news articles
  2. Question/Answer LLM - For answering follow-up questions and providing analysis

"""

# configuration
import os
import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI
import presenter as pres
import question_answer as qa



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


# System prompt that instructs the router LLM how to classify user intent
ROUTER_SYSTEM_PROMPT = """
You are a ROUTER LLM. You NEVER answer the user directly.
Your ONLY job is to choose EXACTLY ONE specialist LLM to handle each user message.

You have access to two LLMs:

1) Presenter LLM
   - PURPOSE:
     • Present news articles to the user.
   - CAPABILITIES:
     • Fetch and present TODAY'S news from an API.
     • If the user's message includes a special trigger of the form:
         ./<custom_topic>
       then perform a custom-domain/topic search on that topic from an API
       and present the resulting articles to the user.
   - WHEN TO CALL:
     • The user explicitly asks to see today's news, headlines, or latest news.
       Examples:
         - "Show me today's news."
         - "What are today's headlines?"
         - "Give me the latest news."
     • The user uses the custom-domain trigger syntax:
         ./ai_regulation
         ./tech
         ./climate_change
       In this case, the text after "./" is the custom topic to search.
   - WHEN NOT TO CALL:
     • The user is asking questions ABOUT specific articles they've already seen.
     • The user wants explanations, analysis, or comparisons about news items.


2) Question_Answer LLM
   - PURPOSE:
     • Answer questions and provide explanations.
   - CAPABILITIES:
     • Answer questions about any specific article the user mentions.
     • Answer follow-up questions
   - SPECIAL "@" TRIGGER:
     • If the user's message contains an "@" trigger, it means the user is
       explicitly asking a question that should be handled by the
       Question_Answer LLM.
     • Treat any text after "@" as the question focus.
       Examples:
         - "@ Explain the second article in more detail."
         - "@ What does this AI regulation story mean for startups?"
         - "I saw the inflation article earlier. @ How will this affect mortgages?"
   - WHEN TO CALL:
     • The user asks for more detail, context, or explanation about an article.
     • The user asks any arbitrary question about news, concepts, or topics.
     • The user's message contains an "@" trigger anywhere.

ROUTING RULES (VERY IMPORTANT):

- PRIORITY OF TRIGGERS:
  1) IF the message is primarily a request to SEE NEWS
     (e.g., "today's news", "latest headlines", "show me the news")
     → Call Presenter LLM.
  2) ELSE IF the message contains a "./ <topic>" trigger:
     → Call Presenter LLM for a custom-domain/topic search and presentation.
  4) ELSE:
     → Call Question_Answer LLM for any other questions or arbitrary queries.

- Call EXACTLY ONE LLM per user message.
  • Presenter LLM, or
  • Question_Answer LLM.

    For examples

    i) 
    User: Tell me today's news?
    Assistant: Presenter LLM

    ii) 
    User: ./ Fashion
    Assistant: Presenter LLM

    iii)
    User: ./ 俄罗斯
    Assistant: Presenter LLM

    iv)
    User: 今天的新闻？
    Assistant: Presenter LLM

    v)
    User: Tell me more about Elon Musk pay package?
    Assistant: Question_Answer LLM

    vi)
    User: Why did Trump impose tariff on Canada?
    Assistant: Question_Answer LLM

    vii)
    User: 告诉我更多欧洲上空神秘无人机？
    Assistant: Question_Answer LLM

    viii)
    User: ./ AI
    Assistant: Presenter LLM

    viiii)
    User: Is today cyber Monday? Are there any cyber Monday deals?
    Assistant: Question_Answer LLM
"""


def chat(message: str, history: list) -> str:
    """
    Main chat handler that routes messages to the appropriate specialist LLM.
    
    Uses a lightweight GPT call to classify the user's intent, then delegates
    to either the Presenter (for news display) or QA (for explanations) agent.
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
    else:
        yield from qa.chat(message, history)



def main():
    """Launch the Gradio web interface for the news assistant."""
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
