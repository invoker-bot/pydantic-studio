import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { URLNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { shortTypeName } from "@/lib/typeName";

type URLNode = z.infer<typeof URLNodeSchema>;

export function URLField({ node, path }: { node: URLNode; path: string }) {
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
        <span className="rounded bg-zinc-100 px-1.5 font-mono text-[10px] text-zinc-600">
          {shortTypeName(node.target_type_name)}
        </span>
      </FieldHeader>
      {node.description && <Description>{node.description}</Description>}
      <Input
        id={`field-${path}`}
        name={node.name}
        type="url"
        placeholder="https://example.com"
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
      <FieldError message={error} />
    </FieldRow>
  );
}
