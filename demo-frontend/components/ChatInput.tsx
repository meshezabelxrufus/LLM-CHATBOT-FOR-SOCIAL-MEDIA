"use client";

import { useRef, useState } from "react";
import { SendHorizonal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { SuggestionChips } from "./SuggestionChips";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = value.trim().length > 0 && !isLoading;

  function handleSend() {
    const trimmed = value.trim();
    if (!trimmed || isLoading) return;
    onSend(trimmed);
    setValue("");
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setValue(e.target.value);
    // Auto-grow
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  function handleChipSelect(question: string) {
    onSend(question);
  }

  return (
    <div className="flex-shrink-0 border-t border-slate-200 bg-white px-4 py-3 space-y-2">
      {/* Suggestion chips */}
      <SuggestionChips onSelect={handleChipSelect} disabled={isLoading} />

      {/* Input row */}
      <div className="flex items-end gap-2">
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Type your message… (Shift+Enter for new line)"
          disabled={isLoading}
          rows={1}
          className="resize-none min-h-[42px] max-h-40 overflow-y-auto rounded-xl border-slate-200 bg-slate-50 text-sm placeholder:text-slate-400 focus-visible:ring-1 focus-visible:ring-slate-400 transition-all"
        />
        <Button
          onClick={handleSend}
          disabled={!canSend}
          size="icon"
          className="h-[42px] w-[42px] rounded-xl bg-slate-900 hover:bg-slate-700 flex-shrink-0 transition-all"
          aria-label="Send message"
        >
          <SendHorizonal className="w-4 h-4" />
        </Button>
      </div>

      <p className="text-[11px] text-slate-400 text-center">
        Demo mode — responses come from the live FastAPI backend.
      </p>
    </div>
  );
}
