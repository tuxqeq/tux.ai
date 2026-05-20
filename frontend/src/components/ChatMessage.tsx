import React from "react";
import { TokenBadge } from "./TokenBadge";

interface Props {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

// Parses content and splits into text runs and token spans.
function renderContent(content: string): React.ReactNode[] {
  const TOKEN_RE = /\[([A-Z_]{1,30})_([0-9a-f]{8})\]/g;
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = TOKEN_RE.exec(content)) !== null) {
    if (match.index > last) {
      nodes.push(content.slice(last, match.index));
    }
    nodes.push(
      <TokenBadge key={match.index} label={match[1]} hexid={match[2]} />
    );
    last = match.index + match[0].length;
  }
  if (last < content.length) {
    nodes.push(content.slice(last));
  }
  return nodes;
}

export function ChatMessage({ role, content, streaming }: Props) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="mt-1 h-7 w-7 flex-shrink-0 rounded-full bg-accent/20 flex items-center justify-center text-accent text-xs font-bold">
          AI
        </div>
      )}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "bg-accent text-white rounded-br-sm"
            : "bg-surface-raised text-gray-100 rounded-bl-sm"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">
          {renderContent(content)}
          {streaming && !isUser && (
            <span className="ml-0.5 inline-block h-3.5 w-0.5 animate-pulse bg-current opacity-70 align-middle" />
          )}
        </p>
      </div>
      {isUser && (
        <div className="mt-1 h-7 w-7 flex-shrink-0 rounded-full bg-surface-overlay flex items-center justify-center text-xs font-bold text-gray-400">
          U
        </div>
      )}
    </div>
  );
}
