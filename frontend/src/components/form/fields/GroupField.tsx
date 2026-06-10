import { useEffect, useState } from "react";

import type { GroupNodeData } from "@/api/schemas";
import { hasErrorUnder, useFormFlags } from "@/components/form/errors";
import { FormField } from "@/components/form/FormField";
import { childPath } from "@/components/form/path";
import { isUnsetSubtree } from "@/lib/required";
import { shortTypeName } from "@/lib/typeName";

export function GroupField({
  node,
  path,
}: { node: GroupNodeData; path: string }) {
  // Root group (path === "") expands the children directly with no card
  // chrome - it IS the form. Nested groups render with a collapsible
  // card so the hierarchy is visible.
  if (path === "") {
    return (
      <div className="space-y-6">
        {node.fields.map((child) => (
          <FormField
            key={child.name}
            node={child}
            path={childPath(path, child.name)}
          />
        ))}
      </div>
    );
  }
  return <NestedGroup node={node} path={path} />;
}

function NestedGroup({
  node,
  path,
}: { node: GroupNodeData; path: string }) {
  // Collapsed by default: a 30-field schema with nested models used to
  // render as one giant wall (every plugin card fully spread, optional
  // models looking mandatory). The summary line carries the scent;
  // expansion is one click — and automatic when a submit error points
  // inside.
  const [expanded, setExpanded] = useState(false);
  const flags = useFormFlags();
  const errored = hasErrorUnder(flags, path);

  useEffect(() => {
    if (errored) setExpanded(true);
  }, [errored]);

  const unset = isUnsetSubtree(node);
  const summary = unset
    ? "not set — expand to configure"
    : `${node.fields.length} ${node.fields.length === 1 ? "field" : "fields"}`;
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50/50">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-100"
        aria-expanded={expanded}
      >
        <span className="flex items-baseline gap-2">
          <span className="text-xs font-mono uppercase text-zinc-500">group</span>
          <span className="font-medium">{node.name}</span>
          {node.schema_class && (
            <span className="text-xs text-zinc-400">
              {shortTypeName(node.schema_class)}
            </span>
          )}
          <span className="text-xs text-zinc-400">{summary}</span>
        </span>
        <span className="text-zinc-400">{expanded ? "v" : ">"}</span>
      </button>
      {expanded && (
        <div className="space-y-4 border-t border-zinc-200 p-4 bg-white">
          {node.fields.map((child) => (
            <FormField
              key={child.name}
              node={child}
              path={childPath(path, child.name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
