// Submit-error + readonly context: lets every FormField know whether
// its path is implicated without threading props through 24 field
// components, and gives containers the signal to auto-expand when a
// collapsed descendant holds an error.

import { createContext, useContext } from "react";

export interface FormFlags {
  errorPaths: ReadonlySet<string>;
  readonlyPaths: ReadonlySet<string>;
}

const EMPTY: FormFlags = {
  errorPaths: new Set<string>(),
  readonlyPaths: new Set<string>(),
};

export const FormFlagsContext = createContext<FormFlags>(EMPTY);

export function useFormFlags(): FormFlags {
  return useContext(FormFlagsContext);
}

export function hasErrorAt(flags: FormFlags, path: string): boolean {
  return path !== "" && flags.errorPaths.has(path);
}

export function hasErrorUnder(flags: FormFlags, path: string): boolean {
  if (path === "") return flags.errorPaths.size > 0;
  for (const p of flags.errorPaths) {
    if (p === path || p.startsWith(`${path}.`)) return true;
  }
  return false;
}

export function isReadonly(flags: FormFlags, path: string): boolean {
  return path !== "" && flags.readonlyPaths.has(path);
}

export function fieldAnchorId(path: string): string {
  return `field-anchor-${path}`;
}

/** Scroll to a field anchor; falls back to the nearest existing
 * ancestor anchor when the exact path isn't rendered (e.g. an error
 * deep inside a collapsed card that is still mounting). */
export function scrollToField(path: string): void {
  let candidate = path;
  while (candidate) {
    const el = document.getElementById(fieldAnchorId(candidate));
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const cut = candidate.lastIndexOf(".");
    if (cut < 0) return;
    candidate = candidate.slice(0, cut);
  }
}
