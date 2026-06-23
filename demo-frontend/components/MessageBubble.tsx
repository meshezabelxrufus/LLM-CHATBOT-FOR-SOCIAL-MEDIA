import { Bot, User, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Message } from "@/types";

interface MessageBubbleProps {
  message: Message;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isError = message.isError === true;

  return (
    <div
      className={cn(
        "flex gap-3 animate-fade-in",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-5",
          isUser
            ? "bg-slate-800"
            : isError
            ? "bg-red-100 border border-red-200"
            : "bg-white border-2 border-slate-200"
        )}
      >
        {isUser ? (
          <User className="w-3.5 h-3.5 text-white" />
        ) : isError ? (
          <AlertCircle className="w-3.5 h-3.5 text-red-500" />
        ) : (
          <Bot className="w-3.5 h-3.5 text-slate-600" />
        )}
      </div>

      {/* Content column */}
      <div className={cn("flex flex-col gap-1 max-w-[78%]", isUser && "items-end")}>
        {/* Meta line */}
        <span className="text-[11px] text-slate-400 px-1">
          {isUser ? "You" : "Assistant"}&nbsp;·&nbsp;{formatTime(message.timestamp)}
        </span>

        {/* Bubble */}
        <div
          className={cn(
            "px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words",
            isUser
              ? "bg-slate-900 text-white rounded-2xl rounded-tr-sm"
              : isError
              ? "bg-red-50 text-red-700 border border-red-200 rounded-2xl rounded-tl-sm"
              : "bg-white text-slate-800 border border-slate-200 shadow-sm rounded-2xl rounded-tl-sm"
          )}
        >
          {message.content}
        </div>
      </div>
    </div>
  );
}
