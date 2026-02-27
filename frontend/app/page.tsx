"use client";

import { useState, useCallback } from "react";
import NewsFeed from "@/components/NewsFeed";
import type { ChatMessage, Lang } from "@/types";

export default function Home() {
  const [lang, setLang] = useState<Lang>("en");
  const [expandedArticleIndex, setExpandedArticleIndex] = useState<number | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [followUpMessage, setFollowUpMessage] = useState<string | null>(null);

  const handleExplain = (articleIndex: number) => {
    setExpandedArticleIndex(articleIndex);
    setFollowUpMessage(null); // clear any pending follow-up when switching cards
    setIsStreaming(true);
  };

  const handleStreamStart = useCallback(() => {
    setIsStreaming(true);
  }, []);

  const handleStreamEnd = useCallback(() => {
    setIsStreaming(false);
  }, []);

  const handleComplete = useCallback(
    (userMessage: ChatMessage, assistantMessage: ChatMessage) => {
      setHistory((prev) => [...prev, userMessage, assistantMessage]);
      // Note: setIsStreaming(false) is handled by handleStreamEnd
    },
    []
  );

  const handleLangChange = (newLang: Lang) => {
    if (newLang === lang) return; // No change
    setLang(newLang);
    setHistory([]);
    setExpandedArticleIndex(null);
    setFollowUpMessage(null);
    setIsStreaming(false);
  };

  const handleFollowUpSubmit = useCallback((message: string) => {
    setFollowUpMessage(message);
  }, []);

  const handleFollowUpComplete = useCallback(() => {
    setFollowUpMessage(null);
  }, []);

  return (
    <div className="min-h-screen bg-neutral-50 dark:bg-neutral-950">
      <header className="sticky top-0 z-10 border-b border-neutral-200 bg-white/95 px-4 py-3 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/95">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-neutral-900 dark:text-white">
            News Feed
          </h1>
          {/* Language toggle: EN/ZH */}
          <div className="flex items-center gap-1 rounded-lg bg-neutral-100 p-1 dark:bg-neutral-800">
            <button
              type="button"
              onClick={() => handleLangChange("en")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                lang === "en"
                  ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                  : "text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200"
              }`}
              aria-label="Switch to English"
            >
              EN
            </button>
            <button
              type="button"
              onClick={() => handleLangChange("zh")}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                lang === "zh"
                  ? "bg-white text-neutral-900 shadow-sm dark:bg-neutral-700 dark:text-white"
                  : "text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200"
              }`}
              aria-label="Switch to Chinese"
            >
              ZH
            </button>
          </div>
        </div>
      </header>
      <NewsFeed
        lang={lang}
        onExplain={handleExplain}
        isStreaming={isStreaming}
        expandedArticleIndex={expandedArticleIndex}
        history={history}
        onStreamStart={handleStreamStart}
        onStreamEnd={handleStreamEnd}
        onComplete={handleComplete}
        followUpMessage={followUpMessage}
        onFollowUpSubmit={handleFollowUpSubmit}
        onFollowUpComplete={handleFollowUpComplete}
      />
    </div>
  );
}
