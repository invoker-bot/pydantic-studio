import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { TimeNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError, fieldErrorControlProps } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type TimeNodeT = z.infer<typeof TimeNodeSchema>;

// Browsers' type=time control accepts "HH:MM" or "HH:MM:SS". If the
// server emitted "HH:MM:SS.microseconds" (Python time has microsecond
// resolution), slice off the seconds-fraction before binding to the
// native control so it doesn't display blank.
function isoToTimeInput(iso: string | null): string {
  if (iso === null) return "";
  // Strip microseconds and trailing tz for the control value (commit
  // sends the trimmed value; round-trip is lossy for microsecond
  // precision — acceptable for Phase 5).
  const match = iso.match(/^(\d{2}:\d{2}(?::\d{2})?)/);
  return match ? match[1] : iso;
}

export function TimeField({ node, path }: { node: TimeNodeT; path: string }) {
  const mutation = useApplyMutation();
  const initial = isoToTimeInput(node.value);
  const [local, setLocal] = useState<string>(initial);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(isoToTimeInput(node.value));
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
        type="time"
        step="1"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
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
