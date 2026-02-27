"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import type { Lang } from "@/types";

interface StreamedResponseProps {
  content: string;
  isStreaming: boolean;
  lang: Lang;
}

const LOADING_LABEL = {
  en: "Reading and summarizing…",
  zh: "阅读中… 可先浏览下方其他新闻。",
} as const;

const markdownComponents: Components = {
  h1: ({ ...props }) => (
    <h1 className="mb-3 mt-4 text-2xl font-semibold text-neutral-900 dark:text-white" {...props} />
  ),
  h2: ({ ...props }) => (
    <h2 className="mb-2 mt-4 text-xl font-semibold text-neutral-900 dark:text-white" {...props} />
  ),
  h3: ({ ...props }) => (
    <h3 className="mb-2 mt-3 text-lg font-semibold text-neutral-900 dark:text-white" {...props} />
  ),
  p: ({ ...props }) => (
    <p className="mb-3 text-base leading-relaxed text-neutral-700 dark:text-neutral-300" {...props} />
  ),
  strong: ({ ...props }) => (
    <strong className="font-semibold text-neutral-900 dark:text-neutral-100" {...props} />
  ),
  ul: ({ ...props }) => (
    <ul className="mb-3 ml-4 list-disc space-y-1 text-base text-neutral-700 dark:text-neutral-300" {...props} />
  ),
  ol: ({ ...props }) => (
    <ol className="mb-3 ml-4 list-decimal space-y-1 text-base text-neutral-700 dark:text-neutral-300" {...props} />
  ),
  li: ({ ...props }) => <li className="leading-relaxed" {...props} />,
  a: ({ ...props }) => (
    <a
      {...props}
      target="_blank"
      rel="noopener noreferrer"
      className="text-neutral-700 no-underline hover:underline dark:text-neutral-300 dark:hover:text-neutral-100"
    >
      ({props.children})
    </a>
  ),
  img: ({ alt, ...props }) => (
    <img {...props} alt={alt ?? ""} className="rounded-lg" loading="lazy" />
  ),
  blockquote: ({ ...props }) => (
    <blockquote
      className="my-4 rounded-r-md border-l-4 border-neutral-400 bg-neutral-100 py-2 pl-4 pr-4 text-base leading-relaxed text-neutral-700 dark:border-neutral-500 dark:bg-neutral-700/50 dark:text-neutral-300"
      {...props}
    />
  ),
};

export default function StreamedResponse({
  content,
  isStreaming,
  lang,
}: StreamedResponseProps) {
  const loadingLabel = LOADING_LABEL[lang];
  const showLoadingPlaceholder = isStreaming && !content;

  return (
    <div className="max-w-none">
      {showLoadingPlaceholder ? (
        <span className="animate-pulse text-base text-neutral-600 dark:text-neutral-400">
          {loadingLabel}
        </span>
      ) : (
        <>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {content}
          </ReactMarkdown>
          {isStreaming && (
            <span className="ml-1 inline-block h-4 w-0.5 animate-pulse bg-neutral-500 dark:bg-neutral-400" />
          )}
        </>
      )}
    </div>
  );
}
