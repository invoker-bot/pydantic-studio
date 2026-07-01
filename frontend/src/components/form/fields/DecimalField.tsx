import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { DecimalNodeSchema } from "@/api/schemas";
import { Chip } from "@/components/form/chrome/Chip";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type DecimalNode = z.infer<typeof DecimalNodeSchema>;

export function DecimalField({ node, path }: { node: DecimalNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value ?? "");
    setError(node.error);
  }, [node.value, node.error]);

  return (
    <FieldRow>
      <FieldHeader>
        <Label htmlFor={`field-${path}`} className="text-sm font-medium">
          {node.name}
        </Label>
        <TypeBadge node={node} />
        {node.required && <RequiredBadge />}
        {node.max_digits !== null && <Chip>{node.max_digits} digits</Chip>}
        {!node.allow_inf_nan && <Chip>finite</Chip>}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="text"
        inputMode="decimal"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
          // Wire format is a string; backend coerces via Decimal(value).
          // Empty string -> null (lets DecimalNode.validate_value enforce
          // required-ness).
          const wire = local.trim() === "" ? null : local.trim();
          mutation.mutate(
            { op: "set_value", path, value: wire },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
