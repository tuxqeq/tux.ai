import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatMessage } from "@/components/ChatMessage";
import { Composer, type ComposerHandle } from "@/components/Composer";
import { DatasetPicker } from "@/components/DatasetPicker";
import { Redaction } from "@/components/Redaction";
import { useChat } from "@/hooks/useChat";
import { chats, datasets, type ChatDataset, type Message, type User } from "@/lib/api";

interface Props {
  user: User;
  onLogout: () => void;
}

const LAST_DATASET = "tux.lastDataset";

function readLastDataset(): string {
  try {
    return localStorage.getItem(LAST_DATASET) ?? "";
  } catch {
    return "";
  }
}

export function Chat({ user, onLogout }: Readonly<Props>) {
  const [sessionId, setSessionId] = useState("");
  // D-29: a new chat needs a dataset (otherwise nothing is tokenized and RAG is off);
  // an existing chat keeps the dataset it was started with.
  const [datasetId, setDatasetId] = useState(readLastDataset);
  // dataset of the open chat (a chat stays bound to the dataset it started with)
  const [boundDatasetId, setBoundDatasetId] = useState("");
  const [options, setOptions] = useState<ChatDataset[] | null>(null);
  const [history, setHistory] = useState<Message[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // a session that the live stream created: its messages are already on screen
  const createdHere = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<ComposerHandle>(null);
  const stickToBottom = useRef(true);

  const datasetRef = useRef(datasetId);
  datasetRef.current = datasetId;
  const onSessionCreated = useCallback((id: string) => {
    createdHere.current = id;
    setBoundDatasetId(datasetRef.current);
    setSessionId(id);
  }, []);
  const onAnswerDone = useCallback(() => setRefreshKey((k) => k + 1), []);

  const { messages, setMessages, streaming, error, send, stop } = useChat({
    sessionId,
    datasetId,
    onSessionCreated,
    onAnswerDone,
  });

  // datasets the user can chat with
  useEffect(() => {
    datasets
      .list()
      .then((list) => {
        setOptions(list);
        setDatasetId((cur) => (list.some((d) => d.id === cur) ? cur : list[0]?.id ?? ""));
      })
      .catch(() => setOptions([]));
  }, []);

  useEffect(() => {
    try {
      if (datasetId) localStorage.setItem(LAST_DATASET, datasetId);
    } catch {
      /* storage can be blocked; the choice then lasts for this visit only */
    }
  }, [datasetId]);

  // history of a chat picked in the sidebar
  useEffect(() => {
    if (!sessionId || sessionId === createdHere.current) return;
    let cancelled = false;
    setHistoryLoading(true);
    chats
      .get(sessionId)
      .then((s) => {
        if (cancelled) return;
        setHistory(s.messages);
        setBoundDatasetId(s.dataset_id ?? "");
        if (s.dataset_id) setDatasetId(s.dataset_id);
      })
      .catch(() => !cancelled && setHistory([]))
      .finally(() => !cancelled && setHistoryLoading(false));
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const all = [...history, ...messages];
  const liveFrom = history.length;

  // follow the answer while it streams, unless the reader scrolled up
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [all.length, messages]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (el) stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const startNew = useCallback(() => {
    stop();
    createdHere.current = null;
    setSessionId("");
    setHistory([]);
    setMessages([]);
    setDrawerOpen(false);
    composerRef.current?.focus();
  }, [setMessages, stop]);

  const select = useCallback(
    (id: string) => {
      if (id === sessionId) return;
      stop();
      createdHere.current = null;
      setMessages([]);
      setHistory([]);
      setSessionId(id);
    },
    [sessionId, setMessages, stop],
  );

  const handleSend = (text: string) => {
    stickToBottom.current = true;
    send(text);
  };

  const datasetName = options?.find((d) => d.id === datasetId)?.name;
  const empty = all.length === 0 && !historyLoading;

  return (
    <div className="flex h-dvh overflow-hidden bg-paper">
      <Sidebar
        user={user}
        activeId={sessionId || null}
        refreshKey={refreshKey}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onSelect={select}
        onNew={startNew}
        onLogout={onLogout}
      />

      <main className="flex min-w-0 flex-1 flex-col bg-sheet">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-rule px-4 sm:px-6">
          <button
            onClick={() => setDrawerOpen(true)}
            className="btn-quiet -ml-1 md:hidden"
            aria-label="Open chats"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden>
              <path d="M2 4h12M2 8h12M2 12h8" />
            </svg>
          </button>
          <DatasetPicker
            options={options}
            value={sessionId ? boundDatasetId : datasetId}
            onChange={setDatasetId}
            locked={Boolean(sessionId)}
          />
        </header>

        <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[780px] px-4 sm:px-6">
            {empty ? (
              <EmptyState
                status={
                  options === null
                    ? "loading"
                    : options.length === 0
                      ? "none"
                      : datasetName
                        ? "ready"
                        : "choose"
                }
                datasetName={datasetName}
              />
            ) : (
              <div className="py-6" aria-live="polite">
                {historyLoading && (
                  <div className="space-y-3 py-6 sm:pl-24">
                    <div className="ghost-line w-1/2" />
                    <div className="ghost-line w-5/6" />
                    <div className="ghost-line w-2/3" />
                  </div>
                )}
                {all.map((m, i) => (
                  <ChatMessage
                    key={m.id ?? i}
                    role={m.role}
                    content={m.content}
                    live={i >= liveFrom}
                    streaming={streaming && i === all.length - 1 && m.role === "assistant"}
                  />
                ))}
                {error && (
                  <div className="rise my-2 border-l-2 border-alert bg-alert-soft/60 py-2.5 pl-4 pr-3 text-sm text-alert sm:ml-24">
                    The answer stopped: {error}. Send the question again.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0 pb-4 pt-2 sm:pb-5">
          <div className="mx-auto w-full max-w-[780px] px-4 sm:px-6 sm:pl-[120px]">
            <Composer
              ref={composerRef}
              streaming={streaming}
              disabled={!sessionId && !datasetId}
              disabledReason="Choose a dataset first"
              placeholder={datasetName ? `Ask about ${datasetName}` : "Ask a question"}
              onSend={handleSend}
              onStop={stop}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

type EmptyStatus = "loading" | "none" | "choose" | "ready";

const EMPTY_HEADING: Record<EmptyStatus, string> = {
  loading: "Ask about your records.",
  none: "No dataset is ready yet.",
  choose: "Choose a dataset to start.",
  ready: "",
};

function EmptyState({ status, datasetName }: Readonly<{ status: EmptyStatus; datasetName?: string }>) {
  return (
    <div className="fade-in pb-10 pt-[14vh] sm:pl-24">
      <h1 className="max-w-[26ch] text-2xl font-semibold tracking-[-0.015em] text-ink">
        {status === "ready" ? `Ask about the records in ${datasetName}.` : EMPTY_HEADING[status]}
      </h1>
      <p className="mt-4 max-w-[60ch] text-base text-ink-2">
        {status === "none" ? (
          <>An admin must create a dataset and upload its key. Then it appears in the list above.</>
        ) : (
          <>
            Names, numbers and other personal data in your question become tokens before the model
            reads it. The answer shows the values that your role allows. Every other value stays
            hidden, like this: <Redaction label="PERSON" hexid="3f9a1c2e70b4" />. Point at a bar to
            see its token.
          </>
        )}
      </p>
    </div>
  );
}
