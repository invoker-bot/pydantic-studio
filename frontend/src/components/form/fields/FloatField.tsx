import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { FloatNodeSchema } from "@/api/schemas";
import { Chip } from "@/components/form/chrome/Chip";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type FloatNode = z.infer<typeof FloatNodeSchema>;

export function FloatField({ node, path }: { node: FloatNode; path: string }) {
  const mutation = useApplyMutation();
  const initial = node.value !== null ? String(node.value) : "";
  const [local, setLocal] = useState<string>(initial);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value !== null ? String(node.value) : "");
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
        {!node.allow_inf_nan && <Chip>finite</Chip>}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="number"
        step="any"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === initial) return;
          const parsed = local.trim() === "" ? null : Number(local);
          if (parsed !== null && Number.isNaN(parsed)) {
            setError(`'${local}' is not a number`);
            return;
          }
          mutation.mutate(
            { op: "set_value", path, value: parsed },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
