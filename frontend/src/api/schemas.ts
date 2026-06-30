// zod schemas mirroring the Phase 1 JSON API contract (see spec §5.1).
// Each schema corresponds to one FormNode subclass in
// src/pydantic_studio/tree/nodes.py. Phase 3 covers the 5 primitive
// kinds the dispatcher handles (string/int/bool/enum/literal) plus
// group (the root + nested groups). Phase 4 adds the dynamic kinds
// (sequence/mapping/union/any).

import { z } from "zod";

export const VariantOptionSchema = z.object({
  id: z.string(),
  label: z.string(),
  description: z.string().nullable(),
  model_type_name: z.string(),
});

export const VariantStateSchema = z.object({
  options: z.array(VariantOptionSchema),
  selected_id: z.string(),
  discriminator: z.string().nullable(),
  persistence: z.enum(["metadata", "inline_discriminator"]),
});

export type VariantStateData = z.infer<typeof VariantStateSchema>;

// Common base fields on every FormNode.
const NodeBase = z.object({
  name: z.string(),
  description: z.string().nullable(),
  required: z.boolean(),
  error: z.string().nullable(),
});

export const StringNodeSchema = NodeBase.extend({
  kind: z.literal("string"),
  value: z.string().nullable(),
  default: z.string().nullable(),
  min_length: z.number().nullable(),
  max_length: z.number().nullable(),
  pattern: z.string().nullable(),
  multiline: z.boolean(),
  secret: z.boolean(),
});

export const IntNodeSchema = NodeBase.extend({
  kind: z.literal("int"),
  value: z.number().nullable(),
  default: z.number().nullable(),
  ge: z.number().nullable(),
  le: z.number().nullable(),
  gt: z.number().nullable(),
  lt: z.number().nullable(),
  multiple_of: z.number().nullable(),
});

export const BoolNodeSchema = NodeBase.extend({
  kind: z.literal("bool"),
  value: z.boolean().nullable(),
  default: z.boolean().nullable(),
});

export const EnumNodeSchema = NodeBase.extend({
  kind: z.literal("enum"),
  value: z.unknown(),       // EnumNode.value is the enum member instance; opaque to client
  default: z.unknown(),
  enum_class_name: z.string(),
  choices: z.array(z.tuple([z.string(), z.unknown()])),  // [(name, member), ...]
});

export const LiteralNodeSchema = NodeBase.extend({
  kind: z.literal("literal"),
  value: z.unknown(),
  default: z.unknown(),
  choices: z.array(z.unknown()),
});

export const FloatNodeSchema = NodeBase.extend({
  kind: z.literal("float"),
  value: z.number().nullable(),
  default: z.number().nullable(),
  ge: z.number().nullable(),
  le: z.number().nullable(),
  gt: z.number().nullable(),
  lt: z.number().nullable(),
  multiple_of: z.number().nullable(),
  allow_inf_nan: z.boolean(),
});

export const DecimalNodeSchema = NodeBase.extend({
  kind: z.literal("decimal"),
  // Decimal round-trips as a string via Pydantic JSON; preserves
  // precision (1e-30, etc.) that z.number() would lose.
  value: z.string().nullable(),
  default: z.string().nullable(),
  max_digits: z.number().nullable(),
  decimal_places: z.number().nullable(),
  ge: z.string().nullable(),
  le: z.string().nullable(),
  gt: z.string().nullable(),
  lt: z.string().nullable(),
});

