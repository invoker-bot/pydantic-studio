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
import { z } from "zod";
import { studioUrl } from "@/api/base";

const SubmitErrorSchema = z.object({
  path: z.string(),
  message: z.string(),
}).strict();

const SubmitFailureResponseSchema = z.object({
  ok: z.literal(false),
  errors: z.array(SubmitErrorSchema),
}).strict();

const SubmitSuccessResponseSchema = z.object({
  ok: z.literal(true),
}).strict();

const CancelResponseSchema = z.object({
  ok: z.literal(true),
}).strict();

const ErrorDetailSchema = z.object({
  detail: z.string(),
}).strict();

export type SubmitError = z.infer<typeof SubmitErrorSchema>;

export type SubmitResponse =
  | {
      ok: true;
      errors: [];
    }
  | {
      ok: false;
      errors: SubmitError[];
    };

export async function submitTree(): Promise<SubmitResponse> {
  const response = await fetch(studioUrl("/api/submit"), { method: "POST" });
  if (response.status === 400) {
    try {
      return SubmitFailureResponseSchema.parse(await response.clone().json());
    } catch {
      throw new Error(await responseErrorMessage(response, "POST /api/submit"));
    }
  }
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "POST /api/submit"));
  }
  SubmitSuccessResponseSchema.parse(await response.json());
  return { ok: true, errors: [] };
}

export async function cancelEdit(): Promise<void> {
  const response = await fetch(studioUrl("/api/cancel"), { method: "POST" });
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response, "POST /api/cancel"));
  }
  CancelResponseSchema.parse(await response.json());
}

async function responseErrorMessage(
  response: Response,
  requestLabel: string,
): Promise<string> {
  const fallback = `${requestLabel} failed: HTTP ${response.status}`;
  try {
    const body = ErrorDetailSchema.parse(await response.json());
    return `${fallback}: ${body.detail}`;
  } catch {
    return fallback;
  }
}

export function useSubmitTree() {
  return useMutation({ mutationFn: submitTree });
}

export function useCancelEdit() {
  return useMutation({ mutationFn: cancelEdit });
}
