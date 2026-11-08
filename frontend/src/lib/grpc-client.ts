/**
 * gRPC-Web chat client — manual fetch-based implementation.
 *
 * Communicates with the Envoy proxy (port 8080 in Docker, or via Vite proxy
 * on /chat.ChatService) using the gRPC-Web wire format over standard fetch.
 *
 * This works without running protoc. If you run `npm run gen:proto` you can
 * swap the internals here for the generated TypeScript stubs.
 */

// ── Minimal manual proto encoding (matches chat.proto field numbers) ───────────

// Protobuf varint (tags, lengths, bools). A length used to be written as ONE byte, so any field of
// 128+ UTF-8 bytes (a long question; 64+ Cyrillic chars) produced a broken request.
function encodeVarint(n: number): number[] {
  const out: number[] = [];
  while (n > 0x7f) {
    out.push((n & 0x7f) | 0x80);
    n = Math.floor(n / 128);
  }
  out.push(n);
  return out;
}

function readVarint(bytes: Uint8Array, pos: number): [number, number] {
  let result = 0;
  let mul = 1;
  while (pos < bytes.length) {
    const b = bytes[pos++];
    result += (b & 0x7f) * mul;
    if (!(b & 0x80)) break;
    mul *= 128;
  }
  return [result, pos];
}

function encodeString(fieldNumber: number, value: string): Uint8Array {
  if (!value) return new Uint8Array(0);
  const bytes = new TextEncoder().encode(value);
  const head = [...encodeVarint((fieldNumber << 3) | 2), ...encodeVarint(bytes.length)];
  const out = new Uint8Array(head.length + bytes.length);
  out.set(head, 0);
  out.set(bytes, head.length);
  return out;
}

function encodeChatRequest(params: {
  chat_session_id: string;
  message: string;
  dataset_id: string;
  auth_token: string;
}): Uint8Array {
  const parts = [
    encodeString(1, params.chat_session_id),
    encodeString(2, params.message),
    encodeString(3, params.dataset_id),
    encodeString(4, params.auth_token),
  ];
  const total = parts.reduce((s, p) => s + p.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}

function decodeChatChunk(bytes: Uint8Array): { content: string; done: boolean; error: string } {
  let pos = 0;
  let content = "";
  let done = false;
  let error = "";
  const dec = new TextDecoder();

  while (pos < bytes.length) {
    let tag: number;
    [tag, pos] = readVarint(bytes, pos);
    const fieldNumber = tag >> 3;
    const wireType = tag & 0x7;

    if (wireType === 2) {
      let len: number;
      [len, pos] = readVarint(bytes, pos);
      const slice = bytes.slice(pos, pos + len);
      pos += len;
      if (fieldNumber === 1) content = dec.decode(slice);
      if (fieldNumber === 3) error = dec.decode(slice);
    } else if (wireType === 0) {
      let val: number;
      [val, pos] = readVarint(bytes, pos);
      if (fieldNumber === 2) done = Boolean(val);
    } else if (wireType === 1) {
      pos += 8;
    } else if (wireType === 5) {
      pos += 4;
    } else {
      break; // unknown wire type: stop instead of looping on garbage
    }
  }
  return { content, done, error };
}

// ── gRPC-Web stream using fetch (works without protoc-gen stubs) ───────────────

export interface ChatStreamParams {
  chat_session_id: string;
  message: string;
  dataset_id: string;
  onChunk: (content: string) => void;
  onDone: (session_id?: string) => void;
  onError: (err: string) => void;
}

export function streamChat(params: ChatStreamParams): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      // Encode request as gRPC-Web frame: 5-byte header + body
      const body = encodeChatRequest({
        chat_session_id: params.chat_session_id,
        message: params.message,
        dataset_id: params.dataset_id,
        auth_token: "", // JWT sent via cookie; field kept for gRPC metadata fallback
      });

      const frame = new Uint8Array(5 + body.length);
      frame[0] = 0; // no compression
      const view = new DataView(frame.buffer);
      view.setUint32(1, body.length, false); // big-endian length
      frame.set(body, 5);

      // Retrieve CSRF token for the grpc endpoint (informational; gRPC uses metadata)
      const csrfMatch = document.cookie.match(/csrf_token=([^;]+)/);
      const csrf = csrfMatch ? csrfMatch[1] : "";

      const res = await fetch("/chat.ChatService/StreamChat", {
        method: "POST",
        headers: {
          "Content-Type": "application/grpc-web+proto",
          "X-Grpc-Web": "1",
          "X-CSRF-Token": csrf,
        },
        credentials: "include",
        body: frame,
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        params.onError(`HTTP ${res.status}`);
        return;
      }

      const reader = res.body.getReader();
      let buffer = new Uint8Array(0);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Append to buffer
        const next = new Uint8Array(buffer.length + value.length);
        next.set(buffer);
        next.set(value, buffer.length);
        buffer = next;

        // Parse as many complete gRPC-Web frames as possible
        while (buffer.length >= 5) {
          const frameLen = new DataView(buffer.buffer).getUint32(1, false);
          if (buffer.length < 5 + frameLen) break;

          const frameType = buffer[0];
          const frameBody = buffer.slice(5, 5 + frameLen);
          buffer = buffer.slice(5 + frameLen);

          if (frameType === 0x80) {
            // Trailers frame — stream complete
            params.onDone();
            return;
          }

          const chunk = decodeChatChunk(frameBody);
          if (chunk.error) {
            params.onError(chunk.error);
            return;
          }
          if (chunk.content) {
            params.onChunk(chunk.content);
          }
          if (chunk.done) {
            params.onDone();
            return;
          }
        }
      }
      params.onDone();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        params.onError(String(err));
      }
    }
  })();

  return () => controller.abort();
}
