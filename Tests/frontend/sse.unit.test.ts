import { describe, expect, it, vi } from "vitest";

import { streamSseDeltas } from "../../frontend/lib/sse";

function buildSseResponse(chunks: string[], init?: ResponseInit): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    status: 200,
    statusText: "OK",
    headers: { "Content-Type": "text/event-stream" },
    ...init,
  });
}

describe("streamSseDeltas", () => {
  it("accumulates delta chunks and stops on [DONE]", async () => {
    const response = buildSseResponse([
      "data: {\"delta\":\"Hel",
      "lo\"}\n",
      "data: {\"delta\":\" world\"}\n",
      "data: [DONE]\n",
    ]);
    const onDelta = vi.fn();

    const result = await streamSseDeltas(response, onDelta);

    expect(result).toEqual({ accumulated: "Hello world", receivedDone: true });
    expect(onDelta).toHaveBeenCalledTimes(2);
    expect(onDelta).toHaveBeenNthCalledWith(1, "Hello", "Hello");
    expect(onDelta).toHaveBeenNthCalledWith(2, "Hello world", " world");
  });

  it("ignores malformed payloads but continues processing valid events", async () => {
    const response = buildSseResponse([
      "data: {\"delta\":\"Hi\"}\n",
      "data: this-is-not-json\n",
      "data: {\"delta\":\" there\"}\n",
      "data: [DONE]\n",
    ]);

    const result = await streamSseDeltas(response, () => undefined);

    expect(result).toEqual({ accumulated: "Hi there", receivedDone: true });
  });

  it("throws when backend sends an error event", async () => {
    const response = buildSseResponse([
      "data: {\"delta\":\"Partial\"}\n",
      "data: {\"error\":\"tool failure\"}\n",
    ]);

    await expect(streamSseDeltas(response, () => undefined)).rejects.toThrow("tool failure");
  });

  it("returns partial content when stream ends without [DONE]", async () => {
    const response = buildSseResponse(["data: {\"delta\":\"partial\"}\n"]);

    const result = await streamSseDeltas(response, () => undefined);

    expect(result).toEqual({ accumulated: "partial", receivedDone: false });
  });

  it("preserves final event when EOF arrives without trailing newline", async () => {
    const response = buildSseResponse(["data: {\"delta\":\"partial\"}"]);

    const result = await streamSseDeltas(response, () => undefined);

    expect(result).toEqual({ accumulated: "partial", receivedDone: false });
  });

  it("handles multiple data events packed in one chunk", async () => {
    const response = buildSseResponse([
      "data: {\"delta\":\"a\"}\ndata: {\"delta\":\"b\"}\ndata: [DONE]\n",
    ]);

    const result = await streamSseDeltas(response, () => undefined);

    expect(result).toEqual({ accumulated: "ab", receivedDone: true });
  });

  it("ignores non-data SSE lines while parsing data lines", async () => {
    const response = buildSseResponse([
      ": keep-alive\nid: 1\nevent: message\ndata: {\"delta\":\"ok\"}\ndata: [DONE]\n",
    ]);

    const result = await streamSseDeltas(response, () => undefined);

    expect(result).toEqual({ accumulated: "ok", receivedDone: true });
  });

  it("throws for non-2xx HTTP responses", async () => {
    const response = buildSseResponse([], { status: 500, statusText: "Internal Server Error" });

    await expect(streamSseDeltas(response, () => undefined)).rejects.toThrow(
      "HTTP 500: Internal Server Error"
    );
  });
});
