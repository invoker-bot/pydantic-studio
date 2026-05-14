// Minimal GroupField for Phase 3: just iterates child fields. No
// collapsible chrome, no nested-card visual treatment - those land
// in Phase 4 when sequence/mapping/union containers raise the bar
// for what "nested" looks like. The interface (props.node, props.path)
// is the long-term contract.

import type { GroupNodeData } from "@/api/schemas";
import { FormField } from "@/components/form/FormField";

export function GroupField({ node, path }: { node: GroupNodeData; path: string }) {
  return (
    <div className="space-y-6">
      {node.fields.map((child) => (
        <FormField
          key={child.name}
          node={child}
          path={path ? `${path}.${child.name}` : child.name}
        />
      ))}
    </div>
  );
}
