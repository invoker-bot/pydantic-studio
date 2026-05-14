// zod schemas mirroring the Phase 1 JSON API contract (see spec §5.1).
// Each schema corresponds to one FormNode subclass in
// src/pydantic_studio/tree/nodes.py. Phase 3 covers the 5 primitive
// kinds the dispatcher handles (string/int/bool/enum/literal) plus
// group (the root + nested groups). Phase 4 adds the dynamic kinds
// (sequence/mapping/union/any).

import { z } from "zod";

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
  BoolNodeSchema,
  EnumNodeSchema,
  LiteralNodeSchema,
  GroupNodeSchema,
  UnknownNodeSchema,
]);

export type FormNodeData =
  | z.infer<typeof StringNodeSchema>
  | z.infer<typeof IntNodeSchema>
  | z.infer<typeof BoolNodeSchema>
  | z.infer<typeof EnumNodeSchema>
  | z.infer<typeof LiteralNodeSchema>
  | GroupNodeData
  | { kind: string; name: string; [extra: string]: unknown };

export const FormTreeSchema = z.object({
  schema_name: z.string(),
  root: GroupNodeSchema,
  unsaved_count: z.number(),
}).passthrough();   // tolerate extra top-level fields (created_at, cursor, etc.)

export type FormTree = z.infer<typeof FormTreeSchema>;
