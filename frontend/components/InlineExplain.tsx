"use client";

import { useEffect, useRef, useState } from "react";
import type { Article, ChatMessage, Lang } from "@/types";
import { streamSseDeltas } from "@/lib/sse";
import StreamedResponse from "./StreamedResponse";
import FollowUpBar from "./FollowUpBar";

interface InlineExplainProps {
  article: Article;
  lang: Lang;
  history: ChatMessage[];
  onStreamStart: () => void;
  onStreamEnd: () => void;
  onComplete: (userMessage: ChatMessage, assistantMessage: ChatMessage) => void;
  followUpMessage: string | null;
  onFollowUpSubmit: (message: string) => void;
  onFollowUpComplete: () => void;
  isStreaming: boolean;
}

export default function InlineExplain({
  article,
  lang,
  history,
  onStreamStart,
  onStreamEnd,
  onComplete,
  followUpMessage,
  onFollowUpSubmit,
  onFollowUpComplete,
  isStreaming: isStreamingFromParent,
}: InlineExplainProps) {
  const [content, setContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const streamEndedRef = useRef(false);
  const historyRef = useRef(history);
  const contentRef = useRef("");

  useEffect(() => {
    historyRef.current = history;
  }, [history]);

  useEffect(() => {
    contentRef.current = content;
  }, [content]);

  useEffect(() => {
    const message = `Tell me more about this article: ${article.title}. URL: ${article.url}`;
    streamEndedRef.current = false;
    onStreamStart();

    const abortController = new AbortController();

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: historyRef.current, lang }),
      signal: abortController.signal,
    })
      .then(async (response) => {
        const { accumulated } = await streamSseDeltas(response, (nextContent) => {
          setContent(nextContent);
        });

        setIsStreaming(false);
        if (accumulated) {
          onComplete(
            { role: "user", content: message },
            { role: "assistant", content: accumulated }
          );
        }
        if (!streamEndedRef.current) {
          streamEndedRef.current = true;
          onStreamEnd();
        }
      })
      .catch((e: unknown) => {
        if (e instanceof Error && e.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "Failed to stream response");
        setIsStreaming(false);
        if (!streamEndedRef.current) {
          streamEndedRef.current = true;
          onStreamEnd();
        }
      });

    return () => {
      abortController.abort();
      if (!streamEndedRef.current) {
        streamEndedRef.current = true;
        onStreamEnd();
      }
    };
    // Only re-run when article changes, NOT when history changes (history is captured via ref)
  }, [article.title, article.url, lang, onStreamStart, onStreamEnd, onComplete]);

  useEffect(() => {
    if (!followUpMessage) return;

    const message = followUpMessage;
    const followUpLabel = lang === "zh" ? "追问" : "Follow up";
    const quotedMessage = message.replace(/\n/g, "\n> ");
    const prefix =
      contentRef.current + "\n\n> **" + followUpLabel + ":** " + quotedMessage + "\n\n";

    setContent(prefix);
    setError(null);
    onStreamStart();
    setIsStreaming(true);
    streamEndedRef.current = false;

    const abortController = new AbortController();

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: historyRef.current, lang }),
      signal: abortController.signal,
    })
      .then(async (response) => {
        const { accumulated } = await streamSseDeltas(response, (nextContent) => {
          setContent(prefix + nextContent);
        });

        setIsStreaming(false);
        if (accumulated) {
          onComplete(
            { role: "user", content: message },
            { role: "assistant", content: accumulated }
          );
        }
        onFollowUpComplete();
        if (!streamEndedRef.current) {
          streamEndedRef.current = true;
          onStreamEnd();
        }
      })
      .catch((e: unknown) => {
        if (e instanceof Error && e.name === "AbortError") return;
        setError(e instanceof Error ? e.message : "Failed to stream response");
        setIsStreaming(false);
        onFollowUpComplete();
        if (!streamEndedRef.current) {
          streamEndedRef.current = true;
          onStreamEnd();
        }
      });

    return () => {
      abortController.abort();
      if (!streamEndedRef.current) {
        streamEndedRef.current = true;
        onStreamEnd();
      }
      onFollowUpComplete();
    };
  }, [followUpMessage, lang, onStreamStart, onStreamEnd, onComplete, onFollowUpComplete]);

  return (
    <div className="mt-4 rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-800">
      {error ? (
        <div className="text-sm text-red-600 dark:text-red-400">Error: {error}</div>
      ) : (
        <StreamedResponse content={content} isStreaming={isStreaming} lang={lang} />
      )}
      <FollowUpBar
        onSubmit={onFollowUpSubmit}
        isDisabled={isStreamingFromParent}
        placeholder={lang === "zh" ? "追问..." : "Ask a follow-up..."}
      />
    </div>
  );
}
