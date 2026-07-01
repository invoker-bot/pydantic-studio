import { useState } from "react";

import type { SequenceNodeData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import { ContainerConstraintChips } from "@/components/form/chrome/ContainerConstraintChips";
import { Description } from "@/components/form/chrome/Description";
import {
  FieldError,
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
import { Label } from "@/components/ui/label";
import { shortTypeName } from "@/lib/typeName";

export function SequenceField({
  node,
  path,
}: { node: SequenceNodeData; path: string }) {
  const mutation = useApplyMutation();
  const flags = useFormFlags();
  const [structureError, setStructureError] = useState<string | null>(null);
  const readonlyStructure = hasReadonlyUnder(flags, path);
  const structureDisabled = readonlyStructure || node.origin === "tuple_fixed";
  const structureErrorPath = `${path}.structure`;
  const itemCount = node.items.length;
  const atMinLength = node.min_length !== null && itemCount <= node.min_length;
  const atMaxLength = node.max_length !== null && itemCount >= node.max_length;

  const structuralErrorProps = fieldErrorControlProps(
    structureError,
    structureErrorPath,
  );
  const onStructureError = (e: unknown) =>
    setStructureError(e instanceof Error ? e.message : String(e));
  const onAdd = () =>
    mutation.mutate(
      { op: "add_item", path },
      { onSuccess: () => setStructureError(null), onError: onStructureError },
    );
  const onRemove = (index: number) =>
    mutation.mutate(
      { op: "remove_item", path, index },
      { onSuccess: () => setStructureError(null), onError: onStructureError },
    );
  const onMove = (from: number, to: number) =>
    mutation.mutate(
      { op: "move_item", path, from, to },
      { onSuccess: () => setStructureError(null), onError: onStructureError },
    );

  // item_type_name is null for tuple_fixed (heterogeneous slots); fall
  // back to a generic "item" label for the +Add button.
  const itemLabel = node.item_type_name
    ? shortTypeName(node.item_type_name, "item")
    : "item";

  return (
    <FieldRow>
      <FieldHeader>
        <Label className="text-sm font-medium">{node.name}</Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
        <ContainerConstraintChips constraints={node} />
        <span className="text-xs text-zinc-400">
          {itemCount} {itemCount === 1 ? "item" : "items"}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <div className="space-y-2">
        {node.items.map((item, index) => (
          <div
            key={index}
            className="rounded-md border border-zinc-200 bg-zinc-50/50"
          >
            <div className="flex items-center justify-between px-3 py-1.5 text-xs">
              <span className="font-mono text-zinc-500">[{index}]</span>
              <div className="flex gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={structureDisabled || index === 0}
                  onClick={() => onMove(index, index - 1)}
                  aria-label={`move ${node.name}[${index}] up`}
                  {...structuralErrorProps}
                >
                  ^
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={structureDisabled || index === itemCount - 1}
                  onClick={() => onMove(index, index + 1)}
                  aria-label={`move ${node.name}[${index}] down`}
                  {...structuralErrorProps}
                >
                  v
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={structureDisabled || atMinLength}
                  onClick={() => onRemove(index)}
                  aria-label={`remove ${node.name}[${index}]`}
                  {...structuralErrorProps}
                >
                  x
                </Button>
              </div>
            </div>
            <div className="border-t border-zinc-200 bg-white p-3">
              <FormField node={item} path={childPath(path, index)} />
            </div>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full border-dashed text-zinc-500"
          disabled={structureDisabled || atMaxLength}
          onClick={onAdd}
          aria-label={`add ${node.name} item`}
          {...structuralErrorProps}
        >
          + Add {itemLabel}
        </Button>
      </div>
      <FieldError message={structureError} path={structureErrorPath} />
      <FieldError message={node.error} />
    </FieldRow>
  );
}
