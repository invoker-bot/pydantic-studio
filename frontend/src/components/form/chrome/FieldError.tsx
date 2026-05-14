// Red helper text under the input. Renders nothing when message is null.

export function FieldError({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="text-xs text-red-600">{message}</p>;
}
