import { Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface HeaderProps {
  isOnline: boolean;
}

export function Header({ isOnline }: HeaderProps) {
  return (
    <header className="flex-shrink-0 border-b bg-white px-6 py-3.5 flex items-center justify-between shadow-sm z-10">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-slate-900 flex items-center justify-center shadow-sm">
          <Bot className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="text-base font-semibold text-slate-900 leading-tight">
            AI Receptionist Demo
          </h1>
          <p className="text-xs text-slate-400 leading-tight">Kinderuniversiteit</p>
        </div>
      </div>

      <Badge
        className={cn(
          "gap-1.5 font-normal text-xs px-2.5 py-1 rounded-full",
          isOnline
            ? "bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-50"
            : "bg-red-50 text-red-600 border border-red-200 hover:bg-red-50"
        )}
      >
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            isOnline ? "bg-emerald-500 animate-pulse" : "bg-red-500"
          )}
        />
        {isOnline ? "Backend Online" : "Backend Offline"}
      </Badge>
    </header>
  );
}