export const DatetimeNodeSchema = NodeBase.extend({
  kind: z.literal("datetime"),
  // ISO 8601 datetime: "2025-01-15T10:30:00" or with tz "2025-01-15T10:30:00+00:00"
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const DateNodeSchema = NodeBase.extend({
  kind: z.literal("date"),
  // ISO 8601 date: "2025-01-15"
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const TimeNodeSchema = NodeBase.extend({
  kind: z.literal("time"),
  // ISO 8601 time: "14:30:00" or "14:30"
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const TimedeltaNodeSchema = NodeBase.extend({
  kind: z.literal("timedelta"),
  // ISO 8601 duration: "PT1H30M", "P1DT2H", etc.
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const IPAddressNodeSchema = NodeBase.extend({
  kind: z.literal("ip_address"),
  value: z.string().nullable(),
  default: z.string().nullable(),
  version: z.union([z.literal(4), z.literal(6)]),
});

export const IPNetworkNodeSchema = NodeBase.extend({
  kind: z.literal("ip_network"),
  value: z.string().nullable(),
  default: z.string().nullable(),
  version: z.union([z.literal(4), z.literal(6)]),
});

export const URLNodeSchema = NodeBase.extend({
  kind: z.literal("url"),
  value: z.string().nullable(),
  default: z.string().nullable(),
  // Fully qualified name of the URL type, e.g. "pydantic.HttpUrl".
  target_type_name: z.string(),
});

export const EmailNodeSchema = NodeBase.extend({
  kind: z.literal("email"),
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const PathNodeSchema = NodeBase.extend({
  kind: z.literal("path"),
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const UUIDNodeSchema = NodeBase.extend({
  kind: z.literal("uuid"),
  // Pydantic JSON-dumps UUID as string.
  value: z.string().nullable(),
  default: z.string().nullable(),
});

export const SecretNodeSchema = NodeBase.extend({
  kind: z.literal("secret"),
  // SecretStr value is a plain str; SecretBytes value is bytes that
  // Pydantic JSON-encodes as a UTF-8 string. Both arrive as str on
  // the wire; secret_kind discriminates how to render and how the
  // backend dispatcher's _maybe_coerce_typed_value re-encodes.
  value: z.string().nullable(),
  default: z.string().nullable(),
  secret_kind: z.union([z.literal("str"), z.literal("bytes")]),
});

export const PatternNodeSchema = NodeBase.extend({
  kind: z.literal("pattern"),
  // Regex source string (the pattern itself).
  value: z.string().nullable(),
  default: z.string().nullable(),
  // Python re flag bitmask; renderer derives single-char chips
  // (i/m/s/x/a/u) read-only for Phase 5 (no in-UI editing yet).
  flags: z.number(),
});

export const BytesNodeSchema = NodeBase.extend({
  kind: z.literal("bytes"),
  // BytesNode._serialize_value emits hex (lossless on round-trip).
  value: z.string().nullable(),
  default: z.string().nullable(),
});

// GroupNode is recursive — define it before adding it to the union.
export interface GroupNodeData {
  kind: "group";
  name: string;
  description: string | null;
  required: boolean;
  error: string | null;
  schema_class: string;
  fields: FormNodeData[];
}

export const GroupNodeSchema: z.ZodType<GroupNodeData> = z.lazy(() =>
  NodeBase.extend({
    kind: z.literal("group"),
    schema_class: z.string(),
    fields: z.array(FormNodeSchema),
  }),
);

// SequenceNode: list[T] / set[T] / tuple[T,...]. items is a recursive
// list of FormNodes (each item gets its own sub-tree).
export interface SequenceNodeData {
  kind: "sequence";
  name: string;
  description: string | null;
  required: boolean;
  error: string | null;
  origin: "list" | "set" | "tuple" | "tuple_fixed";
  items: FormNodeData[];
  item_type_name: string | null;        // null for tuple_fixed; FQ name otherwise
  slot_type_names: string[] | null;     // populated for tuple_fixed
  min_length: number | null;
  max_length: number | null;
}

export const SequenceNodeSchema: z.ZodType<SequenceNodeData> = z.lazy(() =>
  NodeBase.extend({
    kind: z.literal("sequence"),
    origin: z.enum(["list", "set", "tuple", "tuple_fixed"]),
    items: z.array(FormNodeSchema),
    item_type_name: z.string().nullable(),
    slot_type_names: z.array(z.string()).nullable(),
    min_length: z.number().nullable(),
    max_length: z.number().nullable(),
  }),
);

// MappingNode: dict[K, V]. entries is a list of (key_node, value_node)
// tuples - 2-element arrays in JSON. Backend uses index-based removal
// and rename so the client doesn't have to worry about key uniqueness.
export interface MappingNodeData {
  kind: "mapping";
  name: string;
  description: string | null;
  required: boolean;
  error: string | null;
  entries: Array<[FormNodeData, FormNodeData]>;
  key_type_name: string;
  value_type_name: string;
  min_length: number | null;
  max_length: number | null;
}

export const MappingNodeSchema: z.ZodType<MappingNodeData> = z.lazy(() =>
  NodeBase.extend({
    kind: z.literal("mapping"),
    entries: z.array(z.tuple([FormNodeSchema, FormNodeSchema])),
    key_type_name: z.string(),
    value_type_name: z.string(),
    min_length: z.number().nullable(),
    max_length: z.number().nullable(),
  }),
);

// UnionNode: T1 | T2 | ... (with optional discriminator). selected is the
// active variant node (matching one of variant_type_names). variant_index
// is the index into variant_type_names.
export interface UnionNodeData {
  kind: "union";
  name: string;
  description: string | null;
  required: boolean;
  error: string | null;
  variant_type_names: string[];
  selected_index: number | null;
  selected: FormNodeData | null;
}

export const UnionNodeSchema: z.ZodType<UnionNodeData> = z.lazy(() =>
  NodeBase.extend({
    kind: z.literal("union"),
    variant_type_names: z.array(z.string()),
    selected_index: z.number().nullable(),
    selected: FormNodeSchema.nullable(),
  }),
);

// AnyValueNode: typing.Any. mode auto-syncs to value's runtime shape
// (null/str/int/float/bool/list/dict). The wire value is the raw JSON.
export const AnyValueNodeSchema = NodeBase.extend({
  kind: z.literal("any"),
  mode: z.enum(["null", "str", "int", "float", "bool", "list", "dict"]),
  value: z.unknown(),
});

// Phase 3 dispatcher covers these 6 kinds. Phase 4 adds sequence,
// mapping, union, any (and the rest of the spec's 20+ node kinds).
// For now, unknown kinds parse loosely as a passthrough so the
// fetch doesn't reject the whole tree on a node Phase 3 doesn't
// understand yet (e.g., a sequence in the test schema).
//
// We use ``z.union`` (not ``z.discriminatedUnion``) for two reasons:
//   1. GroupNodeSchema is recursive via z.lazy, so its TS type is the
//      wide ``ZodType<GroupNodeData>`` — not the narrower
//      ``ZodDiscriminatedUnionOption<"kind">`` that discriminatedUnion
//      requires for inference.
//   2. We need an UnknownNodeSchema fallback whose ``kind`` is
//      ``z.string()`` (not a literal), which discriminatedUnion also
//      rejects. Plain ``z.union`` accepts both.
// Runtime validation is identical; the only loss is a marginal speedup
// from discriminator-based dispatch, which doesn't matter at our scale.
const UnknownNodeSchema = z.object({
  kind: z.string(),
  name: z.string(),
}).passthrough();

export const FormNodeSchema: z.ZodType<FormNodeData> = z.union([
  StringNodeSchema,
  IntNodeSchema,
  FloatNodeSchema,
  BoolNodeSchema,
  DecimalNodeSchema,
  DatetimeNodeSchema,
  DateNodeSchema,
  TimeNodeSchema,
  TimedeltaNodeSchema,
  IPAddressNodeSchema,
  IPNetworkNodeSchema,
  URLNodeSchema,
  EmailNodeSchema,
  PathNodeSchema,
  UUIDNodeSchema,
  SecretNodeSchema,
  PatternNodeSchema,
  BytesNodeSchema,
  EnumNodeSchema,
  LiteralNodeSchema,
  GroupNodeSchema,
  SequenceNodeSchema,
  MappingNodeSchema,
  UnionNodeSchema,
  AnyValueNodeSchema,
  UnknownNodeSchema,
]);

export type FormNodeData =
  | z.infer<typeof StringNodeSchema>
  | z.infer<typeof IntNodeSchema>
  | z.infer<typeof FloatNodeSchema>
  | z.infer<typeof BoolNodeSchema>
  | z.infer<typeof DecimalNodeSchema>
  | z.infer<typeof DatetimeNodeSchema>
  | z.infer<typeof DateNodeSchema>
  | z.infer<typeof TimeNodeSchema>
  | z.infer<typeof TimedeltaNodeSchema>
  | z.infer<typeof IPAddressNodeSchema>
  | z.infer<typeof IPNetworkNodeSchema>
  | z.infer<typeof URLNodeSchema>
  | z.infer<typeof EmailNodeSchema>
  | z.infer<typeof PathNodeSchema>
  | z.infer<typeof UUIDNodeSchema>
  | z.infer<typeof SecretNodeSchema>
  | z.infer<typeof PatternNodeSchema>
  | z.infer<typeof BytesNodeSchema>
  | z.infer<typeof EnumNodeSchema>
  | z.infer<typeof LiteralNodeSchema>
  | GroupNodeData
  | SequenceNodeData
  | MappingNodeData
  | UnionNodeData
  | z.infer<typeof AnyValueNodeSchema>
  | { kind: string; name: string; [extra: string]: unknown };

export const FormTreeSchema = z.object({
  schema_name: z.string(),
  root: GroupNodeSchema,
  variant: VariantStateSchema.nullable(),
  unsaved_count: z.number(),
  preview: z.string(),
  readonly_paths: z.array(z.string()).default([]),
}).passthrough();   // tolerate extra top-level fields (created_at, cursor, etc.)

export type FormTree = z.infer<typeof FormTreeSchema>;
