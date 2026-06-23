"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { ChatWindow } from "@/components/ChatWindow";
import { sendMessage } from "@/lib/api";
import type { Message, HistoryEntry } from "@/types";

function uid() {
  return typeof crypto !== "undefined"
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);
}

/** The initial greeting shown before the user types anything. */
const INITIAL_MESSAGE: Message = {
  id: "greeting",
  role: "assistant",
  content:
    "Hello! I'm your AI Receptionist for Kinderuniversiteit. How can I help you today?",
  timestamp: new Date(),
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([INITIAL_MESSAGE]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOnline, setIsOnline] = useState(true);

  /** Ping the backend on mount to determine the header badge status. */
  useEffect(() => {
    const controller = new AbortController();
    fetch("/backend/health", { signal: controller.signal })
      .then((r) => setIsOnline(r.ok))
      .catch(() => setIsOnline(false));
    return () => controller.abort();
  }, []);

  const handleSend = useCallback(
    async (text: string) => {
      if (isLoading) return;

      // Append user message immediately
      const userMsg: Message = {
        id: uid(),
        role: "user",
        content: text,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      // Build conversation history (exclude the greeting, exclude the message we just added)
      const history: HistoryEntry[] = messages
        .filter((m) => m.id !== "greeting" && !m.isError)
        .map((m) => ({ role: m.role, content: m.content }));

      try {
        const reply = await sendMessage(text, history);

        const assistantMsg: Message = {
          id: uid(),
          role: "assistant",
          content: reply,
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, assistantMsg]);
        setIsOnline(true);
      } catch (err) {
        const errorMsg: Message = {
          id: uid(),
          role: "assistant",
          content:
            err instanceof Error
              ? err.message
              : "Sorry, something went wrong. Please try again.",
          timestamp: new Date(),
          isError: true,
        };

        setMessages((prev) => [...prev, errorMsg]);
        setIsOnline(false);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, messages]
  );

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-slate-100">
      {/* ── Top header bar ── */}
      <Header isOnline={isOnline} />

      {/* ── Body: sidebar + chat ── */}
      <main className="flex flex-col lg:flex-row flex-1 min-h-0 gap-4 p-4 lg:p-5 overflow-y-auto lg:overflow-hidden">
        {/* Sidebar — full width on mobile, fixed width on desktop */}
        <div className="w-full lg:w-64 xl:w-72 flex-shrink-0">
          <Sidebar />
        </div>

        {/* Chat panel */}
        <div className="flex flex-col flex-1 min-h-0 min-w-0" style={{ minHeight: "500px" }}>
          <ChatWindow
            messages={messages}
            isLoading={isLoading}
            onSend={handleSend}
          />
        </div>
      </main>
    </div>
  );
}
