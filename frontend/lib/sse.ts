interface StreamEventPayload {
  delta?: string;
  error?: string;
}

export interface StreamSseResult {
  accumulated: string;
  receivedDone: boolean;
}

export async function streamSseDeltas(
  response: Response,
  onDelta: (accumulated: string, delta: string) => void
): Promise<StreamSseResult> {
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  if (!response.body) {
    throw new Error("Response body is null");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let accumulated = "";
  let receivedDone = false;

  const processSseLine = (line: string): StreamSseResult | null => {
    if (!line.startsWith("data: ")) return null;
    const payload = line.slice(6).trim();

    if (payload === "[DONE]") {
      receivedDone = true;
      return { accumulated, receivedDone };
    }

    let parsed: StreamEventPayload;
    try {
      parsed = JSON.parse(payload) as StreamEventPayload;
    } catch {
      // Ignore malformed partial chunks.
      return null;
    }

    if (parsed.error) {
      throw new Error(String(parsed.error));
    }
    if (typeof parsed.delta === "string" && parsed.delta.length > 0) {
      accumulated += parsed.delta;
      onDelta(accumulated, parsed.delta);
    }
    return null;
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const maybeDone = processSseLine(line);
      if (maybeDone) {
        return maybeDone;
      }
    }
  }

  // Flush decoder + remaining buffered line(s) if stream ended without trailing newline.
  buffer += decoder.decode();
  if (buffer) {
    for (const line of buffer.split("\n")) {
      const maybeDone = processSseLine(line);
      if (maybeDone) {
        return maybeDone;
      }
    }
  }

  return { accumulated, receivedDone };
}
