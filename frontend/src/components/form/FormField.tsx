// Dispatcher: switch on node.kind to render the right field component.
// Every field renders inside an anchored wrapper so
// submit errors can scroll-to and highlight it; readonly paths render
// inside a disabled fieldset (native form disabling, no per-field code).

import type { FormNodeData } from "@/api/schemas";
import {
  fieldAnchorId,
  hasErrorAt,
  isReadonly,
  useFormFlags,
} from "@/components/form/errors";
import { AnyField } from "@/components/form/fields/AnyField";
import { BoolField } from "@/components/form/fields/BoolField";
import { BytesField } from "@/components/form/fields/BytesField";
import { DateField } from "@/components/form/fields/DateField";
import { DatetimeField } from "@/components/form/fields/DatetimeField";
import { DecimalField } from "@/components/form/fields/DecimalField";
import { EmailField } from "@/components/form/fields/EmailField";
import { EnumField } from "@/components/form/fields/EnumField";
import { FloatField } from "@/components/form/fields/FloatField";
import { GroupField } from "@/components/form/fields/GroupField";
import { IntField } from "@/components/form/fields/IntField";
import { IPAddressField } from "@/components/form/fields/IPAddressField";
import { IPNetworkField } from "@/components/form/fields/IPNetworkField";
import { LiteralField } from "@/components/form/fields/LiteralField";
import { MappingField } from "@/components/form/fields/MappingField";
import { PathField } from "@/components/form/fields/PathField";
import { PatternField } from "@/components/form/fields/PatternField";
import { SecretField } from "@/components/form/fields/SecretField";
import { SequenceField } from "@/components/form/fields/SequenceField";
import { StringField } from "@/components/form/fields/StringField";
import { TimedeltaField } from "@/components/form/fields/TimedeltaField";
import { TimeField } from "@/components/form/fields/TimeField";
import { UnionField } from "@/components/form/fields/UnionField";
import { URLField } from "@/components/form/fields/URLField";
import { UUIDField } from "@/components/form/fields/UUIDField";

type NodeOfKind<K extends string> = Extract<FormNodeData, { kind: K }>;

export function FormField({
  node,
  path,
}: { node: FormNodeData; path: string }) {
  const flags = useFormFlags();
  const body = dispatch(node, path);
  if (path === "") return body;
  const errored = hasErrorAt(flags, path);
  const readonly = isReadonly(flags, path);
  const inner = readonly ? (
    <fieldset disabled className="opacity-60">
      <legend className="text-[10px] uppercase tracking-wide text-zinc-400">
        read-only
      </legend>
      {body}
    </fieldset>
  ) : (
    body
  );
  return (
    <div
      id={fieldAnchorId(path)}
      data-field-path={path}
      className={
        errored
          ? "rounded-md ring-2 ring-red-400 ring-offset-2 ring-offset-white"
          : undefined
      }
    >
      {inner}
    </div>
  );
}

function dispatch(node: FormNodeData, path: string) {
  switch (node.kind) {
    case "string":
      return <StringField node={node as NodeOfKind<"string">} path={path} />;
    case "int":
      return <IntField node={node as NodeOfKind<"int">} path={path} />;
    case "float":
      return <FloatField node={node as NodeOfKind<"float">} path={path} />;
    case "bool":
      return <BoolField node={node as NodeOfKind<"bool">} path={path} />;
    case "date":
      return <DateField node={node as NodeOfKind<"date">} path={path} />;
    case "time":
      return <TimeField node={node as NodeOfKind<"time">} path={path} />;
    case "datetime":
      return <DatetimeField node={node as NodeOfKind<"datetime">} path={path} />;
    case "timedelta":
      return <TimedeltaField node={node as NodeOfKind<"timedelta">} path={path} />;
    case "decimal":
      return <DecimalField node={node as NodeOfKind<"decimal">} path={path} />;
    case "path":
      return <PathField node={node as NodeOfKind<"path">} path={path} />;
    case "url":
      return <URLField node={node as NodeOfKind<"url">} path={path} />;
    case "email":
      return <EmailField node={node as NodeOfKind<"email">} path={path} />;
    case "ip_address":
      return <IPAddressField node={node as NodeOfKind<"ip_address">} path={path} />;
    case "ip_network":
      return <IPNetworkField node={node as NodeOfKind<"ip_network">} path={path} />;
    case "uuid":
      return <UUIDField node={node as NodeOfKind<"uuid">} path={path} />;
    case "secret":
      return <SecretField node={node as NodeOfKind<"secret">} path={path} />;
    case "pattern":
      return <PatternField node={node as NodeOfKind<"pattern">} path={path} />;
    case "bytes":
      return <BytesField node={node as NodeOfKind<"bytes">} path={path} />;
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
    default: {
      const exhaustive: never = node;
      return exhaustive;
    }
  }
}
