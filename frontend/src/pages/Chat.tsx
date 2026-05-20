import { useCallback, useEffect, useRef, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatMessage } from "@/components/ChatMessage";
import { useChat } from "@/hooks/useChat";
import { chats, type User, type Message } from "@/lib/api";

interface Props {
  user: User;
  onLogout: () => void;
}

export function Chat({ user, onLogout }: Props) {
  const [sessionId, setSessionId] = useState<string>("");
  const [datasetId] = useState<string>("");  // TODO: dataset picker in future iteration
  const [historicMessages, setHistoricMessages] = useState<Message[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [input, setInput] = useState("");

  const { messages, setMessages, streaming, error, send } = useChat({
    sessionId,
    datasetId,
    onSessionCreated: setSessionId,
  });

  // Load historic messages when switching sessions
  useEffect(() => {
    if (!sessionId) {
      setHistoricMessages([]);
      return;
    }
    chats.get(sessionId).then((s) => setHistoricMessages(s.messages));
  }, [sessionId]);

  // Merge: show historic messages then live streaming messages
  const allMessages = [...historicMessages, ...messages];

  // Auto-scroll on new content
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
        {/* Top bar */}
        <header className="flex items-center justify-between border-b border-white/10 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-white/60">
              {sessionId ? "Chat" : "New Chat"}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-white/40">
              <span
                className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full ${
                  { admin: "bg-red-400", analyst: "bg-yellow-400", viewer: "bg-green-400" }[
                    user.role
                  ]
                }`}
              />
              {user.role}
            </span>
            <span className="text-xs text-white/40">{user.email}</span>
            {user.role === "admin" && (
              <a
                href="/admin"
                className="rounded px-2 py-1 text-xs text-white/50 hover:bg-surface-overlay hover:text-white transition-colors"
              >
                Admin
              </a>
            )}
            <button
              onClick={onLogout}
              className="rounded px-2 py-1 text-xs text-white/50 hover:bg-surface-overlay hover:text-white transition-colors"
            >
              Sign out
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {allMessages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-3 text-4xl">🔒</div>
              <h2 className="text-lg font-medium text-white/80">tux.ai Chat</h2>
              <p className="mt-2 max-w-sm text-sm text-white/40">
                Your messages are tokenized before being sent to the model. PII in
                responses appears based on your access level.
              </p>
            </div>
          )}
          <div className="mx-auto max-w-2xl space-y-4">
            {allMessages.map((msg, i) => (
              <ChatMessage
                key={msg.id ?? i}
                role={msg.role as "user" | "assistant"}
                content={msg.content}
                streaming={streaming && i === allMessages.length - 1 && msg.role === "assistant"}
              />
            ))}
            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-900/20 px-3 py-2 text-sm text-red-400">
                Error: {error}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input */}
        <div className="border-t border-white/10 p-4">
          <div className="mx-auto max-w-2xl">
            <div className="flex items-end gap-2 rounded-2xl border border-white/10 bg-surface-raised px-4 py-3 focus-within:border-accent/50 transition-colors">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message tux.ai… (Shift+Enter for new line)"
                rows={1}
                className="flex-1 resize-none bg-transparent text-sm text-white placeholder-white/25 outline-none"
                style={{ maxHeight: "140px" }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || streaming}
                className="mb-0.5 rounded-lg bg-accent p-1.5 text-white disabled:opacity-40 hover:bg-accent-hover transition-colors"
                title="Send"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                </svg>
              </button>
            </div>
            <p className="mt-2 text-center text-xs text-white/20">
              PII in your messages is automatically tokenized before reaching the model.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
