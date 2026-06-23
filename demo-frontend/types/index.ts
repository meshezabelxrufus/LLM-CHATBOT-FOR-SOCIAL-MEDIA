export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isError?: boolean;
}

export interface HistoryEntry {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  message: string;
  history: HistoryEntry[];
}

export interface ChatResponse {
  reply: string;
  confidence: number;
  sources: string[];
}
