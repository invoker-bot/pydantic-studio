// Wrapper around POST /api/mutations from Phase 1. Each field
// component calls useApplyMutation() and invokes .mutate(...) with
// a typed Mutation. On success the tree is invalidated and refetched,
// triggering re-render of all subscribed components with the new
// server-side state.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { studioUrl } from "@/api/base";
import { FormTreeSchema, type FormTree } from "@/api/schemas";

export const APPLY_MUTATION_KEY = ["applyMutation"] as const;

const MutationErrorResponseSchema = z.object({
  detail: z.string(),
}).strict();

const ValidationErrorSchema = z.object({
  path: z.string(),
  message: z.string(),
}).strict();

const ValidationEnvelopeSchema = z.object({
  ok: z.boolean(),
  errors: z.array(ValidationErrorSchema),
}).strict();

const MutationResultSchema = z.object({
  ok: z.boolean(),
  errors: z.array(z.string()),
}).strict();

const MutationResponseSchema = z.object({
  tree: FormTreeSchema,
  validation: ValidationEnvelopeSchema,
  mutation_result: MutationResultSchema,
}).strict();

// Discriminated union for the JSON API mutation contract. Field edits,
// containers, variants, and history controls all share this server-
// authoritative path.
export type Mutation =
  | { op: "set_value"; path: string; value: unknown }
  | { op: "undo" }
  | { op: "redo" }
  | { op: "add_item"; path: string }
  | { op: "remove_item"; path: string; index: number }
  | { op: "move_item"; path: string; from: number; to: number }
  | { op: "add_entry"; path: string; key: string }
  | { op: "remove_entry"; path: string; index: number }
  | { op: "rename_key"; path: string; index: number; new_key: string }
  | { op: "select_variant"; path: string; variant_index: number }
  | { op: "select_root_variant"; variant_id: string };

export type MutationResponse = z.infer<typeof MutationResponseSchema>;

export async function applyMutation(mutation: Mutation): Promise<MutationResponse> {
  const response = await fetch(studioUrl("/api/mutations"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(mutation),
  });
  if (response.status === 400) {
    // Unknown op or malformed request (Phase 1 spec §5.2 contract).
    throw new Error(`Mutation rejected: ${await responseErrorMessage(response)}`);
  }
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  const raw = await response.json();
  const parsed = MutationResponseSchema.parse(raw);
  // The server returns 200 even when the mutation is REJECTED by
  // validate-first (the tree is intact; mutation_result.ok=false flags
  // the rejection). Surface that as a thrown Error so useMutation's
  // onError fires and the field component can show the error - rather
  // than leaving the per-field onError handlers as dead code.
  if (!parsed.mutation_result.ok) {
    const msg = parsed.mutation_result.errors.join("; ") || "mutation rejected";
    const err = new Error(msg);
    // Stash the tree on the error so onError handlers in TanStack
    // Query's onSuccess - which won't fire because we threw - can
    // still update the cache. (See useApplyMutation below.)
    (err as Error & { tree?: FormTree }).tree = parsed.tree;
    throw err;
  }
  return parsed;
}

async function responseErrorMessage(response: Response): Promise<string> {
  const fallback = `POST /api/mutations failed: HTTP ${response.status}`;
  try {
    const body = MutationErrorResponseSchema.parse(await response.json());
    return `${fallback}: ${body.detail}`;
  } catch {
    return fallback;
  }
}

export function useApplyMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: APPLY_MUTATION_KEY,
    mutationFn: applyMutation,
    onSuccess: (response) => {
      // Server-authoritative: replace the cached tree with what the
      // server returned. Every component using useQuery(['tree']) will
      // re-render with the new state on the next React tick.
      queryClient.setQueryData(["tree"], response.tree);
    },
    onError: (error) => {
      // applyMutation throws when mutation_result.ok=false, but the
      // server still returns the (un-mutated) tree. Update the cache
      // anyway so node.error stamps surface via useEffect re-sync.
      const errWithTree = error as Error & { tree?: FormTree };
      if (errWithTree.tree) {
        queryClient.setQueryData(["tree"], errWithTree.tree);
      }
    },
  });
}
