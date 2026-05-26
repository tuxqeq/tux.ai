import { useCallback, useRef, useState } from "react";
import { streamChat } from "@/lib/grpc-client";
import type { Message } from "@/lib/api";

function uuid(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export interface UseChatOptions {
  sessionId: string;
  datasetId: string;
  onSessionCreated?: (id: string) => void;
}

export function useChat({ sessionId, datasetId, onSessionCreated }: UseChatOptions) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stopRef = useRef<(() => void) | null>(null);

  const send = useCallback(
    (text: string) => {
      if (!text.trim() || streaming) return;

      const userMsg: Message = {
        id: uuid(),
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setStreaming(true);
      setError(null);

      // Placeholder for assistant response — will be updated as chunks arrive
      const assistantId = uuid();
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "", created_at: new Date().toISOString() },
      ]);

      stopRef.current = streamChat({
        chat_session_id: sessionId,
        message: text,
        dataset_id: datasetId,

        onChunk(chunk) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + chunk } : m
            )
          );
        },

        onDone(newSessionId) {
          setStreaming(false);
          if (newSessionId && onSessionCreated) {
            onSessionCreated(newSessionId);
          }
        },

        onError(err) {
          setStreaming(false);
          setError(err);
          setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        },
      });
    },
    [sessionId, datasetId, streaming, onSessionCreated]
  );

  const stop = useCallback(() => {
    stopRef.current?.();
    setStreaming(false);
  }, []);

  const reset = useCallback(() => {
    stopRef.current?.();
    setMessages([]);
    setStreaming(false);
    setError(null);
  }, []);

  return { messages, setMessages, streaming, error, send, stop, reset };
}
