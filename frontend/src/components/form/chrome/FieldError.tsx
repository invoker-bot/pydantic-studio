// Red helper text under the input. Renders nothing when message is null.

export function fieldErrorId(path: string): string {
  return `field-${path}-error`;
}

export function fieldErrorControlProps(message: string | null, path: string) {
  if (!message) {
    return {
      "aria-describedby": undefined,
      "aria-invalid": undefined,
    };
  }
  return {
    "aria-describedby": fieldErrorId(path),
    "aria-invalid": true,
  };
}

export function FieldError({
  message,
  path,
}: { message: string | null; path?: string }) {
  if (!message) return null;
  return (
    <p
      id={path ? fieldErrorId(path) : undefined}
      className="text-xs text-red-600"
      role="alert"
      aria-atomic="true"
    >
      {message}
    </p>
  );
}
