import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { AnyValueNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type AnyValueNode = z.infer<typeof AnyValueNodeSchema>;

// Display + parse the Any value as a JSON string. Mirrors the HTMX
// route (routes.py:64-74): try JSON.parse first (covers numbers,
// booleans, null, arrays, objects); fall back to raw string. The
// node.mode discriminator on the server tracks the inferred shape.

function stringifyAny(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function parseAny(raw: string): unknown {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return raw;
  }
}

export function AnyField({
  node,
  path,
}: { node: AnyValueNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(stringifyAny(node.value));
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(stringifyAny(node.value));
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
        <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
          {node.mode}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          const original = stringifyAny(node.value);
          if (local === original) return;
          mutation.mutate(
            { op: "set_value", path, value: parseAny(local) },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
        placeholder="any value (JSON or raw string)"
        className="font-mono text-xs"
      />
      <FieldError message={error} />
    </FieldRow>
  );
}
