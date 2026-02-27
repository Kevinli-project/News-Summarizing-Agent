"use client";

import { useState, useEffect } from "react";
import type { ChatMessage, Lang, NewsResponse } from "@/types";
import NewsCard from "./NewsCard";
import InlineExplain from "./InlineExplain";
import ChatbotCard from "./ChatbotCard";

interface NewsFeedProps {
  lang: Lang;
  onExplain: (articleIndex: number) => void;
  isStreaming: boolean;
  expandedArticleIndex: number | null;
  history: ChatMessage[];
  onStreamStart: () => void;
  onStreamEnd: () => void;
  onComplete: (userMessage: ChatMessage, assistantMessage: ChatMessage) => void;
  followUpMessage: string | null;
  onFollowUpSubmit: (message: string) => void;
  onFollowUpComplete: () => void;
}

export default function NewsFeed({
  lang,
  onExplain,
  isStreaming,
  expandedArticleIndex,
  history,
  onStreamStart,
  onStreamEnd,
  onComplete,
  followUpMessage,
  onFollowUpSubmit,
  onFollowUpComplete,
}: NewsFeedProps) {
  const [data, setData] = useState<NewsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const url = `/api/news?lang=${lang}&_ts=${Date.now()}`;
    fetch(url, { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText);
        return res.json();
      })
      .then((json: NewsResponse) => {
        if (!cancelled) setData(json);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load news");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [lang]);

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-6 px-4 py-6">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="flex overflow-hidden rounded-2xl bg-neutral-100 dark:bg-neutral-800"
          >
            <div className="flex-1 space-y-3 p-4">
              <div className="h-5 w-20 animate-pulse rounded-full bg-neutral-200 dark:bg-neutral-700" />
              <div className="h-5 w-full animate-pulse rounded bg-neutral-200 dark:bg-neutral-700" />
              <div className="h-4 w-3/4 animate-pulse rounded bg-neutral-200 dark:bg-neutral-700" />
              <div className="h-4 w-1/2 animate-pulse rounded bg-neutral-200 dark:bg-neutral-700" />
              <div className="h-12 w-12 animate-pulse rounded-full bg-neutral-200 dark:bg-neutral-700" />
            </div>
            <div className="h-40 w-40 shrink-0 animate-pulse bg-neutral-200 dark:bg-neutral-700 sm:h-44 sm:w-44" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 text-center">
        <p className="text-neutral-600 dark:text-neutral-400">{error}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-4 rounded-full bg-neutral-900 px-4 py-2 text-sm font-medium text-white dark:bg-white dark:text-neutral-900"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data?.categories?.length) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 text-center text-neutral-600 dark:text-neutral-400">
        No news available.
      </div>
    );
  }

  let articleIndex = 0;
  return (
    <div className="mx-auto max-w-2xl space-y-8 px-4 py-6">
      {data.categories.map((category) => (
        <section key={category.name}>
          <h2 className="mb-4 text-xl font-semibold text-neutral-900 dark:text-white">
            {category.name}
          </h2>
          <ul className="space-y-4">
            {category.articles.map((article) => {
              const currentIndex = articleIndex++;
              const isExpanded = currentIndex === expandedArticleIndex;
              return (
                <li key={article.url}>
                  <NewsCard
                    article={article}
                    categoryName={category.name}
                    onExplain={() => onExplain(currentIndex)}
                    isDisabled={isStreaming}
                  />
                  {isExpanded && (
                    <InlineExplain
                      article={article}
                      lang={lang}
                      history={history}
                      onStreamStart={onStreamStart}
                      onStreamEnd={onStreamEnd}
                      onComplete={onComplete}
                      followUpMessage={followUpMessage}
                      onFollowUpSubmit={onFollowUpSubmit}
                      onFollowUpComplete={onFollowUpComplete}
                      isStreaming={isStreaming}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      {/* Chatbot card at bottom of feed */}
      <section>
        <ChatbotCard
          lang={lang}
          history={history}
          onStreamStart={onStreamStart}
          onStreamEnd={onStreamEnd}
          onComplete={onComplete}
          isStreaming={isStreaming}
        />
      </section>
    </div>
  );
}
