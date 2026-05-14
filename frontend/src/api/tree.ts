import { FormTreeSchema, type FormTree } from "@/api/schemas";

export async function fetchTree(): Promise<FormTree> {
  const response = await fetch("/api/tree");
  if (!response.ok) {
    throw new Error(`GET /api/tree failed: HTTP ${response.status}`);
  }
  const raw = await response.json();
  return FormTreeSchema.parse(raw);
}
