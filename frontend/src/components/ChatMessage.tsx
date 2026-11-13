import { useEffect, useState } from "react";
import { renderTokens } from "./Redaction";

interface Props {
  role: "user" | "assistant";
  content: string;
  /** The answer is still streaming in. */
  streaming?: boolean;
  /** Sent or received in this visit (not loaded from history): animate its arrival. */
  live?: boolean;
}

/**
 * One transcript entry. Speaker in the left gutter, text in a single reading column,
 * like a deposition transcript: both speakers share the same measure.
 */
export function ChatMessage({ role, content, streaming = false, live = false }: Readonly<Props>) {
  const isUser = role === "user";
  const waiting = streaming && content.length === 0;

  return (
    <article
      className={`grid grid-cols-1 gap-x-6 gap-y-1 py-4 sm:grid-cols-[72px_minmax(0,1fr)] ${
        live ? "rise" : ""
      }`}
      aria-busy={streaming || undefined}
    >
      <div
        className={`pt-[3px] text-xs font-semibold sm:text-right ${isUser ? "text-ink-2" : "text-ink"}`}
      >
        {isUser ? "You" : "tux.ai"}
      </div>

      {waiting ? (
        <WaitingLines />
      ) : (
        <div
          className={`whitespace-pre-wrap break-words text-base ${
            isUser ? "text-ink-2" : "text-ink"
          }`}
        >
          {renderTokens(content, { freshFrom: live && !isUser ? 0 : undefined })}
          {streaming && <span className="caret" aria-hidden />}
        </div>
      )}
    </article>
  );
}

/** Shown until the first chunk arrives. After 3 s it counts, because a cold start can take minutes. */
function WaitingLines() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const t0 = Date.now();
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - t0) / 1000)), 500);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="pt-1.5" role="status">
      <div className="flex max-w-md flex-col gap-2.5" aria-hidden>
        <div className="ghost-line w-[92%]" />
        <div className="ghost-line w-[68%] after:[animation-delay:180ms]" />
      </div>
      <p className="mt-3 text-xs text-ink-3">
        {seconds < 3 ? "Waiting for the model" : `Waiting for the model, ${seconds} s`}
      </p>
    </div>
  );
}
