# News-Summarizer-Agent

<img width="1184" height="864" alt="image" src="https://github.com/user-attachments/assets/e50e2baf-92d9-4f43-957e-2c8b100ca4e9" />

## What This Project Does

This is an AI-powered daily news summarizer for busy people.

It reads news across categories like **Top Headlines, Business, Technology, and Canada**, then:
- Summarizes articles based on your interests
- Keeps information neutral and high-level
- Explains **What Happened**, **Why This Matters**, and **How It Relates to Us**
- Lets you ask follow-up questions
- Links directly to original sources if you want to dive deeper

The goal is simple: understand what’s happening without spending all day reading the news.



##  How It Works

This project uses a multi-agent LLM pipeline to turn raw news into clean summaries.

<img width="2048" height="909" alt="image" src="https://github.com/user-attachments/assets/d4a0331a-8752-4b07-ab97-451dd6990daf" />
*Figure: High-level architecture of the multi-agent LLM pipeline. User input is routed through a Router LLM to specialized agents for presentation, question answering, and evaluation before producing the final output.*



1. **Router LLM**  
   Every user input first goes through a Router LLM, which determines what kind of task is being requested (e.g. news presentation vs. a follow-up question) and routes it to the appropriate agent.


2. **Presenter LLM**  
   For news presentation, the request is sent to the Presenter LLM.  
   It focuses on:
   - Reading and aggregating news
   - Extracting what is important
   - Presenting the information in a clear, high-level format  
   
   
3. **QA LLM**  
   If the user is interested in a particular article, the Router sends it to the QA LLM.  
   This agent can:
   - Visit original articles
   - Search the internet for additional context
   - Generate detailed, source-backed answers


4. **Evaluator LLM**  
   The Evaluator LLM reviews the QA LLM’s decisions, to make sure QA LLM’s response is evidence based.

5. **Final Output**  
   The refined response is sent back to the user, along with source links for transparency and further reading.

This separation of responsibilities keeps the system fast, modular and specialized, and easy to extend.


## Example Usage

### 1) Get Daily News Presentation

**User input: "Tell me today's news?"** 

<img width="2328" height="984" alt="image" src="https://github.com/user-attachments/assets/e3cfd2d3-368a-41c7-823e-b7005c17aef0" />
---

**What happens behind the scenes:**
<img width="1858" height="772" alt="image" src="https://github.com/user-attachments/assets/a0f400f2-130f-4f67-bed5-08149741c988" />


- The **Router LLM** classifies this as a news summary request
- The request is routed to the **Presenter LLM**
- The Presenter reads and aggregates news across selected categories

**Output:**
- A clean, high-level daily news briefing
- Published date and source links for each article
- Optional images for visual context

---

### 2) Ask a Follow-Up Question

**User input: "Tell me more about this XXX article?"**

<img width="2170" height="1090" alt="image" src="https://github.com/user-attachments/assets/e85c5efc-54ee-48f3-aab6-55f4bf097293" />
---

**What happens behind the scenes:**
<img width="2048" height="916" alt="image" src="https://github.com/user-attachments/assets/417212c4-c115-4844-a429-c8fa6e71e468" />


- The **Router LLM** detects a follow-up question
- The request is sent to the **QA LLM**
- The QA agent:
  - Visits original articles
  - Searches the internet for additional context
- The **Evaluator LLM** reviews the QA LLM's action for clarity and relevance
- The refined response is returned to the user with sources

**Output:**
- A focused, source-backed explanation
- Clear reasoning without unnecessary detail
- Direct links to referenced articles


## 🚀 Try It Out

You can try the chatbot live on **Hugging Face Spaces** — no setup required:

👉 **Live Demo:** https://huggingface.co/spaces/Kevinli0802/News_Summarizing_Agent

Once you’re in, just start chatting. For example:

- say "Tell me today's news?" to get daily news presentation
- say "Tell me more about this XXX article? " to have chatbot summarize the article for you




## Future Improvements

This project is actively evolving. Some areas I plan to improve in the future include:

- **Asynchronous article retrieval**  
  Improve the internet article fetch and reading process by moving from a sequential pipeline to asynchronous Python. This will significantly reduce search time and allow the system to pull from a wider range of sources.

- **Richer presentation and summaries**  
  Experiment with more engaging presentation formats and make the summary sections slightly more detailed, while still keeping the high-level, time-saving focus.

- **User-customizable news categories**  
  Allow users to fully customize which news categories and topics they are interested in. This is a larger feature.

These improvements aim to make the system faster, more flexible, and more personalized over time.


