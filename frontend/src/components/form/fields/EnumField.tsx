import { useEffect, useState } from "react";
import type { z } from "zod";

import { useApplyMutation } from "@/api/mutations";
import type { EnumNodeSchema } from "@/api/schemas";
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

type EnumNode = z.infer<typeof EnumNodeSchema>;

// EnumNode.value and each choices[i][1] are serialized as the
// member's `.name` by EnumNode._serialize_member (canonical wire
// format). currentName looks up the matching choice; the
// `String(member) === valStr` branch is defensive (kept against a
// future serializer change) but doesn't fire today.

function currentName(node: EnumNode): string {
  // value may be undefined / null / serialized as either name or value
  if (node.value === null || node.value === undefined) return "";
  const valStr = String(node.value);
  // Find the choice whose name OR whose serialized member matches
  for (const [name, member] of node.choices) {
    if (name === valStr) return name;
    if (String(member) === valStr) return name;
  }
  return valStr;   // fallback - displays as-is
}

export function EnumField({ node, path }: { node: EnumNode; path: string }) {
  const mutation = useApplyMutation();
  const [local, setLocal] = useState<string>(currentName(node));
  const [error, setError] = useState<string | null>(node.error);

  useEffect(() => {
    setLocal(currentName(node));
    setError(node.error);
  }, [node.value, node.error, node.choices]);

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
        onValueChange={(name) => {
          setLocal(name);
          mutation.mutate(
            { op: "set_value", path, value: name },
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
          {node.choices.map(([name]) => (
            <SelectItem key={name} value={name}>{name}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      <FieldError message={error} path={path} />
    </FieldRow>
  );
}
