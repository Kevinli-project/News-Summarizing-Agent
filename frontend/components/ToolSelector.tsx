"use client";

import { useState, useRef, useEffect } from "react";
import type { Lang, ToolType } from "@/types";

interface ToolSelectorProps {
  selectedTool: null | ToolType;
  onToolChange: (tool: null | ToolType) => void;
  lang: Lang;
}

const LABELS = {
  en: {
    show_news: "Search topics",
    web_search: "Internet search",
  },
  zh: {
    show_news: "搜索主题",
    web_search: "网络搜索",
  },
} as const;

export default function ToolSelector({
  selectedTool,
  onToolChange,
  lang,
}: ToolSelectorProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const labels = LABELS[lang];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (tool: ToolType) => {
    onToolChange(selectedTool === tool ? null : tool);
    setOpen(false);
  };

  return (
    <div ref={containerRef} className="relative flex items-center gap-2">
      {/* + button */}
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-neutral-300 bg-neutral-100 text-neutral-600 transition-colors hover:bg-neutral-200 hover:text-neutral-800 dark:border-neutral-600 dark:bg-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-600 dark:hover:text-white"
        aria-label={lang === "zh" ? "选择工具" : "Choose tool"}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <span className="text-lg leading-none">+</span>
      </button>

      {/* Dropdown (opens upward, compact so it fits inside the card) */}
      {open && (
        <div
          className="absolute bottom-full left-0 z-10 mb-1 flex flex-col rounded-md border border-neutral-200 bg-white py-0.5 shadow-lg dark:border-neutral-600 dark:bg-neutral-800"
          role="menu"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => handleSelect("show_news")}
            className="whitespace-nowrap px-3 py-1.5 text-left text-xs text-neutral-800 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-neutral-700"
          >
            {labels.show_news}
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => handleSelect("web_search")}
            className="whitespace-nowrap px-3 py-1.5 text-left text-xs text-neutral-800 hover:bg-neutral-100 dark:text-neutral-200 dark:hover:bg-neutral-700"
          >
            {labels.web_search}
          </button>
        </div>
      )}

      {/* Selected tool chip (round pill) */}
      {selectedTool && (
        <button
          type="button"
          onClick={() => onToolChange(null)}
          className="inline-flex items-center gap-1 rounded-full bg-neutral-200 px-3 py-1.5 text-xs font-medium text-neutral-800 transition-colors hover:bg-neutral-300 dark:bg-neutral-600 dark:text-white dark:hover:bg-neutral-500"
          aria-label={lang === "zh" ? "取消选择" : "Clear selection"}
        >
          {selectedTool === "show_news" ? labels.show_news : labels.web_search}
          <span className="ml-0.5 text-neutral-500 dark:text-neutral-400" aria-hidden>×</span>
        </button>
      )}
    </div>
  );
}
