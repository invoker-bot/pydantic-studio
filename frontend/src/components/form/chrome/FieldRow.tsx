// Spacing wrapper used by every primitive field component. Provides
// vertical rhythm between fields and a consistent left-padded layout.

import type { ReactNode } from "react";

export function FieldRow({ children }: { children: ReactNode }) {
  return <div className="space-y-1.5">{children}</div>;
}
