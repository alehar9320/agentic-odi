import { MAX_ROWS, RECORD_SECTIONS, type RecordRow } from "../../lib/records";

interface RecordsTableProps {
  rows: RecordRow[];
  /** The row key that is open, not an id: a record without an id can still be open. */
  selectedKey: string | null;
  onSelect: (rowKey: string) => void;
  /** So closing a record can hand focus back to the row that opened it. */
  registerButton: (rowKey: string, button: HTMLButtonElement | null) => void;
}

/**
 * One table per kind, because every kind has its own real columns. A single
 * mixed table would invent a column model the store does not have.
 *
 * A row is a button rather than a clickable region, so opening a record is a thing
 * a keyboard and a screen reader can do: the first cell names it, and
 * `aria-expanded` says whether it is already open.
 */
export function RecordsTable({
  rows,
  selectedKey,
  onSelect,
  registerButton,
}: RecordsTableProps) {
  if (rows.length === 0) {
    return (
      <p className="records__empty">
        No records yet. They appear here as the conversation creates them.
      </p>
    );
  }

  return (
    <div className="records__sections">
      {RECORD_SECTIONS.map((section) => {
        const sectionRows = rows.filter((row) => row.kind === section.kind);
        if (sectionRows.length === 0) {
          return null;
        }
        const shown = sectionRows.slice(0, MAX_ROWS);
        const hidden = sectionRows.length - shown.length;
        return (
          <section className="records__section" key={section.kind}>
            <h3 className="records__heading">
              {section.label}
              <span className="records__count">{sectionRows.length}</span>
            </h3>
            <table className="records__table">
              <caption className="sr-only">
                {section.label}: {sectionRows.length} stored
                {sectionRows.length === 1 ? " record" : " records"}
              </caption>
              <thead>
                <tr>
                  {section.columns.map((column) => (
                    <th key={column} scope="col">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {shown.map((row) => {
                  const lastIndex = row.cells.length - 1;
                  return (
                    <tr key={row.rowKey}>
                      {row.cells.map((cell, index) =>
                        index === 0 ? (
                          <th className="records__row" scope="row" key={`${row.rowKey}:0`}>
                            <button
                              type="button"
                              className="records__row-button"
                              aria-expanded={row.rowKey === selectedKey}
                              ref={(button) => registerButton(row.rowKey, button)}
                              onClick={() => onSelect(row.rowKey)}
                            >
                              {cell}
                            </button>
                          </th>
                        ) : (
                          <td key={`${row.rowKey}:${index}`}>
                            {index === lastIndex ? (
                              <code className="records__id">{cell}</code>
                            ) : (
                              cell
                            )}
                          </td>
                        ),
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {hidden > 0 ? (
              <p className="records__cap">
                Showing first {MAX_ROWS} of {sectionRows.length} {section.label.toLowerCase()}.
              </p>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}
