/**
 * Lightweight CSV generation and download utility.
 * No external dependencies — uses native Blob + URL.createObjectURL.
 */

export interface CSVMetadata {
  source: string;
  generatedAt?: string;
  filters?: Record<string, string>;
}

/**
 * Escapes a CSV field value: wraps in quotes if it contains comma, quote, or newline.
 */
function escapeField(value: string): string {
  if (
    value.includes(",") ||
    value.includes('"') ||
    value.includes("\n") ||
    value.includes("\r")
  ) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

/**
 * Generates CSV content from headers, rows, and optional metadata.
 * Metadata is prepended as comment lines (prefixed with #).
 */
export function generateCSV(
  headers: string[],
  rows: (string | number)[][],
  metadata?: CSVMetadata
): string {
  const lines: string[] = [];

  // Metadata as comment lines
  if (metadata) {
    const timestamp = metadata.generatedAt || new Date().toISOString();
    lines.push(`# Generated: ${timestamp}`);
    lines.push(`# Source: ${metadata.source}`);
    if (metadata.filters) {
      const filterStr = Object.entries(metadata.filters)
        .map(([k, v]) => `${k}=${v}`)
        .join("; ");
      lines.push(`# Filters: ${filterStr}`);
    }
    lines.push("#");
  }

  // Header row
  lines.push(headers.map((h) => escapeField(h)).join(","));

  // Data rows
  for (const row of rows) {
    lines.push(row.map((cell) => escapeField(String(cell))).join(","));
  }

  return lines.join("\n");
}

/**
 * Triggers a browser download of a CSV string as a file.
 */
export function downloadCSV(csvContent: string, filename: string): void {
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Convenience: generate CSV and immediately trigger download.
 */
export function exportCSV(
  headers: string[],
  rows: (string | number)[][],
  filename: string,
  metadata?: CSVMetadata
): void {
  const csv = generateCSV(headers, rows, metadata);
  downloadCSV(csv, filename);
}
