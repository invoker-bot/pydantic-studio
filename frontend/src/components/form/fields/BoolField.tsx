import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { BoolNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError, fieldErrorControlProps } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

type BoolNode = z.infer<typeof BoolNodeSchema>;

export function BoolField({ node, path }: { node: BoolNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<boolean>(node.value ?? false);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value ?? false);
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
      <div className="pt-1">
        <Switch
          id={`field-${path}`}
        {...fieldErrorControlProps(error, path)}
          name={node.name}
          checked={local}
          onCheckedChange={(checked: boolean) => {
            setLocal(checked);
            // Switches mutate immediately (no blur for a checkbox)
            mutation.mutate(
              { op: "set_value", path, value: checked },
              { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
            );
          }}
        />
      </div>
      <FieldError message={error} path={path} />
    </FieldRow>
  );
}
