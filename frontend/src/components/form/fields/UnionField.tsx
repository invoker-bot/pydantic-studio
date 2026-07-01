import type { UnionNodeData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { FormField } from "@/components/form/FormField";
import {
  hasReadonlyUnder,
  useFormFlags,
} from "@/components/form/errors";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { shortTypeName } from "@/lib/typeName";

export function UnionField({
  node,
  path,
}: { node: UnionNodeData; path: string }) {
  const mutation = useApplyMutation();
  const flags = useFormFlags();
  const readonlyVariant = hasReadonlyUnder(flags, path);

  const onSelect = (variant_index: number) =>
    mutation.mutate({ op: "select_variant", path, variant_index });

  return (
    <FieldRow>
      <FieldHeader>
        <Label className="text-sm font-medium">{node.name}</Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <div
        role="group"
        aria-label={`${node.name} variants`}
        className="flex flex-wrap gap-1"
      >
        {node.variant_type_names.map((variantName, index) => {
          const active = node.selected_index === index;
          return (
            <Button
              key={variantName}
              type="button"
              variant={active ? "default" : "outline"}
              size="sm"
              aria-pressed={active}
              aria-label={`select ${node.name} variant ${shortTypeName(variantName)}`}
              disabled={readonlyVariant}
              onClick={() => onSelect(index)}
            >
              {shortTypeName(variantName)}
              {active && " v"}
            </Button>
          );
        })}
      </div>
      {node.selected ? (
        <div className="rounded-md border border-zinc-200 bg-white p-3">
          <FormField node={node.selected} path={path} />
        </div>
      ) : (
        <p className="text-xs text-zinc-400">
          Pick a variant above to set a value.
        </p>
      )}
      <FieldError message={node.error} />
    </FieldRow>
  );
}
