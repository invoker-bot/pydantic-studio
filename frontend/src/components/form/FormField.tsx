// Dispatcher: switch on node.kind to render the right component.
// Phase 3 covered string/int/bool/enum/literal/group. Phase 4 adds
// sequence/mapping/union/any.

import type { FormNodeData } from "@/api/schemas";
import { AnyField } from "@/components/form/fields/AnyField";
import { BoolField } from "@/components/form/fields/BoolField";
import { DecimalField } from "@/components/form/fields/DecimalField";
import { EmailField } from "@/components/form/fields/EmailField";
import { EnumField } from "@/components/form/fields/EnumField";
import { FloatField } from "@/components/form/fields/FloatField";
import { GroupField } from "@/components/form/fields/GroupField";
import { IntField } from "@/components/form/fields/IntField";
import { LiteralField } from "@/components/form/fields/LiteralField";
import { MappingField } from "@/components/form/fields/MappingField";
import { PathField } from "@/components/form/fields/PathField";
import { SequenceField } from "@/components/form/fields/SequenceField";
import { StringField } from "@/components/form/fields/StringField";
import { UnionField } from "@/components/form/fields/UnionField";
import { URLField } from "@/components/form/fields/URLField";

type NodeOfKind<K extends string> = Extract<FormNodeData, { kind: K }>;

export function FormField({
  node,
  path,
}: { node: FormNodeData; path: string }) {
  switch (node.kind) {
    case "string":
      return <StringField node={node as NodeOfKind<"string">} path={path} />;
    case "int":
      return <IntField node={node as NodeOfKind<"int">} path={path} />;
    case "float":
      return <FloatField node={node as NodeOfKind<"float">} path={path} />;
    case "bool":
      return <BoolField node={node as NodeOfKind<"bool">} path={path} />;
    case "decimal":
      return <DecimalField node={node as NodeOfKind<"decimal">} path={path} />;
    case "path":
      return <PathField node={node as NodeOfKind<"path">} path={path} />;
    case "url":
      return <URLField node={node as NodeOfKind<"url">} path={path} />;
    case "email":
      return <EmailField node={node as NodeOfKind<"email">} path={path} />;
    case "enum":
      return <EnumField node={node as NodeOfKind<"enum">} path={path} />;
    case "literal":
      return <LiteralField node={node as NodeOfKind<"literal">} path={path} />;
    case "group":
      return <GroupField node={node as NodeOfKind<"group">} path={path} />;
    case "sequence":
      return <SequenceField node={node as NodeOfKind<"sequence">} path={path} />;
    case "mapping":
      return <MappingField node={node as NodeOfKind<"mapping">} path={path} />;
    case "union":
      return <UnionField node={node as NodeOfKind<"union">} path={path} />;
    case "any":
      return <AnyField node={node as NodeOfKind<"any">} path={path} />;
    default:
      return (
        <div className="rounded border border-dashed border-zinc-300 p-2 text-xs text-zinc-500">
          <strong className="font-mono">{node.name}</strong>: kind{" "}
          <code className="font-mono">{node.kind}</code> not yet wired
          (Phase 5+).
        </div>
      );
  }
}
