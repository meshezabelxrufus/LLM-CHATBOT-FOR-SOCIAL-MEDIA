"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./MessageBubble";
import { TypingIndicator } from "./TypingIndicator";
import { ChatInput } from "./ChatInput";
import type { Message } from "@/types";

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
  onSend: (message: string) => void;
}

export function ChatWindow({ messages, isLoading, onSend }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom whenever messages or loading state changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex flex-col flex-1 min-h-0 bg-slate-50 rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      {/* Section label */}
      <div className="flex-shrink-0 px-5 py-3 border-b border-slate-200 bg-white">
        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
          Conversation
        </p>
      </div>

      {/* Message list */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="flex flex-col gap-5 px-5 py-5">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* Animated typing indicator while awaiting response */}
          {isLoading && <TypingIndicator />}

          {/* Invisible anchor for auto-scroll */}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Input area pinned to bottom */}
      <ChatInput onSend={onSend} isLoading={isLoading} />
    </div>
  );
}
