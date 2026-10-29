import { useEffect, useRef, useState } from "react";

import { useStudio } from "../../state/StudioContext";

const QUICK_PROMPTS_LEVEL0: { label: string; prompt: string }[] = [
  {
    label: "🎯 Define Job",
    prompt: "Help me define a new Job-to-be-Done for developer platforms.",
  },
  { label: "📖 Guidelines", prompt: "Give me the ODI Stage-by-Stage guidelines." },
];

const QUICK_PROMPTS_LEVEL1: { label: string; prompt: string }[] = [
  {
    label: "🎯 Define Job",
    prompt: "Help me define a new Job-to-be-Done for developer platforms.",
  },
  { label: "⚡ Simulate Bet", prompt: "Simulate the impact of an Auto-Sync Agent on outcome O-1." },
  { label: "📖 Guidelines", prompt: "Give me the ODI Stage-by-Stage guidelines." },
];

const QUICK_PROMPTS_LEVEL2: { label: string; prompt: string }[] = [
  {
    label: "🎯 Define Job",
    prompt: "Help me define a new Job-to-be-Done for developer platforms.",
  },
  { label: "⚡ Simulate Bet", prompt: "Simulate the impact of an Auto-Sync Agent on outcome O-1." },
  { label: "📖 Guidelines", prompt: "Give me the ODI Stage-by-Stage guidelines." },
];

export function ChatCopilot() {
  const {
    messages,
    streaming,
    thinkingPhase,
    toolActivity,
    sendMessage,
    engagementLevel,
    setEngagementLevel,
  } = useStudio();

  const [draft, setDraft] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setMobileOpen(true);
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (logRef.current) {
      if (typeof logRef.current.scrollTo === "function") {
        logRef.current.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
      } else {
        logRef.current.scrollTop = logRef.current.scrollHeight;
      }
    }
  }, [messages, toolActivity, streaming, engagementLevel]);

  useEffect(() => {
    if (messages.length === 1 && engagementLevel === 0) {
      setEngagementLevel(1);
    }
  }, [messages.length, engagementLevel, setEngagementLevel]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!draft.trim() || streaming) return;
    const text = draft;
    setDraft("");
    await sendMessage(text);
  }

  const quickPrompts = engagementLevel >= 2
    ? QUICK_PROMPTS_LEVEL2
    : engagementLevel >= 1
      ? QUICK_PROMPTS_LEVEL1
      : QUICK_PROMPTS_LEVEL0;

  return (
    <>
      {/* Mobile Floating Action Button */}
      <button
        type="button"
        className="mobile-chat-fab"
        onClick={() => {
          setMobileOpen(true);
          setTimeout(() => inputRef.current?.focus(), 100);
        }}
        aria-label="Open AI Copilot Chat"
      >
        💬 AI Copilot
        {streaming && <span style={{ fontSize: "0.7rem", opacity: 0.9 }}> (thinking…)</span>}
      </button>

      {/* Backdrop for Mobile Bottom Sheet */}
      <div
        className={`chat-copilot__backdrop ${mobileOpen ? "chat-copilot__backdrop--open" : ""}`}
        onClick={() => setMobileOpen(false)}
        aria-hidden="true"
      />

      <section className={`chat-copilot ${mobileOpen ? "chat-copilot--open" : ""}`}>
        <div className="chat-copilot__header">
          <div>
            <h2 className="section-title" style={{ margin: 0 }}>💬 Agentic Studio Copilot</h2>
            <p className="caption" style={{ margin: "2px 0 0" }}>
              Speak intent; AI navigates ODI methodology.
            </p>
          </div>
          <button
            type="button"
            className="studio-button studio-button--ghost mobile-only"
            onClick={() => setMobileOpen(false)}
            aria-label="Close drawer"
            style={{ padding: "4px 10px", minHeight: "36px" }}
          >
            ✕ Close
          </button>
        </div>

        <div className="chat-quick-pills" style={{ marginTop: 8 }}>
          {quickPrompts.map((quick) => (
            <button
              key={quick.label}
              type="button"
              className="studio-button chat-quick-pill"
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
              🛠️ {tool.name} - {tool.status}
              {tool.preview ? ` — ${tool.preview}` : ""}
            </div>
          ))}
          {streaming && (
            <div className="thinking" role="status">
              {thinkingPhase ? `Synthesizing intent (${thinkingPhase})…` : "Thinking…"}
            </div>
          )}
        </div>

        <form className="chat-input-row" onSubmit={submit}>
          <textarea
            ref={inputRef}
            className="studio-input"
            rows={2}
            aria-label="State your product intent or question"
            placeholder="State your intent or ask a question..."
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
    </>
  );
}
