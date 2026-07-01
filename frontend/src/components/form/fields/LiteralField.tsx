import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { LiteralNodeSchema } from "@/api/schemas";
import { Description } from "@/components/form/chrome/Description";
import { FieldError, fieldErrorControlProps } from "@/components/form/chrome/FieldError";
import { FieldHeader } from "@/components/form/chrome/FieldHeader";
import { FieldRow } from "@/components/form/chrome/FieldRow";
import { RequiredBadge } from "@/components/form/chrome/RequiredBadge";
import { TypeBadge } from "@/components/form/chrome/TypeBadge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type LiteralNode = z.infer<typeof LiteralNodeSchema>;

export function LiteralField({ node, path }: { node: LiteralNode; path: string }) {
  const mutation = useApplyMutation();
  const currentStr = node.value === null || node.value === undefined ? "" : String(node.value);
  const [local, setLocal] = useState<string>(currentStr);
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(node.value === null || node.value === undefined ? "" : String(node.value));
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
      <Select
        value={local}
        onValueChange={(picked) => {
          setLocal(picked);
          // Send the raw choice value; the server matches against the
          // original literal choices via __eq__.
          const matchedChoice = node.choices.find((c) => String(c) === picked);
          const valueToSend = matchedChoice ?? picked;
          mutation.mutate(
            { op: "set_value", path, value: valueToSend },
            { onError: (e) => setError(e instanceof Error ? e.message : String(e)) },
          );
        }}
      >
        <SelectTrigger
          id={`field-${path}`}
          {...fieldErrorControlProps(error, path)}
          name={node.name}
        >
          <SelectValue placeholder="Select..." />
        </SelectTrigger>
        <SelectContent>
          {node.choices.map((choice) => {
            const str = String(choice);
            return <SelectItem key={str} value={str}>{str}</SelectItem>;
          })}
        </SelectContent>
      </Select>
      <FieldError message={error} path={path} />
    </FieldRow>
  );
}
