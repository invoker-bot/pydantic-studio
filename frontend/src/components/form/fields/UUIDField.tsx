import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { UUIDNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type UUIDNode = z.infer<typeof UUIDNodeSchema>;

// crypto.randomUUID is available in all modern evergreen browsers
// (Chrome 92+, Firefox 95+, Safari 15.4+). Fall back to a v4-shaped
// hex string from getRandomValues for older targets; we only need to
// produce something the backend's UUID(value) parses, which Python's
// uuid module is lenient about (any valid 32-hex-with-hyphens form).
function generateUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const buf = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(buf);
  } else {
    for (let i = 0; i < 16; i++) buf[i] = Math.floor(Math.random() * 256);
  }
  // Force v4 format: byte 6 = 0x4X, byte 8 = 0x[8-b]X.
  buf[6] = (buf[6] & 0x0f) | 0x40;
  buf[8] = (buf[8] & 0x3f) | 0x80;
  const hex = Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function UUIDField({ node, path }: { node: UUIDNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value ?? "");
    setError(node.error);
  }, [node.value, node.error]);

  const commit = (next: string) => {
    if (next === (node.value ?? "")) return;
    mutation.mutate(
      { op: "set_value", path, value: next },
      { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
    );
  };

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
      <div className="flex gap-2">
        <Input
          id={`field-${path}`}
          name={node.name}
          type="text"
          className="font-mono text-sm"
          placeholder="00000000-0000-0000-0000-000000000000"
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          onBlur={() => commit(local)}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={`regenerate ${node.name}`}
          onClick={() => {
            const next = generateUuid();
            setLocal(next);
            commit(next);
          }}
        >
          regenerate
        </Button>
      </div>
      <FieldError message={error} />
    </FieldRow>
  );
}
