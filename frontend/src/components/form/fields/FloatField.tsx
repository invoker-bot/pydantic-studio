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
type ParsedFloatWireValue =
  | { ok: true; value: number | string | null }
  | { ok: false; error: string };

function formatFloatWireValue(value: FloatNode["value"]): string {
  return value !== null && value !== undefined ? String(value) : "";
}

function parseFloatWireValue(raw: string, allowInfNan: boolean): ParsedFloatWireValue {
  const trimmed = raw.trim();
  if (trimmed === "") {
    return { ok: true, value: null };
  }
  if (
    allowInfNan &&
    (trimmed === "NaN" || trimmed === "Infinity" || trimmed === "-Infinity")
  ) {
    return { ok: true, value: trimmed };
  }
  const parsed = Number(trimmed);
  if (Number.isNaN(parsed)) {
    return { ok: false, error: `'${raw}' is not a number` };
  }
  if (!Number.isFinite(parsed)) {
    if (!allowInfNan) {
      return { ok: false, error: `'${raw}' must be finite` };
    }
    return { ok: true, value: parsed > 0 ? "Infinity" : "-Infinity" };
  }
  return { ok: true, value: parsed };
}

export function FloatField({ node, path }: { node: FloatNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(formatFloatWireValue(node.value));
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(formatFloatWireValue(node.value));
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
        type="text"
        inputMode="decimal"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === formatFloatWireValue(node.value))
            return;
          const parsed = parseFloatWireValue(local, node.allow_inf_nan);
          if (!parsed.ok) {
            setError(parsed.error);
            return;
          }
          mutation.mutate(
            { op: "set_value", path, value: parsed.value },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
