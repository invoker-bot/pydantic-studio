import { useState } from "react";

import type { VariantStateData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import {
  FieldError,
  fieldErrorControlProps,
} from "@/components/form/chrome/FieldError";
import { useFormFlags } from "@/components/form/errors";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function VariantSelector({ variant }: { variant: VariantStateData }) {
  const mutation = useApplyMutation();
  const flags = useFormFlags();
  const isRootVariantReadonly = flags.readonlyPaths.size > 0;
  const [variantError, setVariantError] = useState<string | null>(null);
  const variantErrorPath = "root.variant";
  const variantErrorProps = fieldErrorControlProps(
    variantError,
    variantErrorPath,
  );
  const selected = variant.options.find(
    (option) => option.id === variant.selected_id,
  );

  return (
    <div className="space-y-2 rounded-md border border-zinc-200 bg-zinc-50 p-3">
      <Label htmlFor="variant-selector" className="text-sm font-medium">
        Variant
      </Label>
      <Select
        disabled={isRootVariantReadonly}
        value={variant.selected_id}
        onValueChange={(variant_id) => {
          setVariantError(null);
          mutation.mutate(
            { op: "select_root_variant", variant_id },
            {
              onSuccess: () => setVariantError(null),
              onError: (err) => {
                setVariantError(
                  `Variant failed: ${
                    err instanceof Error ? err.message : String(err)
                  }`,
                );
              },
            },
          );
        }}
      >
        <SelectTrigger
          id="variant-selector"
          aria-label="Variant"
          disabled={isRootVariantReadonly}
          {...variantErrorProps}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {variant.options.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {selected?.description && (
        <p className="text-xs text-zinc-500">{selected.description}</p>
      )}
      <FieldError message={variantError} path={variantErrorPath} />
    </div>
  );
}
