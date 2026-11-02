import { canvasStatus } from "../../lib/canvasProvenance";
import { downloadFile } from "../../lib/export";
import { buildRecords, toCsv } from "../../lib/records";
import { useStudio } from "../../state/StudioContext";
import { RecordsTable } from "./RecordsTable";

/**
 * The store, as the canvas already holds it. No fetch: opening this lens costs
 * nothing, and the chip and the table are counted from the same rows.
 */
export function RecordsPanel() {
  const { canvas } = useStudio();
  const rows = buildRecords(canvas);
  const status = canvasStatus(canvas);

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
      <RecordsTable rows={rows} />
    </div>
  );
}
