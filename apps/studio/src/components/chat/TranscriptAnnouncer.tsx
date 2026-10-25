import { useEffect, useRef, useState } from "react";

export interface Announcement {
  /** Changes once per settled turn, so the same wording is still spoken. */
  token: number;
  text: string;
}

/**
 * A quiet mouth for the transcript.
 *
 * The visible conversation is not a live region: announcing streamed tokens
 * produces a stutter, and re-rendered Markdown can be read twice. Instead the
 * shell hands this component one settled turn at a time.
 *
 * Two alternating polite regions are deliberate. Moving the text from one slot
 * to the other is a real change in the DOM even when the wording repeats, and
 * clearing the inactive slot keeps the previous reply from being read again.
 */
export function TranscriptAnnouncer({ announcement }: { announcement: Announcement | null }) {
  const [slot, setSlot] = useState(0);
  const [text, setText] = useState("");
  const lastToken = useRef<number | null>(null);

  useEffect(() => {
    if (!announcement || lastToken.current === announcement.token) {
      return;
    }
    lastToken.current = announcement.token;
    setText(announcement.text);
    setSlot((current) => (current === 0 ? 1 : 0));
  }, [announcement]);

  return (
    <>
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {slot === 0 ? text : ""}
      </div>
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {slot === 1 ? text : ""}
      </div>
    </>
  );
}
