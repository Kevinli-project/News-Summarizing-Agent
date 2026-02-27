"use client";

import { useEffect, useState, useRef } from "react";
import type { ChatMessage, Lang, ToolType } from "@/types";
import { streamSseDeltas } from "@/lib/sse";
import ToolSelector from "./ToolSelector";
import StreamedResponse from "./StreamedResponse";

const CARD_HEADER = {
  en: "If you wanna see more topics, or ask me anything specific, just say so!",
  zh: "想看更多主题或问我任何问题，直接说即可！",
} as const;

const PLACEHOLDER = {
  en: "Type a message...",
  zh: "输入消息...",
} as const;

const PLACEHOLDER_SHOW_NEWS = {
  en: "Type \"Elon Musk\", \"Japan\", etc.",
  zh: "输入关键词，如「马斯克」「日本」等",
} as const;

interface ChatbotCardProps {
  lang: Lang;
  history: ChatMessage[];
  onStreamStart: () => void;
  onStreamEnd: () => void;
  onComplete: (userMessage: ChatMessage, assistantMessage: ChatMessage) => void;
  isStreaming: boolean;
}

type MessageItem = ChatMessage;

export default function ChatbotCard({
  lang,
  history,
  onStreamStart,
  onStreamEnd,
  onComplete,
  isStreaming: isStreamingFromParent,
}: ChatbotCardProps) {
  const [selectedTool, setSelectedTool] = useState<null | ToolType>(null);
  const [inputValue, setInputValue] = useState("");
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const historyRef = useRef(history);

  useEffect(() => {
    historyRef.current = history;
  }, [history]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const message = inputValue.trim();
    if (!message || isStreamingFromParent || isStreaming) return;

    setInputValue("");
    setError(null);
    onStreamStart();
    setIsStreaming(true);

    const userMessage: MessageItem = { role: "user", content: message };
    setMessages((prev) => [...prev, userMessage]);
    setStreamingContent("");

    const isNewsSearch = selectedTool === "show_news";
    const url = isNewsSearch ? "/api/news-search" : "/api/chat";
    const body = isNewsSearch
      ? JSON.stringify({ query: message, lang, history: historyRef.current })
      : JSON.stringify({
          message: selectedTool === "web_search" ? `Search the web: ${message}` : message,
          history: historyRef.current,
          lang,
        });

    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    })
      .then(async (response) => {
        const { accumulated } = await streamSseDeltas(response, (nextContent) => {
          setStreamingContent(nextContent);
        });

        setIsStreaming(false);
        setStreamingContent("");
        if (accumulated) {
          setMessages((prev) => [...prev, { role: "assistant", content: accumulated }]);
          onComplete(
            { role: "user", content: message },
            { role: "assistant", content: accumulated }
          );
        }
        onStreamEnd();
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to stream response");
        setIsStreaming(false);
        onStreamEnd();
      });
  };

  const disabled = isStreamingFromParent || isStreaming;

  return (
    <div className="flex overflow-hidden rounded-2xl bg-neutral-100 shadow-sm dark:bg-neutral-800">
      <div className="flex min-w-0 flex-1 flex-col p-4">
        {/* Category: orange-to-yellow gradient text */}
        <span className="mb-2 inline-block bg-gradient-to-r from-orange-500 to-yellow-400 bg-clip-text text-xs font-semibold uppercase tracking-wide text-transparent">
          Chatbot
        </span>
        <p className="mb-4 text-sm text-neutral-700 dark:text-neutral-300">
          {CARD_HEADER[lang]}
        </p>

        {/* Message list */}
        <div className="mb-4 space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={
                msg.role === "user"
                  ? "rounded-lg bg-neutral-200/80 px-3 py-2 text-sm text-neutral-900 dark:bg-neutral-700 dark:text-white"
                  : ""
              }
            >
              {msg.role === "user" ? (
                msg.content
              ) : (
                <StreamedResponse content={msg.content} isStreaming={false} lang={lang} />
              )}
            </div>
          ))}
          {isStreaming && (
            <div>
              <StreamedResponse content={streamingContent} isStreaming lang={lang} />
            </div>
          )}
        </div>

        {error && (
          <div className="mb-4 text-sm text-red-600 dark:text-red-400">Error: {error}</div>
        )}

        {/* Tool selector + input (same row: + dropdown, chip, input, Send); min-height so dropdown has room */}
        <form onSubmit={handleSubmit} className="mt-2 min-h-[4rem] pt-2">
          <div className="flex flex-wrap items-center gap-2">
            <ToolSelector
              selectedTool={selectedTool}
              onToolChange={setSelectedTool}
              lang={lang}
            />
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={selectedTool === "show_news" ? PLACEHOLDER_SHOW_NEWS[lang] : PLACEHOLDER[lang]}
              disabled={disabled}
              className="min-w-0 flex-1 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm placeholder:text-neutral-400 focus:border-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-400 dark:border-neutral-600 dark:bg-neutral-800 dark:placeholder:text-neutral-500 dark:focus:border-neutral-500 dark:focus:ring-neutral-500"
              aria-label="Chat message"
            />
            <button
              type="submit"
              disabled={disabled || !inputValue.trim()}
              className="shrink-0 rounded-lg bg-neutral-700 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-600 disabled:opacity-50 dark:bg-neutral-600 dark:hover:bg-neutral-500"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
