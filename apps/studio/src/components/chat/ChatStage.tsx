import { useEffect, useRef, useState } from "react";

import { useStudio } from "../../state/StudioContext";
import { Composer } from "./Composer";
import { Conversation } from "./Conversation";
import { Hero } from "./Hero";

/**
 * The main stage: a conversation first, with the classic UI one drawer-click
 * away. Everything here is centred on one readable column, the way modern chat
 * surfaces behave.
 */
export function ChatStage() {
  const { messages, streaming, sendMessage, stopStreaming } = useStudio();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const pinned = useRef(true);
  const refocus = useRef(false);

  const empty = messages.length === 0;

  function submit(text?: string) {
    const value = (text ?? draft).trim();
    if (!value || streaming) {
      return;
    }
    if (text === undefined) {
      setDraft("");
    }
    pinned.current = true;
    refocus.current = true;
    void sendMessage(value);
  }

  // Keep the transcript pinned to the newest token unless the reader scrolled up.
  useEffect(() => {
    if (!pinned.current) {
      return;
    }
    const element = scrollRef.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, [messages, streaming]);

  // The composer moves from the hero into the dock when the conversation starts.
  useEffect(() => {
    if (!empty && refocus.current) {
      refocus.current = false;
      inputRef.current?.focus();
    }
  }, [empty]);

  if (empty) {
    return (
      <section className="chat chat--empty" aria-label="Studio conversation">
        <div className="chat__welcome">
          <div className="chat__welcome-inner">
            <Hero onSubmit={submit} />
            <Composer
              value={draft}
              onChange={setDraft}
              onSubmit={submit}
              streaming={streaming}
              onStop={stopStreaming}
              inputRef={inputRef}
              autoFocus
            />
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="chat" aria-label="Studio conversation">
      <div
        ref={scrollRef}
        className="chat__scroll"
        onScroll={(event) => {
          const element = event.currentTarget;
          pinned.current =
            element.scrollHeight - element.scrollTop - element.clientHeight < 96;
        }}
      >
        <div className="chat__thread">
          <Conversation />
        </div>
      </div>
      <div className="chat__dock">
        <Composer
          value={draft}
          onChange={setDraft}
          onSubmit={submit}
          streaming={streaming}
          onStop={stopStreaming}
          inputRef={inputRef}
        />
      </div>
    </section>
  );
}
