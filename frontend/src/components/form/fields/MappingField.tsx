import { useEffect, useState } from "react";

import type { MappingNodeData, FormNodeData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import { ContainerConstraintChips } from "@/components/form/chrome/ContainerConstraintChips";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import {
  hasReadonlyUnder,
  useFormFlags,
} from "@/components/form/errors";
import { FormField } from "@/components/form/FormField";
import { childPath } from "@/components/form/path";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

// MappingNode.entries are [k_node, v_node] tuples; for dict[str, V] the
// k_node is a StringNode whose .value is the key string. Generic
// extraction so dict[int, ...] keys would also work (their k_node.value
// is the int).
function entryKey(k: FormNodeData): string {
  if ("value" in k && k.value !== null && k.value !== undefined) {
    return String(k.value);
  }
  return "";
}

function typeTail(typeName: string): string {
  const parts = typeName.split(".");
  return parts[parts.length - 1] ?? typeName;
}

function nextDefaultKey(node: MappingNodeData): string {
  const existing = new Set(node.entries.map(([k]) => entryKey(k)));
  const keyType = typeTail(node.key_type_name);
  if (keyType === "int" || keyType === "float") {
    let i = 0;
    while (existing.has(String(i))) i += 1;
    return String(i);
  }
  if (keyType === "bool") {
    for (const candidate of ["false", "true"]) {
      if (!existing.has(candidate)) return candidate;
    }
  }
  let i = 0;
  while (existing.has(`key${i}`)) i += 1;
  return `key${i}`;
}

export function MappingField({
  node,
  path,
}: { node: MappingNodeData; path: string }) {
  const mutation = useApplyMutation();
  const flags = useFormFlags();
  const readonlyStructure = hasReadonlyUnder(flags, path);
  const structureDisabled = readonlyStructure;
  const entryCount = node.entries.length;
  const atMinLength = node.min_length !== null && entryCount <= node.min_length;
  const atMaxLength = node.max_length !== null && entryCount >= node.max_length;

  const onAdd = () => {
    mutation.mutate({ op: "add_entry", path, key: nextDefaultKey(node) });
  };
  const onRemove = (index: number) =>
    mutation.mutate({ op: "remove_entry", path, index });
  const onRenameKey = (index: number, new_key: string) =>
    mutation.mutate({ op: "rename_key", path, index, new_key });

  return (
    <FieldRow>
      <FieldHeader>
        <Label className="text-sm font-medium">{node.name}</Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
        <ContainerConstraintChips constraints={node} />
        <span className="text-xs text-zinc-400">
          {entryCount} {entryCount === 1 ? "entry" : "entries"}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <div className="space-y-2">
        {node.entries.map(([k_node, v_node], index) => (
          <MappingEntry
            key={index}
            entryKey={entryKey(k_node)}
            valueNode={v_node}
            valuePath={childPath(path, index)}
            onRenameKey={(new_key) => onRenameKey(index, new_key)}
            onRemove={() => onRemove(index)}
            removeDisabled={structureDisabled || atMinLength}
            keyDisabled={structureDisabled}
          />
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full border-dashed text-zinc-500"
          disabled={structureDisabled || atMaxLength}
          onClick={onAdd}
        >
          + Add Entry
        </Button>
      </div>
      <FieldError message={node.error} />
    </FieldRow>
  );
}

function MappingEntry({
  entryKey,
  valueNode,
  valuePath,
  onRenameKey,
  onRemove,
  removeDisabled,
  keyDisabled,
}: {
  entryKey: string;
  valueNode: FormNodeData;
  valuePath: string;
  onRenameKey: (new_key: string) => void;
  onRemove: () => void;
  removeDisabled: boolean;
  keyDisabled: boolean;
}) {
  const [keyLocal, setKeyLocal] = useState(entryKey);
  useEffect(() => setKeyLocal(entryKey), [entryKey]);

  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50/50">
      <div className="flex items-center gap-2 px-3 py-1.5">
        <Input
          value={keyLocal}
          onChange={(e) => setKeyLocal(e.target.value)}
          onBlur={() => {
            if (keyLocal !== entryKey) onRenameKey(keyLocal);
          }}
          className="h-7 text-xs font-mono"
          aria-label="entry key"
          disabled={keyDisabled}
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={removeDisabled}
          onClick={onRemove}
          aria-label="remove entry"
        >
          x
        </Button>
      </div>
      <div className="border-t border-zinc-200 bg-white p-3">
        <FormField node={valueNode} path={valuePath} />
      </div>
    </div>
  );
}
