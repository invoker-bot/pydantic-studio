// Small monospace pill showing the field's type. Field-specific
// modifiers and validation constraints render as separate Chip pills.

import type { FormNodeData } from "@/api/schemas";

export function TypeBadge({ node }: { node: FormNodeData }) {
  let summary: string = node.kind;
  if (node.kind === "string") {
    summary = "str";
  }
  return (
    <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
      {summary}
    </span>
  );
}
