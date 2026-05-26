import { useEffect, useState } from "react";
import { chats, type ChatSession } from "@/lib/api";

interface Props {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 86400000) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (diff < 7 * 86400000) return d.toLocaleDateString([], { weekday: "short" });
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function Sidebar({ activeId, onSelect, onNew }: Readonly<Props>) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    chats.list().then(setSessions).finally(() => setLoading(false));
  }, [activeId]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await chats.delete(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (activeId === id) onNew();
  };

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-white/6 bg-surface-raised">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4">
        <span className="text-sm font-semibold tracking-tight">
          tux<span className="text-accent">.ai</span>
        </span>
        <button
          onClick={onNew}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-white/30 transition-colors hover:bg-white/6 hover:text-white"
          title="New chat"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
          </svg>
        </button>
      </div>

      {/* New chat row */}
      <div className="px-2 pb-2">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-white/35 transition-colors hover:bg-white/5 hover:text-white/60"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
          </svg>
          <span>New chat</span>
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 py-1">
        {loading && (
          <p className="px-3 py-2 text-xs text-white/20">Loading…</p>
        )}
        {!loading && sessions.length === 0 && (
          <p className="px-3 py-8 text-center text-xs text-white/20">No conversations yet</p>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(s.id)}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(s.id)}
            className={`group relative flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 transition-colors ${
              activeId === s.id
                ? "bg-white/6 text-white"
                : "text-white/45 hover:bg-white/4 hover:text-white/75"
            }`}
          >
            {activeId === s.id && (
              <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r-full bg-accent" />
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm">{s.title ?? "New chat"}</p>
              <p className="mt-0.5 text-xs opacity-40">{formatDate(s.updated_at)}</p>
            </div>
            <button
              onClick={(e) => handleDelete(e, s.id)}
              className="ml-2 hidden shrink-0 rounded p-0.5 text-white/20 transition-colors hover:text-white/60 group-hover:block"
              title="Delete"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
