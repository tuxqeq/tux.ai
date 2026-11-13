import { forwardRef, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";

interface Props {
  streaming: boolean;
  disabled?: boolean;
  disabledReason?: string;
  placeholder: string;
  onSend: (text: string) => void;
  onStop: () => void;
}

export interface ComposerHandle {
  focus: () => void;
}

const MAX_HEIGHT = 200;

export const Composer = forwardRef<ComposerHandle, Props>(function Composer(
  { streaming, disabled = false, disabledReason, placeholder, onSend, onStop },
  ref,
) {
  const [text, setText] = useState("");
  const areaRef = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({ focus: () => areaRef.current?.focus() }));

  // grow with the text (field-sizing is not in every browser yet)
  useLayoutEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
  }, [text]);

  const canSend = text.trim().length > 0 && !streaming && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSend(text);
    setText("");
  };

  return (
    <div>
      <div
        className={`flex items-end gap-2 rounded-[10px] border bg-sheet p-2 pl-4 transition-[border-color,box-shadow] duration-150 ${
          disabled
            ? "border-rule"
            : "border-rule-strong focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgb(29_32_38/0.1)]"
        }`}
      >
        <label htmlFor="composer" className="sr-only">
          Message
        </label>
        <textarea
          id="composer"
          ref={areaRef}
          value={text}
          rows={1}
          disabled={disabled}
          placeholder={disabled && disabledReason ? disabledReason : placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          className="max-h-[200px] flex-1 resize-none self-center bg-transparent py-1.5 text-base text-ink outline-none placeholder:text-ink-3 disabled:cursor-not-allowed"
        />

        <button
          type="button"
          onClick={streaming ? onStop : submit}
          disabled={!streaming && !canSend}
          aria-label={streaming ? "Stop the answer" : "Send"}
          title={streaming ? "Stop" : "Send"}
          className="relative grid h-9 w-9 shrink-0 place-items-center rounded-md bg-ink text-sheet transition-[background-color,opacity,transform] duration-150 hover:bg-toner active:scale-95 disabled:bg-rule disabled:text-ink-3"
        >
          {/* arrow and stop square swap places with a quarter turn */}
          <svg
            viewBox="0 0 16 16"
            className={`absolute h-4 w-4 transition-[opacity,transform] duration-200 ease-out ${
              streaming ? "rotate-90 scale-50 opacity-0" : "opacity-100"
            }`}
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            aria-hidden
          >
            <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" strokeLinecap="square" />
          </svg>
          <svg
            viewBox="0 0 16 16"
            className={`absolute h-3 w-3 transition-[opacity,transform] duration-200 ease-out ${
              streaming ? "opacity-100" : "-rotate-90 scale-50 opacity-0"
            }`}
            fill="currentColor"
            aria-hidden
          >
            <rect x="2" y="2" width="12" height="12" />
          </svg>
        </button>
      </div>
      <p className="mt-2 hidden text-2xs text-ink-3 sm:block">
        Enter sends. Shift+Enter adds a new line.
      </p>
    </div>
  );
});
