import { Button } from "@/components/ui/button";

const SUGGESTIONS: { emoji: string; label: string; question: string }[] = [
  {
    emoji: "🏕",
    label: "Holiday Camps",
    question: "What holiday camps do you offer?",
  },
  {
    emoji: "💶",
    label: "Pricing",
    question: "What are your prices for the camps?",
  },
  {
    emoji: "🎂",
    label: "Birthday Parties",
    question: "Do you offer birthday party packages?",
  },
  {
    emoji: "📅",
    label: "Opening Hours",
    question: "What are your opening hours?",
  },
  {
    emoji: "📍",
    label: "Location",
    question: "Where are your locations?",
  },
  {
    emoji: "📞",
    label: "Contact",
    question: "How can I contact Kinderuniversiteit?",
  },
];

interface SuggestionChipsProps {
  onSelect: (question: string) => void;
  disabled: boolean;
}

export function SuggestionChips({ onSelect, disabled }: SuggestionChipsProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {SUGGESTIONS.map(({ emoji, label, question }) => (
        <Button
          key={label}
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => onSelect(question)}
          className="h-7 px-3 text-xs rounded-full border-slate-200 text-slate-500 hover:text-slate-900 hover:border-slate-300 hover:bg-slate-50 transition-all"
        >
          <span className="mr-1">{emoji}</span>
          {label}
        </Button>
      ))}
    </div>
  );
}
