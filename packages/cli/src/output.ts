import { stderr, stdout } from "node:process";

export type OutputFormat = "auto" | "table" | "json" | "jsonl" | "raw";

const display = (value: unknown): string => {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};

const records = (data: unknown): Record<string, unknown>[] => {
  if (Array.isArray(data)) return data.map((item) => item as Record<string, unknown>);
  if (data && typeof data === "object" && Array.isArray((data as { items?: unknown }).items)) {
    return (data as { items: Record<string, unknown>[] }).items;
  }
  return data && typeof data === "object" ? [data as Record<string, unknown>] : [{ value: data }];
};

export function printData(data: unknown, requested: OutputFormat = "auto"): void {
  const format = requested === "auto" ? (stdout.isTTY ? "table" : "jsonl") : requested;
  if (format === "raw") {
    if (data instanceof Uint8Array) stdout.write(data);
    else stdout.write(String(data ?? ""));
    return;
  }
  if (format === "json") {
    stdout.write(`${JSON.stringify(data, null, 2)}\n`);
    return;
  }
  if (format === "jsonl") {
    for (const item of records(data)) stdout.write(`${JSON.stringify(item)}\n`);
    return;
  }
  const rows = records(data);
  if (rows.length === 0) return;
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const widths = columns.map((column) =>
    Math.min(60, Math.max(column.length, ...rows.map((row) => display(row[column]).length))),
  );
  const line = (row: Record<string, unknown>): string =>
    columns
      .map((column, index) =>
        display(row[column]).slice(0, widths[index]!).padEnd(widths[index]!),
      )
      .join("  ");
  stdout.write(`${line(Object.fromEntries(columns.map((column) => [column, column])))}\n`);
  stdout.write(`${widths.map((width) => "-".repeat(width)).join("  ")}\n`);
  for (const row of rows) stdout.write(`${line(row)}\n`);
}

export function diagnostic(message: string, quiet = false): void {
  if (!quiet) stderr.write(`${message}\n`);
}
