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

export function Sidebar({ activeId, onSelect, onNew }: Props) {
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
    <aside className="flex h-full w-64 flex-col border-r border-white/10 bg-surface">
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <span className="text-sm font-semibold tracking-wide text-white/80">tux.ai</span>
        <button
          onClick={onNew}
          className="rounded-lg p-1.5 text-white/60 hover:bg-surface-overlay hover:text-white transition-colors"
          title="New chat"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {loading && (
          <p className="px-4 py-2 text-xs text-white/30">Loading…</p>
        )}
        {!loading && sessions.length === 0 && (
          <p className="px-4 py-4 text-xs text-white/30 text-center">No chats yet</p>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => onSelect(s.id)}
            className={`group flex cursor-pointer items-center justify-between px-3 py-2 mx-2 rounded-lg transition-colors ${
              activeId === s.id
                ? "bg-accent/20 text-white"
                : "text-white/60 hover:bg-surface-raised hover:text-white"
            }`}
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm">{s.title ?? "Chat"}</p>
              <p className="text-xs opacity-50">{formatDate(s.updated_at)}</p>
            </div>
            <button
              onClick={(e) => handleDelete(e, s.id)}
              className="ml-2 hidden group-hover:block rounded p-0.5 text-white/40 hover:text-red-400 transition-colors"
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
