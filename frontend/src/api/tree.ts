import { z } from "zod";
import { studioUrl } from "@/api/base";
import { FormTreeSchema, type FormTree } from "@/api/schemas";

const ErrorDetailSchema = z.object({
  detail: z.string(),
}).strict();

export async function fetchTree(): Promise<FormTree> {
  const response = await fetch(studioUrl("/api/tree"));
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  const raw = await response.json();
  return FormTreeSchema.parse(raw);
}

async function responseErrorMessage(response: Response): Promise<string> {
  const fallback = `GET /api/tree failed: HTTP ${response.status}`;
  try {
    const body = ErrorDetailSchema.parse(await response.json());
    return `${fallback}: ${body.detail}`;
  } catch {
    return fallback;
  }
}
