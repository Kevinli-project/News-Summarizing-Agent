"use client";

import { useState } from "react";

interface FollowUpBarProps {
  onSubmit: (message: string) => void;
  isDisabled: boolean;
  placeholder?: string;
}

export default function FollowUpBar({
  onSubmit,
  isDisabled,
  placeholder = "Ask a follow-up...",
}: FollowUpBarProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || isDisabled) return;
    onSubmit(trimmed);
    setValue("");
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-4 flex gap-2 border-t border-neutral-200 pt-4 dark:border-neutral-600"
    >
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        disabled={isDisabled}
        className="flex-1 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm placeholder:text-neutral-400 focus:border-neutral-400 focus:outline-none focus:ring-1 focus:ring-neutral-400 dark:border-neutral-600 dark:bg-neutral-800 dark:placeholder:text-neutral-500 dark:focus:border-neutral-500 dark:focus:ring-neutral-500"
        aria-label="Follow-up question"
      />
      <button
        type="submit"
        disabled={isDisabled || !value.trim()}
        className="rounded-lg bg-neutral-700 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-600 disabled:opacity-50 dark:bg-neutral-600 dark:hover:bg-neutral-500"
      >
        Send
      </button>
    </form>
  );
}
