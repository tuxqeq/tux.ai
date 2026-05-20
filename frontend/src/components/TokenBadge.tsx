/**
 * Renders a [LABEL_hexid] token as a styled pill.
 * visible=true means the plaintext was already substituted (server decrypted it)
 * and the surrounding text shows it normally — this badge is only shown for
 * tokens that remain unreplaced (visible=false).
 */
interface Props {
  label: string;
  hexid: string;
}

const LABEL_COLORS: Record<string, string> = {
  PERSON: "bg-blue-900/50 text-blue-300 border-blue-700",
  EMAIL: "bg-violet-900/50 text-violet-300 border-violet-700",
  PHONE: "bg-cyan-900/50 text-cyan-300 border-cyan-700",
  SSN: "bg-red-900/50 text-red-300 border-red-700",
  CREDIT_CARD: "bg-red-900/50 text-red-300 border-red-700",
  CVV: "bg-red-900/50 text-red-300 border-red-700",
  DOB: "bg-orange-900/50 text-orange-300 border-orange-700",
  LOCATION: "bg-emerald-900/50 text-emerald-300 border-emerald-700",
  ORG: "bg-teal-900/50 text-teal-300 border-teal-700",
  API_KEY: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  AWS_KEY: "bg-yellow-900/50 text-yellow-300 border-yellow-700",
  IP: "bg-slate-700/50 text-slate-300 border-slate-600",
};

const DEFAULT_COLOR = "bg-zinc-800/60 text-zinc-400 border-zinc-600";

export function TokenBadge({ label, hexid }: Props) {
  const colorClass = LABEL_COLORS[label] ?? DEFAULT_COLOR;
  return (
    <span
      title={`Redacted: ${label} (${hexid})`}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-xs leading-none ${colorClass}`}
    >
      <span className="opacity-60 select-none">⊘</span>
      <span>{label}</span>
    </span>
  );
}
