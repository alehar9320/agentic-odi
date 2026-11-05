import { useEffect, useId, useMemo, useRef, useState } from "react";

import { buildDecisionBrief } from "../../lib/brief";
import { briefFilename, briefToMarkdown, downloadMarkdown } from "../../lib/export";
import { useStudio } from "../../state/StudioContext";
import { Markdown } from "../chat/Markdown";

/**
 * The decision brief, previewed as the document it exports to.
 *
 * There is deliberately one formatting path: the preview renders the same
 * Markdown string the download writes, so what a person approves is what lands
 * in the file. The optional objection is the only editing the sheet allows — it
 * adds a source the studio could not know, it does not rewrite the ones it has.
 *
 * Printing is the browser's: the body carries `brief-printing` while the print
 * dialog is open, and `print.css` keeps only the document on the page.
 */
export function BriefLens() {
  const { canvas, brief, theses, presets, canvasCached } = useStudio();
  const [objection, setObjection] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const objectionId = useId();
  const downloadRef = useRef<HTMLButtonElement>(null);

  const markdown = useMemo(
    () =>
      briefToMarkdown(
        buildDecisionBrief({
          canvas,
          brief,
          theses,
          presets,
          canvasCached,
          authorObjection: objection,
        }),
      ),
    [canvas, brief, theses, presets, canvasCached, objection],
  );

  // The primary action is the reason the sheet is open, so it starts there.
  useEffect(() => {
    downloadRef.current?.focus();
  }, []);

  useEffect(() => {
    function afterPrint() {
      document.body.classList.remove("brief-printing");
    }
    window.addEventListener("afterprint", afterPrint);
    return () => {
      window.removeEventListener("afterprint", afterPrint);
      afterPrint();
    };
  }, []);

  function download() {
    downloadMarkdown(markdown, briefFilename());
    setNotice(`Saved as ${briefFilename()}.`);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(markdown);
      setNotice("Brief copied.");
    } catch {
      // The document is on screen either way; a clipboard that refuses is not
      // worth a dialog, and Download is the fallback.
      setNotice("Could not copy the brief. Download .md instead.");
    }
  }

  function print() {
    document.body.classList.add("brief-printing");
    window.print();
  }

  return (
    <div className="brief">
      <div className="brief__bar">
        <button
          type="button"
          ref={downloadRef}
          className="button"
          onClick={download}
        >
          Download .md
        </button>
        <button type="button" className="button button--ghost" onClick={print}>
          Print / PDF
        </button>
        <button type="button" className="button button--ghost" onClick={() => void copy()}>
          Copy
        </button>
      </div>

      {notice && (
        <p className="brief__notice" role="status">
          {notice}
        </p>
      )}

      <div className="brief__objection field">
        <label htmlFor={objectionId}>What argues against this?</label>
        <textarea
          id={objectionId}
          value={objection}
          rows={2}
          placeholder="One objection a reviewer will raise."
          onChange={(event) => setObjection(event.target.value)}
        />
        <p className="field__hint">
          Optional. It prints under Dissent, labelled author-supplied.
        </p>
      </div>

      <article className="brief__doc" aria-label="Decision brief">
        <Markdown source={markdown} />
      </article>
    </div>
  );
}
