import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { DatetimeNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError, clearFieldError, fieldErrorControlProps } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type DatetimeNodeT = z.infer<typeof DatetimeNodeSchema>;

// type=datetime-local rejects timezone suffixes and microsecond
// fractions. Slice the server-emitted ISO down to YYYY-MM-DDTHH:MM
// (or :SS) so the control populates correctly. Round-trip is lossy
// for microsecond precision and tz info in Phase 5; spec accepts that.
function isoToDatetimeLocal(iso: string | null): string {
  if (iso === null) return "";
  // Match "YYYY-MM-DDTHH:MM" (optionally with seconds) then stop.
  const match = iso.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)/);
  return match ? match[1] : iso;
}

export function DatetimeField({ node, path }: { node: DatetimeNodeT; path: string }) {
  const mutation = useApplyMutation();
  const initial = isoToDatetimeLocal(node.value);
  const [local, setLocal] = useState<string>(initial);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(isoToDatetimeLocal(node.value));
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
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        {...fieldErrorControlProps(error, path)}
        name={node.name}
        type="datetime-local"
        step="1"
        value={local}
        onChange={(e) => {
          setLocal(e.target.value);
          clearFieldError(error, setError);
        }}
        onBlur={() => {
          if (local === initial) return;
          const wire = local.trim() === "" ? null : local;
          mutation.mutate(
            { op: "set_value", path, value: wire },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <FieldError message={error} path={path} />
    </FieldRow>
  );
}
