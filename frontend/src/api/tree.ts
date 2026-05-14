// Shared fetch helper for GET /api/tree. Phase 3 will grow this
// module with typed parsers (zod) once the FormField dispatcher
// needs typed access to nodes.

export async function fetchTree(): Promise<unknown> {
  const response = await fetch("/api/tree");
  if (!response.ok) {
    throw new Error(`GET /api/tree failed: HTTP ${response.status}`);
  }
  return response.json();
}
