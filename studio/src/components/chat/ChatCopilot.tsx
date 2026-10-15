import { useEffect, useRef, useState } from "react";

import { useStudio } from "../../state/StudioContext";

const QUICK_PROMPTS: { label: string; prompt: string }[] = [
  {
    label: "🎯 Define Job",
    prompt: "Help me define a new Job-to-be-Done for developer platforms.",
  },
  { label: "⚡ Simulate Bet", prompt: "Simulate the impact of an Auto-Sync Agent on outcome O-1." },
  { label: "📖 Guidelines", prompt: "Give me the ODI Stage-by-Stage guidelines." },
];

export function ChatCopilot() {
  const { messages, streaming, thinkingPhase, toolActivity, sendMessage } = useStudio();
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages, toolActivity, streaming]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft;
    setDraft("");
    await sendMessage(text);
  }

  return (
    <section className="chat-copilot">
      <h2 className="section-title">💬 Agentic Studio Copilot</h2>
      <p className="caption">
        Direct thought interaction. Speak your intent; the agent navigates the ODI methodology.
      </p>

      <p style={{ fontSize: "0.82rem", margin: "0 0 6px" }}>
        <b>Suggested Intents:</b>
      </p>
      <div className="chat-quick-pills">
        {QUICK_PROMPTS.map((quick) => (
          <button
            key={quick.label}
            type="button"
            className="studio-button"
            disabled={streaming}
            onClick={() => void sendMessage(quick.prompt)}
          >
            {quick.label}
          </button>
        ))}
      </div>

      <div className="chat-log" ref={logRef} role="log" aria-label="Chat with the studio copilot">
        {messages.map((message, index) => (
          <div className={`chat-bubble chat-bubble--${message.role}`} key={index}>
            {message.content}
          </div>
        ))}
        {toolActivity.map((tool, index) => (
          <div className="chat-bubble chat-bubble--tool" key={`tool-${index}`}>
            🛠️ {tool.name} · {tool.status}
            {tool.preview ? ` — ${tool.preview}` : ""}
          </div>
        ))}
        {streaming && (
          <div className="thinking">
            {thinkingPhase ? `Synthesizing human intent & outcomes (${thinkingPhase})…` : "Thinking…"}
          </div>
        )}
      </div>

      <form className="chat-input-row" onSubmit={submit}>
        <textarea
          ref={inputRef}
          className="studio-input"
          rows={2}
          aria-label="State your product intent or question"
          placeholder="State your product intent or question..."
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submit(event);
            }
          }}
        />
        <button type="submit" className="studio-button" disabled={streaming || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}
