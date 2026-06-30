// Small monospace pill showing the field's type + constraints.
// Examples:
//   "str · 3..32"
//   "int · ≥1 · ≤64"
//   "HttpUrl"

import type { FormNodeData } from "@/api/schemas";

function formatNumeric(node: FormNodeData): string {
  const parts: string[] = [];
  if ("ge" in node && node.ge !== null) parts.push(`≥${node.ge}`);
  if ("le" in node && node.le !== null) parts.push(`≤${node.le}`);
  if ("gt" in node && node.gt !== null) parts.push(`>${node.gt}`);
  if ("lt" in node && node.lt !== null) parts.push(`<${node.lt}`);
  if ("multiple_of" in node && node.multiple_of !== null) {
    parts.push(`%${node.multiple_of}`);
  }
  return parts.join(" · ");
}

function formatString(node: FormNodeData): string {
  if (!("min_length" in node)) return "";
  const min = node.min_length;
  const max = node.max_length;
  if (min !== null && max !== null) return `${min}..${max}`;
  if (min !== null) return `≥${min}`;
  if (max !== null) return `≤${max}`;
  return "";
}

export function TypeBadge({ node }: { node: FormNodeData }) {
  let summary: string = node.kind;
  if (node.kind === "int" || node.kind === "float" || node.kind === "decimal") {
    const constraints = formatNumeric(node);
    if (constraints) summary = `${node.kind} · ${constraints}`;
  } else if (node.kind === "string") {
    const constraints = formatString(node);
    if (constraints) summary = `str · ${constraints}`;
    else summary = "str";
  }
  return (
    <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
      {summary}
    </span>
  );
}
