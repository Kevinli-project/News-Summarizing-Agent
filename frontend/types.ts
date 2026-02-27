export interface Article {
  title: string;
  summary: string;
  image: string | null;
  url: string;
  source: string;
  published: string;
}

export interface Category {
  name: string;
  articles: Article[];
}

export interface NewsResponse {
  categories: Category[];
}

export type Lang = "en" | "zh";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type ToolType = "show_news" | "web_search";
