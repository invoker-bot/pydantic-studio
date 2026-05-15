// Wrappers around POST /api/submit and POST /api/cancel from spec §5.3.
//
// /api/submit:
//   200 { ok: true }                            -> server.submitted = true
//   400 { ok: false, errors: [{path, message}]} -> tree intact, show errors
// /api/cancel:
//   200 { ok: true }                            -> server.cancelled = true
//
// Both flip a flag on StudioServer; the run_html_app watchdog reads
// the flag and tears down uvicorn within ~1s. The SPA must therefore
// render its success/error state BEFORE the next fetch goes out, since
// the server may already be gone.

import { useMutation } from "@tanstack/react-query";

export interface SubmitError {
  path: string;
  message: string;
}

export interface SubmitResponse {
  ok: boolean;
  errors: SubmitError[];
}

export async function submitTree(): Promise<SubmitResponse> {
  const response = await fetch("/api/submit", { method: "POST" });
  if (response.status === 400) {
    const body = (await response.json()) as { ok?: boolean; errors?: SubmitError[] };
    return { ok: false, errors: body.errors ?? [] };
  }
  if (!response.ok) {
    throw new Error(`POST /api/submit failed: HTTP ${response.status}`);
  }
  return { ok: true, errors: [] };
}

export async function cancelEdit(): Promise<void> {
  const response = await fetch("/api/cancel", { method: "POST" });
  if (!response.ok) {
    throw new Error(`POST /api/cancel failed: HTTP ${response.status}`);
  }
}

export function useSubmitTree() {
  return useMutation({ mutationFn: submitTree });
}

export function useCancelEdit() {
  return useMutation({ mutationFn: cancelEdit });
}
