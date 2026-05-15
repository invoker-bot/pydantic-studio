/** Drop the dotted module prefix from a fully-qualified name.
 * "pydantic.HttpUrl" -> "HttpUrl"; "demo.Email" -> "Email".
 * Returns the fallback (or the original FQN) for inputs without dots.
 */
export function shortTypeName(fq: string, fallback?: string): string {
  return fq.split(".").pop() ?? fallback ?? fq;
}
