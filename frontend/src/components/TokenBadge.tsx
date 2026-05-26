interface Props {
  label: string;
  hexid: string;
}

const LABEL_COLORS: Record<string, string> = {
  PERSON:      "bg-sky-500/12 text-sky-300 border-sky-500/25",
  EMAIL:       "bg-violet-500/12 text-violet-300 border-violet-500/25",
  PHONE:       "bg-cyan-500/12 text-cyan-300 border-cyan-500/25",
  SSN:         "bg-red-500/12 text-red-300 border-red-500/25",
  CREDIT_CARD: "bg-red-500/12 text-red-300 border-red-500/25",
  CVV:         "bg-red-500/12 text-red-300 border-red-500/25",
  DOB:         "bg-orange-500/12 text-orange-300 border-orange-500/25",
  LOCATION:    "bg-emerald-500/12 text-emerald-300 border-emerald-500/25",
  ORG:         "bg-teal-500/12 text-teal-300 border-teal-500/25",
  API_KEY:     "bg-yellow-500/12 text-yellow-300 border-yellow-500/25",
  AWS_KEY:     "bg-yellow-500/12 text-yellow-300 border-yellow-500/25",
  IP:          "bg-zinc-500/12 text-zinc-300 border-zinc-500/25",
};

const DEFAULT_COLOR = "bg-white/6 text-white/45 border-white/12";

export function TokenBadge({ label, hexid }: Readonly<Props>) {
  const colorClass = LABEL_COLORS[label] ?? DEFAULT_COLOR;
  return (
    <span
      title={`Redacted: ${label} (${hexid})`}
      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-xs leading-none ${colorClass}`}
    >
      <span className="select-none opacity-40">⊘</span>
      <span>{label}</span>
    </span>
  );
}
