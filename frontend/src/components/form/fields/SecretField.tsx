import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { SecretNodeSchema } from "@/api/schemas";
import { Chip } from "@/components/form/chrome/Chip";
import { Description } from "@/components/form/chrome/Description";
import { FieldError, clearFieldError, fieldErrorControlProps } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type SecretNodeT = z.infer<typeof SecretNodeSchema>;

export function SecretField({ node, path }: { node: SecretNodeT; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(node.value ?? "");
  const [error, setError] = useState<string | null>(node.error);
  const [revealed, setRevealed] = useState<boolean>(false);

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
        <Chip>Secret{node.secret_kind === "bytes" ? "Bytes" : "Str"}</Chip>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <div className="flex gap-2">
        <Input
          id={`field-${path}`}
        {...fieldErrorControlProps(error, path)}
          name={node.name}
          type={revealed ? "text" : "password"}
          autoComplete="new-password"
          value={local}
          onChange={(e) => {
          setLocal(e.target.value);
          clearFieldError(error, setError);
        }}
          onBlur={() => {
            if (local === (node.value ?? "")) return;
            // For secret_kind=="bytes", backend's _maybe_coerce_typed_value
            // calls value.encode() to produce bytes. For secret_kind=="str",
            // the wire value passes through unchanged.
            mutation.mutate(
              { op: "set_value", path, value: local },
              { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
            );
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={revealed ? `hide ${node.name}` : `show ${node.name}`}
          aria-pressed={revealed}
          onClick={() => setRevealed((v) => !v)}
        >
          {revealed ? "hide" : "show"}
        </Button>
      </div>
      <FieldError message={error} path={path} />
    </FieldRow>
  );
}
