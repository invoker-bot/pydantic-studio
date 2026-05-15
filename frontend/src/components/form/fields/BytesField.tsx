import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { BytesNodeSchema } from "@/api/schemas";
import { Chip } from "@/components/form/chrome/Chip";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type BytesNodeT = z.infer<typeof BytesNodeSchema>;

const HEX_RE = /^[0-9a-fA-F]*$/;

function byteCount(hex: string): number {
  // Whitespace-tolerant: strip spaces before counting (Phase 5 doesn't
  // enforce a strict pattern; users can paste "de ad be ef").
  return Math.floor(hex.replace(/\s+/g, "").length / 2);
}

export function BytesField({ node, path }: { node: BytesNodeT; path: string }) {
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
        <Chip>hex</Chip>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="text"
        className="font-mono text-sm"
        placeholder="deadbeef (hex)"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => {
          if (local === (node.value ?? "")) return;
          const stripped = local.replace(/\s+/g, "");
          // Soft-reject obviously-bad hex BEFORE the round-trip. The
          // backend's bytes.fromhex would also reject, but the local
          // check yields a clearer message.
          if (stripped !== "" && !HEX_RE.test(stripped)) {
            setError(`'${local}' is not valid hex`);
            return;
          }
          if (stripped.length % 2 !== 0) {
            setError(`hex must have an even number of digits (got ${stripped.length})`);
            return;
          }
          mutation.mutate(
            { op: "set_value", path, value: stripped },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      />
      <p className="text-xs text-zinc-500">{byteCount(local)} bytes</p>
      <FieldError message={error} />
    </FieldRow>
  );
}
