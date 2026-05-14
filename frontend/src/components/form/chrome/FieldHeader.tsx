// Header row above a field's input: label + type badge + required pill.

import type { ReactNode } from "react";

export function FieldHeader({ children }: { children: ReactNode }) {
  return <div className="flex items-baseline gap-2">{children}</div>;
}
