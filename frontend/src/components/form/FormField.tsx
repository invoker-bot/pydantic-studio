// Dispatcher: switch on node.kind to render the right component.
// Phase 3 covers 6 kinds (string/int/bool/enum/literal/group);
// Phase 4 adds sequence/mapping/union/any and the remaining 14 kinds
// from src/pydantic_studio/tree/nodes.py.
//
// Unknown kinds (anything not yet wired) render as a small "TODO"
// placeholder so the rest of the form still renders during incremental
// build-out.
//
// Note: FormNodeData's union includes a loose UnknownNodeSchema arm
// ({ kind: string; name: string; [extra: string]: unknown }) so the
// fetch tolerates Phase 4+ kinds the client doesn't yet understand.
// TypeScript can't narrow that arm away via ``case "string":`` alone
// (literal "string" is assignable to ``string``), so we extract a
// typed variant per arm via a generic helper before forwarding.

import type { FormNodeData } from "@/api/schemas";
import { BoolField } from "@/components/form/fields/BoolField";
import { EnumField } from "@/components/form/fields/EnumField";
import { GroupField } from "@/components/form/fields/GroupField";
import { IntField } from "@/components/form/fields/IntField";
import { LiteralField } from "@/components/form/fields/LiteralField";
import { StringField } from "@/components/form/fields/StringField";

type NodeOfKind<K extends string> = Extract<FormNodeData, { kind: K }>;

export function FormField({ node, path }: { node: FormNodeData; path: string }) {
  switch (node.kind) {
    case "string":
      return <StringField node={node as NodeOfKind<"string">} path={path} />;
    case "int":
      return <IntField node={node as NodeOfKind<"int">} path={path} />;
    case "bool":
      return <BoolField node={node as NodeOfKind<"bool">} path={path} />;
    case "enum":
      return <EnumField node={node as NodeOfKind<"enum">} path={path} />;
    case "literal":
      return <LiteralField node={node as NodeOfKind<"literal">} path={path} />;
    case "group":
      return <GroupField node={node as NodeOfKind<"group">} path={path} />;
    default:
      return (
        <div className="rounded border border-dashed border-zinc-300 p-2 text-xs text-zinc-500">
          <strong className="font-mono">{node.name}</strong>: kind <code className="font-mono">{node.kind}</code> not yet wired (Phase 4+).
        </div>
      );
  }
}
