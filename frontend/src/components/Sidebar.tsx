import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { chats, type ChatSession, type User } from "@/lib/api";
import { useSlidingMarker } from "@/hooks/useMotion";
import { renderTokens } from "./Redaction";
import { Wordmark } from "./Wordmark";

interface Props {
  user: User;
  activeId: string | null;
  /** Bump to reload the list (a new chat was created). */
  refreshKey?: number;
  open: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onLogout: () => void;
}

const DAY = 86_400_000;

const ROLE_TEXT: Record<string, string> = {
  admin: "Admin role. You see every value.",
  analyst: "Analyst role. You see the values granted to you.",
  viewer: "Viewer role. You see the values granted to you.",
};

function groupOf(iso: string, now: number): string {
  const d = new Date(iso);
  const startOfToday = new Date(now).setHours(0, 0, 0, 0);
  if (d.getTime() >= startOfToday) return "Today";
  if (d.getTime() >= startOfToday - 6 * DAY) return "Previous 7 days";
  return "Older";
}

function stamp(iso: string, group: string): string {
  const d = new Date(iso);
  if (group === "Today") return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (group === "Previous 7 days") return d.toLocaleDateString([], { weekday: "short" });
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function Sidebar({
  user,
  activeId,
  refreshKey = 0,
  open,
  onClose,
  onSelect,
  onNew,
  onLogout,
}: Readonly<Props>) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [leaving, setLeaving] = useState<Set<string>>(new Set());
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    chats
      .list()
      .then((s) => {
        setSessions(s);
        setLoadError(false);
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const groups = useMemo(() => {
    const now = Date.now();
    const out: { name: string; items: ChatSession[] }[] = [];
    for (const s of sessions) {
      const g = groupOf(s.updated_at, now);
      const last = out[out.length - 1];
      if (last?.name === g) last.items.push(s);
      else out.push({ name: g, items: [s] });
    }
    return out;
  }, [sessions]);

  const { containerRef, markerStyle } = useSlidingMarker<HTMLDivElement>(activeId, "y", [
    sessions,
    leaving,
  ]);

  const remove = async (id: string) => {
    try {
      await chats.delete(id);
    } catch {
      return;
    }
    setLeaving((prev) => new Set(prev).add(id));
    if (activeId === id) onNew();
    window.setTimeout(() => {
      setSessions((prev) => prev.filter((s) => s.id !== id));
      setLeaving((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, 260);
  };

  return (
    <>
      {/* scrim for the mobile drawer */}
      <div
        onClick={onClose}
        aria-hidden
        className={`fixed inset-0 z-30 bg-ink/30 transition-opacity duration-200 md:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[276px] flex-col border-r border-rule bg-desk transition-transform duration-300 ease-out md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Chats"
      >
        <div className="flex h-14 shrink-0 items-center px-5">
          <Wordmark />
        </div>

        <div className="px-3 pb-3">
          <button onClick={onNew} className="btn-line w-full justify-start gap-2.5 bg-sheet/60">
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden>
              <path d="M8 2.5v11M2.5 8h11" strokeLinecap="square" />
            </svg>
            New chat
          </button>
        </div>

        <nav ref={containerRef} className="relative flex-1 overflow-y-auto px-3 pb-4">
          {/* the selection marker slides from the old chat to the new one */}
          <span
            aria-hidden
            style={markerStyle}
            className="pointer-events-none absolute left-3 right-3 top-0 rounded-md bg-sheet shadow-[inset_3px_0_0_theme(colors.ink.DEFAULT)] transition-[transform,height,opacity] duration-300 ease-out"
          />

          {loading && (
            <div className="space-y-3 px-3 pt-4" aria-label="Loading chats">
              <div className="ghost-line w-4/5" />
              <div className="ghost-line w-3/5" />
              <div className="ghost-line w-2/3" />
            </div>
          )}

          {!loading && loadError && (
            <p className="px-3 pt-4 text-xs text-alert">Chats did not load. Reload the page to try again.</p>
          )}

          {!loading && !loadError && sessions.length === 0 && (
            <p className="px-3 pt-4 text-xs text-ink-2">Your chats appear here.</p>
          )}

          {groups.map((g) => (
            <section key={g.name} className="mt-3 first:mt-0">
              <h2 className="px-3 pb-1 pt-2 text-2xs font-semibold text-ink-3">{g.name}</h2>
              <ul>
                {g.items.map((s) => (
                  <li key={s.id} className="collapse-row" data-leaving={leaving.has(s.id) || undefined}>
                    <div>
                      <div
                        data-key={s.id}
                        className={`group relative flex items-center rounded-md transition-colors duration-150 ${
                          activeId === s.id ? "text-ink" : "text-ink-2 hover:bg-sheet/50 hover:text-ink"
                        }`}
                      >
                        <button
                          onClick={() => {
                            onSelect(s.id);
                            onClose();
                          }}
                          aria-current={activeId === s.id ? "page" : undefined}
                          className="min-w-0 flex-1 rounded-md py-2 pl-3 pr-1 text-left"
                        >
                          <span className="block truncate text-sm">
                            {s.title ? renderTokens(s.title, { interactive: false }) : "New chat"}
                          </span>
                          <span className="mt-0.5 block text-2xs text-ink-3">{stamp(s.updated_at, g.name)}</span>
                        </button>
                        <button
                          onClick={() => remove(s.id)}
                          aria-label={`Delete chat ${s.title ?? ""}`.trim()}
                          title="Delete chat"
                          className="mr-1.5 grid h-7 w-7 shrink-0 place-items-center rounded text-ink-3 opacity-0 transition-[opacity,color,background-color] duration-150 hover:bg-alert-soft hover:text-alert focus-visible:opacity-100 group-hover:opacity-100"
                        >
                          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden>
                            <path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </nav>

        <footer className="shrink-0 border-t border-rule px-5 py-4">
          <p className="truncate text-sm font-medium text-ink" title={user.email}>
            {user.email}
          </p>
          <p className="mt-0.5 text-xs text-ink-2">{ROLE_TEXT[user.role] ?? user.role}</p>
          <div className="-ml-2 mt-3 flex gap-1">
            {user.role === "admin" && (
              <Link to="/admin" className="btn-quiet text-xs">
                Admin
              </Link>
            )}
            <button onClick={onLogout} className="btn-quiet text-xs">
              Sign out
            </button>
          </div>
        </footer>
      </aside>
    </>
  );
}
