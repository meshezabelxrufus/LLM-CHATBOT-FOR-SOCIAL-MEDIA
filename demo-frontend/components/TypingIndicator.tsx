import { Bot } from "lucide-react";

export function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade-in">
      {/* Avatar */}
      <div className="w-7 h-7 rounded-full bg-white border-2 border-slate-200 flex items-center justify-center flex-shrink-0 mt-5">
        <Bot className="w-3.5 h-3.5 text-slate-600" />
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-[11px] text-slate-400 px-1">Assistant</span>

        <div className="bg-white border border-slate-200 shadow-sm rounded-2xl rounded-tl-sm px-4 py-3.5 inline-flex items-center gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-2 w-2 rounded-full bg-slate-300"
              style={{
                animation: "bounce-dot 1.4s infinite ease-in-out both",
                animationDelay: `${i * 0.16}s`,
              }}
            />
          ))}
        </div>

        <span className="text-[11px] text-slate-400 px-1 italic">
          Assistant is typing…
        </span>
      </div>
    </div>
  );
}
