import { useState } from "react";

export interface ToastMessage {
  id: number;
  text: string;
  tone: "ok" | "error";
}

/**
 * One message at a time, bottom right. The line under the text drains while the toast is
 * shown; pointing at the toast pauses it. Errors stay longer.
 */
export function Toast({
  msg,
  onDone,
}: Readonly<{ msg: ToastMessage | null; onDone: (id: number) => void }>) {
  const [leaving, setLeaving] = useState<number | null>(null);
  if (!msg) return null;

  const dismiss = () => {
    setLeaving(msg.id);
    window.setTimeout(() => onDone(msg.id), 200);
  };

  const isError = msg.tone === "error";
  return (
    <div
      key={msg.id}
      role={isError ? "alert" : "status"}
      className={`group fixed bottom-5 right-5 z-50 w-[min(380px,calc(100vw-2.5rem))] overflow-hidden rounded-md bg-ink text-sheet shadow-[0_8px_24px_-8px_rgb(0_0_0/0.35)] transition-[opacity,transform] duration-200 ease-out ${
        leaving === msg.id ? "translate-y-2 opacity-0" : "rise"
      }`}
    >
      <div className="flex items-start gap-3 px-4 py-3">
        {isError && (
          <span className="mt-[7px] h-2 w-2 shrink-0 rounded-full bg-[#F28B82]" aria-hidden />
        )}
        <p className="flex-1 text-sm">{msg.text}</p>
        <button
          onClick={dismiss}
          className="-mr-1 rounded px-1.5 text-sm text-sheet/60 hover:text-sheet"
          aria-label="Close message"
        >
          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden>
            <path d="m4 4 8 8M12 4l-8 8" />
          </svg>
        </button>
      </div>
      <div
        className="toast-timer h-[3px] origin-left bg-sheet/40 group-hover:[animation-play-state:paused]"
        style={{ animation: `drain ${isError ? 7000 : 4000}ms linear both` }}
        onAnimationEnd={dismiss}
      />
    </div>
  );
}
