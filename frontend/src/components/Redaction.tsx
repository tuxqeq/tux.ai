import React from "react";
import { useScramble } from "@/hooks/useMotion";

interface Props {
  label: string;
  hexid?: string;
  /** Just arrived in a streamed answer: draw the bar on and decode the label. */
  fresh?: boolean;
  /** Hover / keyboard focus shows the full token id. Off for compact places (sidebar titles). */
  interactive?: boolean;
}

const NAMES: Record<string, string> = {
  PER: "person",
  PERSON: "person",
  ORG: "organisation",
  LOC: "location",
  LOCATION: "location",
  EMAIL: "email address",
  EMAIL_ADDRESS: "email address",
  PHONE: "phone number",
  PHONE_NUMBER: "phone number",
  SSN: "social security number",
  CREDIT_CARD: "card number",
  DOB: "date of birth",
  DATE_OF_BIRTH: "date of birth",
  IP_ADDRESS: "IP address",
  BANK_ACCOUNT: "bank account",
  MRN: "medical record number",
};

export function Redaction({ label, hexid, fresh = false, interactive = true }: Readonly<Props>) {
  const shown = useScramble(label, fresh);
  const name = NAMES[label] ?? label.toLowerCase().replace(/_/g, " ");
  const token = hexid ? `${label}_${hexid}` : label;

  return (
    <span
      className="redact"
      data-fresh={fresh || undefined}
      tabIndex={interactive ? 0 : undefined}
      role="img"
      aria-label={`Hidden ${name}${hexid ? `, token ${token}` : ""}`}
      title={interactive ? undefined : token}
    >
      <span aria-hidden>{shown}</span>
      {interactive && hexid && (
        <span className="redact-id" aria-hidden>
          _{hexid}
        </span>
      )}
    </span>
  );
}

const TOKEN_RE = /\[([A-Z][A-Z_]{0,29})_([0-9a-f]{8,16})\]/g;

/**
 * Splits text into plain strings and redaction bars for every `[LABEL_hexid]` token.
 * `freshFrom`: tokens that start at or after this character offset are drawn on (streaming).
 */
export function renderTokens(
  content: string,
  opts: { freshFrom?: number; interactive?: boolean } = {},
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let last = 0;
  TOKEN_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = TOKEN_RE.exec(content)) !== null) {
    if (m.index > last) nodes.push(content.slice(last, m.index));
    nodes.push(
      <Redaction
        key={`t${m.index}`}
        label={m[1]}
        hexid={m[2]}
        interactive={opts.interactive ?? true}
        fresh={opts.freshFrom !== undefined && m.index >= opts.freshFrom}
      />,
    );
    last = m.index + m[0].length;
  }
  if (last < content.length) nodes.push(content.slice(last));
  return nodes;
}
