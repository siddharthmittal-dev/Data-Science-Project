import { createRequire } from "node:module";
import { join } from "node:path";
import { rm } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const [, , runtime, output] = process.argv;
const require = createRequire(join(runtime, "package.json"));
const { Workbook, SpreadsheetFile } = await import(pathToFileURL(require.resolve("@oai/artifact-tool")).href);
let input = "";
for await (const chunk of process.stdin) input += chunk;
const records = JSON.parse(input);
const headers = Object.keys(records[0]);
const rows = records.map(({ day, ...fields }) => [
  Date.parse(day + "T00:00:00Z") / 86400000 + 25569, ...Object.values(fields),
]);
const book = Workbook.create();
const sheet = book.worksheets.add("Daily demand");
sheet.getRangeByIndexes(0, 0, rows.length + 1, headers.length).values = [headers, ...rows];
const head = sheet.getRange("A1:K1");
head.format.fill = "#28594F";
head.format.font.color = "#FFFFFF";
head.format.font.bold = true;
for (let i = 0; i < headers.length; i++)
  sheet.getRangeByIndexes(0, i, 1, 1).format.columnWidth = Math.max(13, headers[i].length + 4);
sheet.getRange("A2:A" + (rows.length + 1)).setNumberFormat("yyyy-mm-dd");
sheet.freezePanes.freezeRows(1);
book.recalculate();
const file = await SpreadsheetFile.exportXlsx(book);
await file.save(output);
await rm(output + ".inspect.ndjson", { force: true });
