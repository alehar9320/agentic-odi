export interface RawSseEvent {
  event: string;
  data: Record<string, unknown>;
}

export interface SseParser {
  push(chunk: string): RawSseEvent[];
}

export function createSseParser(): SseParser {
  let buffer = "";

  return {
    push(chunk: string): RawSseEvent[] {
      buffer += chunk;
      const events: RawSseEvent[] = [];

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        let event = "message";
        let data = "";
        for (const line of block.split("\n")) {
          if (line.startsWith("event: ")) {
            event = line.slice("event: ".length);
          } else if (line.startsWith("data: ")) {
            data = line.slice("data: ".length);
          }
        }

        if (data) {
          try {
            events.push({ event, data: JSON.parse(data) as Record<string, unknown> });
          } catch {
            events.push({ event: "error", data: { message: data } });
          }
        }

        boundary = buffer.indexOf("\n\n");
      }

      return events;
    },
  };
}
