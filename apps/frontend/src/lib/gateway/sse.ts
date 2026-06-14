// The SSE seam — a self-reconnecting reader of the gateway's per-session event stream
// (GET /sessions/{id}/events). It parses the text/event-stream framing the gateway writes
// (apps/agentgateway/internal/gateway/events_handler.go): each frame is `event: <kind>` /
// `id: <seq>` / `data: <json>` terminated by a blank line. We read it over fetch +
// ReadableStream (not the browser EventSource) for three reasons: (1) we observe the raw `id:`
// seq so reconnect resumes gap-free via Last-Event-ID, (2) we can set Last-Event-ID explicitly
// on a manual reconnect, and (3) the E2E drives the SAME real parser, no mock.
//
// Gap-free resume contract (REQ-0023): the gateway replays the durable transcript [lastSeq+1 ..
// head] then attaches to the live tail. We track the highest seq we have delivered and send it
// as Last-Event-ID on every reconnect, so a dropped connection resumes with no gap and no
// duplicate. The reader de-duplicates defensively (an event whose seq <= the last delivered seq
// is dropped) so a replay overlap can never surface a duplicate to the UI.

import type { EventView } from './types';
import { TERMINAL_KINDS } from './types';

/** A parsed SSE frame: the event kind token, the monotonic seq, and the decoded data payload. */
interface Frame {
  kind: string;
  seq: number;
  data: EventView;
}

/** SubscribeOptions wires the reader's callbacks + lifecycle into the caller (the session store). */
export interface SubscribeOptions {
  /** Called once per delivered (de-duplicated, in-order) event. */
  onEvent: (event: EventView) => void;
  /** Called whenever the connection opens/closes/retries, so the UI can show the live status. */
  onStatus?: (status: SseStatus) => void;
  /** Resume cursor: the highest seq already delivered. The first connect replays [from+1 .. head]
   *  then tails live; 0 (default) replays the whole session from the start. */
  fromSeq?: number;
  /** Reconnect backoff in ms (the gap a dropped stream waits before retrying). Default 500ms. */
  retryMs?: number;
}

/** The connection status the UI surfaces (a live dot / reconnect notice). */
export type SseStatus = 'connecting' | 'open' | 'reconnecting' | 'closed' | 'ended';

/** A handle to an active subscription. close() stops the reader and prevents further reconnects;
 *  it is idempotent and leak-free (it aborts the in-flight fetch). */
export interface Subscription {
  close(): void;
  /** The highest seq delivered so far (the resume cursor a manual reconnect would use). */
  lastSeq(): number;
}

/** subscribeEvents opens the per-session SSE stream and pumps de-duplicated, in-order events to
 *  onEvent until the terminal event, an explicit close, or (transiently) a drop+reconnect. It is
 *  the ONLY place the raw event-stream framing is parsed (one concept, one home). */
export function subscribeEvents(eventsUrl: string, options: SubscribeOptions): Subscription {
  const retryMs = options.retryMs ?? 500;
  let lastSeq = options.fromSeq ?? 0;
  let ended = false; // a terminal event arrived or close() was called — never reconnect.
  let controller: AbortController | null = null;
  let attempts = 0;

  const setStatus = (status: SseStatus) => options.onStatus?.(status);

  const deliver = (frame: Frame) => {
    // De-duplicate against the replay overlap: a reconnect replays [lastSeq+1 .. head], so any
    // frame at or below the highest delivered seq is a duplicate we must drop (gap-free + no dup).
    if (frame.seq <= lastSeq) return;
    lastSeq = frame.seq;
    options.onEvent(frame.data);
    if (TERMINAL_KINDS.has(frame.data.kind)) {
      ended = true;
    }
  };

  const connect = async () => {
    if (ended) return;
    attempts += 1;
    setStatus(attempts === 1 ? 'connecting' : 'reconnecting');
    controller = new AbortController();

    let response: Response;
    try {
      response = await fetch(eventsUrl, {
        method: 'GET',
        // Last-Event-ID is the SSE reconnect standard the gateway honors as the replay cursor.
        headers: { accept: 'text/event-stream', 'last-event-id': String(lastSeq) },
        signal: controller.signal,
      });
    } catch {
      return scheduleReconnect();
    }

    if (!response.ok || !response.body) {
      return scheduleReconnect();
    }

    setStatus('open');
    attempts = 0;

    try {
      await pump(response.body, deliver);
    } catch {
      // A read fault (network drop) falls through to reconnect below.
    }

    if (ended) {
      setStatus('ended');
      return;
    }
    // The stream ended without a terminal event (the server flushed and closed, or the
    // connection dropped): resume from the last delivered seq.
    scheduleReconnect();
  };

  const scheduleReconnect = () => {
    if (ended) return;
    setStatus('reconnecting');
    setTimeout(() => {
      if (!ended) void connect();
    }, retryMs);
  };

  void connect();

  return {
    close() {
      ended = true;
      setStatus('closed');
      controller?.abort();
    },
    lastSeq() {
      return lastSeq;
    },
  };
}

/** pump reads the response body, splits it into SSE frames on the blank-line boundary, parses
 *  each, and delivers it. It returns when the stream closes (EOF) — the caller decides whether
 *  that is a clean end (terminal event seen) or a drop to reconnect. */
async function pump(body: ReadableStream<Uint8Array>, deliver: (frame: Frame) => void) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Frames are separated by a blank line. Normalize CRLF, then split on the double newline.
      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const frame = parseFrame(raw);
        if (frame) deliver(frame);
        boundary = buffer.indexOf('\n\n');
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/** parseFrame turns one raw SSE frame block into a Frame, or null for a comment/heartbeat frame
 *  (`: ...`) or an unparseable data payload. It reads the `event:`, `id:`, and `data:` lines per
 *  the event-stream grammar; a multi-line data field is joined with newlines (the spec). */
function parseFrame(raw: string): Frame | null {
  let kind = 'message';
  let seq = NaN;
  const dataLines: string[] = [];

  for (const line of raw.split('\n')) {
    const normalized = line.replace(/\r$/, '');
    if (normalized === '' || normalized.startsWith(':')) continue; // blank or comment/heartbeat
    const colon = normalized.indexOf(':');
    const field = colon === -1 ? normalized : normalized.slice(0, colon);
    // A single leading space after the colon is stripped per the SSE spec.
    let val = colon === -1 ? '' : normalized.slice(colon + 1);
    if (val.startsWith(' ')) val = val.slice(1);

    if (field === 'event') kind = val;
    else if (field === 'id') seq = Number(val);
    else if (field === 'data') dataLines.push(val);
  }

  if (dataLines.length === 0) return null;
  let data: EventView;
  try {
    data = JSON.parse(dataLines.join('\n')) as EventView;
  } catch {
    return null;
  }
  // Prefer the seq from the data payload (authoritative); fall back to the id: line.
  const resolvedSeq = Number.isFinite(data.seq) ? data.seq : seq;
  if (!Number.isFinite(resolvedSeq)) return null;
  return { kind, seq: resolvedSeq, data };
}
