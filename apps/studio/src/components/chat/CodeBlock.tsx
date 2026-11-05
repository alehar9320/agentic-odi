/**
 * A fenced block you can take with you.
 *
 * The control is in the tab order from the start — it is revealed on hover and
 * on focus-within, never removed — so a keyboard reader meets it in the order
 * the block appears and a pointer reader only sees it over the block it copies.
 */

import { copyText, useCopyFeedback } from "../../lib/copyFeedback";
import { CheckIcon, CopyIcon } from "../icons";

export function CodeBlock({ code, preClassName }: { code: string; preClassName?: string }) {
  const { copied, confirm } = useCopyFeedback();

  return (
    <div className="code-block">
      <pre className={preClassName}>
        <code>{code}</code>
      </pre>
      <button
        type="button"
        className="code-block__copy"
        aria-label="Copy code"
        onClick={() => {
          void copyText(code).then((ok) => {
            if (ok) {
              confirm();
            }
          });
        }}
      >
        {copied ? <CheckIcon size={12} /> : <CopyIcon size={12} />}
        <span>{copied ? "Copied" : "Copy"}</span>
      </button>
    </div>
  );
}
