import { useCallback, useEffect, useRef, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatMessage } from "@/components/ChatMessage";
import { useChat } from "@/hooks/useChat";
import { chats, type User, type Message } from "@/lib/api";

interface Props {
  user: User;
  onLogout: () => void;
}

const ROLE_STYLE: Record<string, string> = {
  admin: "text-rose-400 bg-rose-400/10",
  analyst: "text-amber-400 bg-amber-400/10",
  viewer: "text-emerald-400 bg-emerald-400/10",
};

export function Chat({ user, onLogout }: Readonly<Props>) {
  const [sessionId, setSessionId] = useState<string>("");
  const [datasetId] = useState<string>("");
  const [historicMessages, setHistoricMessages] = useState<Message[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [input, setInput] = useState("");

  const { messages, setMessages, streaming, error, send } = useChat({
    sessionId,
    datasetId,
    onSessionCreated: setSessionId,
  });

  useEffect(() => {
    if (!sessionId) {
      setHistoricMessages([]);
      return;
    }
    chats.get(sessionId).then((s) => setHistoricMessages(s.messages));
  }, [sessionId]);

  const allMessages = [...historicMessages, ...messages];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [allMessages.length, messages]);

  const handleNew = useCallback(() => {
    setSessionId("");
    setHistoricMessages([]);
    setMessages([]);
  }, [setMessages]);

  const handleSelect = useCallback(
    (id: string) => {
      setSessionId(id);
      setMessages([]);
    },
    [setMessages]
  );

  const handleSend = () => {
    if (!input.trim()) return;
    send(input);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      <Sidebar activeId={sessionId || null} onSelect={handleSelect} onNew={handleNew} />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <header className="flex h-13 shrink-0 items-center justify-between border-b border-white/6 px-5">
          <span className="text-sm font-medium text-white/25">
            {sessionId ? "Chat" : "tux​.ai"}
          </span>
          <div className="flex items-center gap-1.5">
            <span
              className={`rounded-md px-2 py-0.5 text-xs font-medium ${ROLE_STYLE[user.role] ?? "text-white/40 bg-white/6"}`}
            >
              {user.role}
            </span>
            <span className="text-xs text-white/20">{user.email}</span>
            {user.role === "admin" && (
              <a
                href="/admin"
                className="ml-1 rounded-md px-2 py-1 text-xs text-white/30 transition-colors hover:bg-white/6 hover:text-white/60"
              >
                Admin
              </a>
            )}
            <button
              onClick={onLogout}
              className="rounded-md px-2 py-1 text-xs text-white/30 transition-colors hover:bg-white/6 hover:text-white/60"
            >
              Sign out
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {allMessages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center px-4 text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 ring-1 ring-accent/15">
                <svg
                  className="h-5 w-5 text-accent"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
                  />
                </svg>
              </div>
              <h2 className="text-base font-medium">
                tux<span className="text-accent">.ai</span>
              </h2>
              <p className="mt-2 max-w-[280px] text-sm leading-relaxed text-white/30">
                Messages are tokenized before reaching the model. PII surfaces based on your access level.
              </p>
            </div>
          ) : (
            <div className="mx-auto max-w-2xl space-y-0.5 px-4 py-6">
              {allMessages.map((msg, i) => (
                <ChatMessage
                  key={msg.id ?? i}
                  role={msg.role}
                  content={msg.content}
                  streaming={streaming && i === allMessages.length - 1 && msg.role === "assistant"}
                />
              ))}
              {error && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/8 px-4 py-3 text-sm text-red-300">
                  {error}
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="shrink-0 border-t border-white/6 px-4 py-4">
          <div className="mx-auto max-w-2xl">
            <div className="flex items-end gap-3 rounded-2xl border border-white/8 bg-surface-raised px-4 py-3 transition-all focus-within:border-accent/20 focus-within:ring-2 focus-within:ring-accent/5">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message tux.ai…"
                rows={1}
                className="flex-1 resize-none bg-transparent text-sm text-white/90 placeholder-white/20 outline-none"
                style={{ maxHeight: "160px" }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || streaming}
                className="mb-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent text-black/70 transition-all hover:bg-accent-hover disabled:opacity-30"
                title="Send"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-3.5 w-3.5"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                </svg>
              </button>
            </div>
            <p className="mt-2 text-center text-xs text-white/15">
              PII is automatically tokenized · Shift+Enter for new line
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
