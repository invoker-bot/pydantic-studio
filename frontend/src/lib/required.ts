// Client-side mirror of FormTree.missing_required_paths — drives the
// "N required missing" counter and the jump button in the header.
// Keep the semantics in sync with tree/nodes.py:
// - groups recurse; an *optional* group whose subtree is all-unset
//   resolves to the field default and contributes nothing
// - sequences/mappings recurse into items / entry values
// - a selected union recurses; an unselected union only counts when
//   the union field itself is required

import type {
  FormNodeData,
  GroupNodeData,
  MappingNodeData,
  SequenceNodeData,
  UnionNodeData,
} from "@/api/schemas";

export function isUnsetSubtree(node: FormNodeData): boolean {
  switch (node.kind) {
    case "group":
      return (node as GroupNodeData).fields.every(isUnsetSubtree);
    case "sequence":
      return (node as SequenceNodeData).items.length === 0;
    case "mapping":
      return (node as MappingNodeData).entries.length === 0;
    case "union":
      return (node as UnionNodeData).selected == null;
    default:
      return (node as { value?: unknown }).value == null;
  }
}

export function missingRequiredPaths(
  node: FormNodeData,
  base = "",
): string[] {
  const join = (segment: string | number) =>
    base ? `${base}.${segment}` : String(segment);
  const out: string[] = [];
  switch (node.kind) {
    case "group": {
      const group = node as GroupNodeData;
      if (!group.required && isUnsetSubtree(group)) return out;
      for (const child of group.fields) {
        out.push(...missingRequiredPaths(child, join(child.name)));
      }
      return out;
    }
    case "sequence": {
      (node as SequenceNodeData).items.forEach(
        (item: FormNodeData, idx: number) => {
          out.push(...missingRequiredPaths(item, join(idx)));
        },
      );
      return out;
    }
    case "mapping": {
      (node as MappingNodeData).entries.forEach(
        (entry: [FormNodeData, FormNodeData], idx: number) => {
          out.push(...missingRequiredPaths(entry[1], join(idx)));
        },
      );
      return out;
    }
    case "union": {
      const union = node as UnionNodeData;
      if (union.selected != null) {
        out.push(...missingRequiredPaths(union.selected, base));
      } else if (union.required) {
        out.push(base);
      }
      return out;
    }
    default: {
      const leaf = node as { required?: boolean; value?: unknown };
      if (leaf.required && leaf.value == null) out.push(base);
      return out;
    }
  }
}
