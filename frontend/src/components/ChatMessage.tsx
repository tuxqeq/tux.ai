import React from "react";
import { TokenBadge } from "./TokenBadge";

interface Props {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

function renderContent(content: string): React.ReactNode[] {
  const TOKEN_RE = /\[([A-Z_]{1,30})_([0-9a-f]{8})\]/g;
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = TOKEN_RE.exec(content)) !== null) {
    if (match.index > last) nodes.push(content.slice(last, match.index));
    nodes.push(<TokenBadge key={match.index} label={match[1]} hexid={match[2]} />);
    last = match.index + match[0].length;
  }
  if (last < content.length) nodes.push(content.slice(last));
  return nodes;
}

export function ChatMessage({ role, content, streaming }: Readonly<Props>) {
  if (role === "user") {
    return (
      <div className="flex justify-end py-2">
        <div className="max-w-[75%] rounded-2xl rounded-br-md bg-white/6 px-4 py-2.5 text-sm leading-relaxed text-white/85">
          <p className="whitespace-pre-wrap break-words">{renderContent(content)}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 py-3">
      <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/12 ring-1 ring-accent/20">
        <svg
          className="h-3.5 w-3.5 text-accent"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.75}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
          />
        </svg>
      </div>
      <div className="flex-1 pt-0.5 text-sm leading-relaxed text-white/75">
        <p className="whitespace-pre-wrap break-words">
          {renderContent(content)}
          {streaming && (
            <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-accent/60 align-middle" />
          )}
        </p>
      </div>
    </div>
  );
}
