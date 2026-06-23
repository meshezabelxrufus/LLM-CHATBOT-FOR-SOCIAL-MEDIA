import { Globe, MessageSquare, Server, Shield, User } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface InfoRowProps {
  icon: React.ElementType;
  label: string;
  value: string;
  /** When true, renders a green pill instead of plain text. */
  pill?: boolean;
}

function InfoRow({ icon: Icon, label, value, pill }: InfoRowProps) {
  return (
    <div className="flex items-center justify-between py-0.5">
      <div className="flex items-center gap-2 text-slate-400">
        <Icon className="w-3.5 h-3.5" />
        <span className="text-xs">{label}</span>
      </div>
      {pill ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-xs text-emerald-700 font-medium">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          {value}
        </span>
      ) : (
        <span className="text-xs font-medium text-slate-800">{value}</span>
      )}
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="w-full lg:w-64 xl:w-72 flex-shrink-0">
      <Card className="shadow-sm border-slate-200">
        <CardHeader className="pb-3 pt-5 px-5">
          <CardTitle className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
            Customer Information
          </CardTitle>
        </CardHeader>

        <CardContent className="px-5 pb-5 space-y-3">
          <InfoRow icon={User} label="Name" value="Demo User" />
          <Separator />
          <InfoRow icon={MessageSquare} label="Channel" value="WhatsApp" />
          <Separator />
          <InfoRow icon={Globe} label="Locale" value="nl_NL" />
          <Separator />
          <InfoRow icon={Shield} label="Status" value="Active" pill />
          <Separator />
          <InfoRow icon={Server} label="Backend" value="Connected" pill />
        </CardContent>
      </Card>

      {/* Session stats — decorative for the demo */}
      <div className="mt-3 rounded-lg border border-slate-200 bg-white shadow-sm p-4 space-y-2">
        <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">
          Session
        </p>
        <div className="flex justify-between text-xs text-slate-500">
          <span>Model</span>
          <span className="font-medium text-slate-800">Claude Haiku</span>
        </div>
        <div className="flex justify-between text-xs text-slate-500">
          <span>RAG</span>
          <span className="font-medium text-slate-800">Multilingual KB</span>
        </div>
        <div className="flex justify-between text-xs text-slate-500">
          <span>Language</span>
          <span className="font-medium text-slate-800">Auto-detect</span>
        </div>
      </div>
    </aside>
  );
}
