// Small monospace pill used to surface modifier/constraint hints next
// to a field label (e.g. "hex", "finite", "IPv4", "SecretStr"). Shares
// styling with TypeBadge but is semantically distinct: TypeBadge
// renders the field's type, Chip annotates a field-specific modifier.

import type { ReactNode } from "react";

export function Chip({
  children,
  title,
}: { children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600"
    >
      {children}
    </span>
  );
}
