import { useRef, useState } from "react";

import { canvasStatus } from "../../lib/canvasProvenance";
import { downloadFile } from "../../lib/export";
import { buildRecords, toCsv } from "../../lib/records";
import { useStudio } from "../../state/StudioContext";
import { RecordDetail } from "./RecordDetail";
import { RecordsTable } from "./RecordsTable";

/**
 * The store, as the canvas already holds it. No fetch: opening this lens costs
 * nothing, and the chip and the table are counted from the same rows.
 *
 * Selection and filtering live here rather than in the table, because opening a
 * record and narrowing to a parent are the same act seen from two places: the row
 * you pressed and the record it belongs to.
 */
export function RecordsPanel() {
  const { canvas } = useStudio();
  const rows = buildRecords(canvas);
  const status = canvasStatus(canvas);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [filter, setFilter] = useState<string | null>(null);
  const rowButtons = useRef(new Map<string, HTMLButtonElement>());

  const visible = filter
    ? rows.filter((row) => row.id === filter || row.parentId === filter)
    : rows;
  // Looked up in every row, not the filtered ones: narrowing to a parent must not
  // close the record that asked for it.
  const selected = rows.find((row) => row.rowKey === selectedKey) ?? null;

  function registerButton(rowKey: string, button: HTMLButtonElement | null) {
    if (button) {
      rowButtons.current.set(rowKey, button);
    } else {
      rowButtons.current.delete(rowKey);
    }
  }

  function close() {
    const origin = selectedKey ? rowButtons.current.get(selectedKey) : undefined;
    setSelectedKey(null);
    origin?.focus();
  }

  function exportCsv() {
    downloadFile(toCsv(rows), "records.csv", "text/csv;charset=utf-8");
  }

  return (
    <div className="records">
      {status ? (
        <p className="records__provenance" title={status.detail}>
          {status.label}
        </p>
      ) : null}
      <button
        type="button"
        className="quiet-action records__export"
        disabled={rows.length === 0}
        title="Download every record the lens shows, as CSV"
        onClick={exportCsv}
      >
        Export CSV
      </button>
      {filter ? (
        <p className="records__filter">
          Filtered: <code className="records__id">{filter}</code>
          <button
            type="button"
            className="records__filter-clear"
            aria-label={`Clear filter ${filter}`}
            onClick={() => setFilter(null)}
          >
            ✕
          </button>
        </p>
      ) : null}
      <RecordsTable
        rows={visible}
        selectedKey={selectedKey}
        onSelect={setSelectedKey}
        registerButton={registerButton}
      />
      {selected ? (
        <RecordDetail row={selected} rows={rows} onFilter={setFilter} onClose={close} />
      ) : null}
    </div>
  );
}
