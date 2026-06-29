// Wrapper around POST /api/mutations from Phase 1. Each field
// component calls useApplyMutation() and invokes .mutate(...) with
// a typed Mutation. On success the tree is invalidated and refetched,
// triggering re-render of all subscribed components with the new
// server-side state.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormTreeSchema, type FormTree } from "@/api/schemas";

// Discriminated union mirroring spec §3.2. Phase 3 wires set_value
// (used by every primitive field). Container ops (add_item, etc.)
// land in Phase 4 when the corresponding components arrive.
export type Mutation =
  | { op: "set_value"; path: string; value: unknown }
  | { op: "add_item"; path: string }
  | { op: "remove_item"; path: string; index: number }
  | { op: "move_item"; path: string; from: number; to: number }
  | { op: "add_entry"; path: string; key: string }
  | { op: "remove_entry"; path: string; index: number }
  | { op: "rename_key"; path: string; index: number; new_key: string }
  | { op: "select_variant"; path: string; variant_index: number }
  | { op: "select_root_variant"; variant_id: string };

export interface MutationResponse {
  tree: FormTree;
  validation: { ok: boolean; errors: Array<{ path: string; message: string }> };
  mutation_result: { ok: boolean; errors: readonly string[] };
}

export async function applyMutation(mutation: Mutation): Promise<MutationResponse> {
  const response = await fetch("/api/mutations", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(mutation),
  });
  if (response.status === 400) {
    // Unknown op or malformed request (Phase 1 spec §5.2 contract).
    const body = await response.json();
    throw new Error(`Mutation rejected: ${body.detail ?? "bad request"}`);
  }
  if (!response.ok) {
    throw new Error(`POST /api/mutations failed: HTTP ${response.status}`);
  }
  const raw = await response.json();
  // The tree field always needs zod parsing; the rest is shape-stable
  // enough that we trust it. Future polish could add a full envelope
  // schema if we ever want stronger guarantees.
  const parsed: MutationResponse = {
    tree: FormTreeSchema.parse(raw.tree),
    validation: raw.validation,
    mutation_result: raw.mutation_result,
  };
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

export function useApplyMutation() {
  const queryClient = useQueryClient();
  return useMutation({
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
