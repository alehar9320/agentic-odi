import { canvasStatus } from "../../lib/canvasProvenance";
import { buildRecords } from "../../lib/records";
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

return (
<div className="records">
{status ? (
<p className="records__provenance" title={status.detail}>
{status.label}
</p>
) : null}
<RecordsTable rows={rows} />
</div>
);
}
