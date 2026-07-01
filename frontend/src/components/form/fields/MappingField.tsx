import { useEffect, useState } from "react";

import type { MappingNodeData, FormNodeData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import { ContainerConstraintChips } from "@/components/form/chrome/ContainerConstraintChips";
import { Description } from "@/components/form/chrome/Description";
import {
  FieldError,
  clearFieldError,
  fieldErrorControlProps,
} from "@/components/form/chrome/FieldError";
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
  const [structureError, setStructureError] = useState<string | null>(null);
  const readonlyStructure = hasReadonlyUnder(flags, path);
  const structureDisabled = readonlyStructure;
  const structureErrorPath = `${path}.structure`;
  const entryCount = node.entries.length;
  const atMinLength = node.min_length !== null && entryCount <= node.min_length;
  const atMaxLength = node.max_length !== null && entryCount >= node.max_length;

  const structuralErrorProps = fieldErrorControlProps(
    structureError,
    structureErrorPath,
  );
  const onStructureError = (e: unknown) =>
    setStructureError(e instanceof Error ? e.message : String(e));
  const onAdd = () => {
    mutation.mutate(
      { op: "add_entry", path, key: nextDefaultKey(node) },
      { onSuccess: () => setStructureError(null), onError: onStructureError },
    );
  };
  const onRemove = (index: number) =>
    mutation.mutate(
      { op: "remove_entry", path, index },
      { onSuccess: () => setStructureError(null), onError: onStructureError },
    );

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
            mappingPath={path}
            entryIndex={index}
            valuePath={childPath(path, index)}
            onRemove={() => onRemove(index)}
            removeDisabled={structureDisabled || atMinLength}
            removeErrorProps={structuralErrorProps}
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
          aria-label={`add ${node.name} entry`}
          {...structuralErrorProps}
        >
          + Add Entry
        </Button>
      </div>
      <FieldError message={structureError} path={structureErrorPath} />
      <FieldError message={node.error} />
    </FieldRow>
  );
}

function MappingEntry({
  entryKey,
  valueNode,
  mappingPath,
  entryIndex,
  valuePath,
  onRemove,
  removeDisabled,
  removeErrorProps,
  keyDisabled,
}: {
  entryKey: string;
  valueNode: FormNodeData;
  mappingPath: string;
  entryIndex: number;
  valuePath: string;
  onRemove: () => void;
  removeDisabled: boolean;
  removeErrorProps: ReturnType<typeof fieldErrorControlProps>;
  keyDisabled: boolean;
}) {
  const mutation = useApplyMutation();
  const [keyLocal, setKeyLocal] = useState(entryKey);
  const [keyError, setKeyError] = useState<string | null>(null);
  const keyErrorPath = `${valuePath}.key`;

  useEffect(() => {
    setKeyLocal(entryKey);
    setKeyError(null);
  }, [entryKey]);

  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50/50">
      <div className="flex items-center gap-2 px-3 py-1.5">
        <Input
          value={keyLocal}
          onChange={(e) => {
            setKeyLocal(e.target.value);
            clearFieldError(keyError, setKeyError);
          }}
          onBlur={() => {
            if (keyLocal !== entryKey) {
              mutation.mutate(
                {
                  op: "rename_key",
                  path: mappingPath,
                  index: entryIndex,
                  new_key: keyLocal,
                },
                {
                  onSuccess: () => setKeyError(null),
                  onError: (e) =>
                    setKeyError(e instanceof Error ? e.message : String(e)),
                },
              );
            }
          }}
          className="h-7 text-xs font-mono"
          aria-label="entry key"
          {...fieldErrorControlProps(keyError, keyErrorPath)}
          disabled={keyDisabled}
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={removeDisabled}
          onClick={onRemove}
          aria-label={`remove entry ${entryKey}`}
          {...removeErrorProps}
        >
          x
        </Button>
      </div>
      {keyError && (
        <div className="px-3 pb-2">
          <FieldError message={keyError} path={keyErrorPath} />
        </div>
      )}
      <div className="border-t border-zinc-200 bg-white p-3">
        <FormField node={valueNode} path={valuePath} />
      </div>
    </div>
  );
}
