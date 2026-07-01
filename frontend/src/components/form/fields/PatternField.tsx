import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { PatternNodeSchema } from "@/api/schemas";
import { Chip } from "@/components/form/chrome/Chip";
import { Description } from "@/components/form/chrome/Description";
import { FieldError, fieldErrorControlProps } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type PatternNodeT = z.infer<typeof PatternNodeSchema>;

// Python re-module flag bitmask values. Mirrors `re` constants.
// UNICODE (32) is intentionally omitted - PatternNode strips it
// before storing so it never reaches this component.
const FLAG_CHIPS: ReadonlyArray<{ bit: number; label: string; tooltip: string }> = [
  { bit: 2, label: "i", tooltip: "IGNORECASE" },
  { bit: 8, label: "m", tooltip: "MULTILINE" },
  { bit: 16, label: "s", tooltip: "DOTALL" },
  { bit: 64, label: "x", tooltip: "VERBOSE" },
  { bit: 256, label: "a", tooltip: "ASCII" },
];

function activeFlagChips(flags: number) {
  return FLAG_CHIPS.filter((chip) => (flags & chip.bit) !== 0);
}

export function PatternField({ node, path }: { node: PatternNodeT; path: string }) {
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
        {activeFlagChips(node.flags).map((chip) => (
          <Chip key={chip.bit} title={chip.tooltip}>
            {chip.label}
          </Chip>
        ))}
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        {...fieldErrorControlProps(error, path)}
        name={node.name}
        type="text"
        className="font-mono text-sm"
        placeholder="regex source"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
          mutation.mutate(
            { op: "set_value", path, value: local },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} path={path} />
    </FieldRow>
  );
}
