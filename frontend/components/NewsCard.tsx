"use client";

import type { MouseEvent } from "react";
import type { Article } from "@/types";

interface NewsCardProps {
  article: Article;
  categoryName: string;
  onExplain: () => void;
  isDisabled: boolean;
}

export default function NewsCard({
  article,
  categoryName,
  onExplain,
  isDisabled,
}: NewsCardProps) {
  const handleExplainClick = (event: MouseEvent<HTMLButtonElement>) => {
    const articleEl = event.currentTarget.closest("article");
    const initialTop = articleEl?.getBoundingClientRect().top ?? null;

    onExplain();

    // Keep the clicked card visually anchored if layout above it changes.
    requestAnimationFrame(() => {
      if (!articleEl || initialTop === null) return;
      const nextTop = articleEl.getBoundingClientRect().top;
      const delta = nextTop - initialTop;
      if (Math.abs(delta) > 1) {
        window.scrollBy({ top: delta });
      }
    });
  };

  return (
    <article className="flex overflow-hidden rounded-2xl bg-neutral-100 shadow-sm dark:bg-neutral-800">
      {/* Left: text content */}
      <div className="flex min-w-0 flex-1 flex-col p-4">
        {/* Category: red-to-pink gradient text, no bubble */}
        <span className="mb-2 inline-block bg-gradient-to-r from-red-500 to-pink-400 bg-clip-text text-xs font-semibold uppercase tracking-wide text-transparent">
          {categoryName}
        </span>

        {/* Article title (prominent, like masthead) */}
        <h2 className="mb-1.5 font-serif text-lg font-bold leading-tight text-neutral-900 dark:text-white">
          {article.title}
        </h2>

        {/* Short summary */}
        <p className="mb-2 line-clamp-3 flex-1 text-sm leading-snug text-neutral-600 dark:text-neutral-300">
          {article.summary}
        </p>

        {/* Published date · Source: smaller than summary */}
        <p className="mb-3 text-[11px] leading-snug text-neutral-500 dark:text-neutral-400">
          {article.published}
          <span className="mx-1.5 font-medium text-neutral-400 dark:text-neutral-500">·</span>
          <a
            href={article.url}
            target="_blank"
            rel="noreferrer"
            className="font-medium uppercase tracking-wide no-underline hover:no-underline"
          >
            {article.source}
          </a>
        </p>

        {/* Explain this: circle with right-pointing arrow, big and obvious */}
        <button
          type="button"
          onClick={handleExplainClick}
          disabled={isDisabled}
          aria-label="Explain this article"
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-neutral-500 text-white transition hover:bg-neutral-600 focus:outline-none focus:ring-2 focus:ring-neutral-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            className="h-6 w-6"
            aria-hidden
          >
            <path
              fillRule="evenodd"
              d="M12.97 3.97a.75.75 0 0 1 1.06 0l7.5 7.5a.75.75 0 0 1 0 1.06l-7.5 7.5a.75.75 0 1 1-1.06-1.06l6.22-6.22H3a.75.75 0 0 1 0-1.5h16.19l-6.22-6.22a.75.75 0 0 1 0-1.06Z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>

      {/* Right: image with top/right margin and rounded corners */}
      <div className="flex shrink-0 items-start justify-end p-3 pr-4 pt-4">
        <div className="relative h-36 w-36 overflow-hidden rounded-xl sm:h-40 sm:w-40">
          {article.image ? (
            <img
              src={article.image}
              alt=""
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center rounded-xl bg-neutral-200 dark:bg-neutral-700">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-10 w-10 text-neutral-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14"
              />
            </svg>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
