declare global {
  interface Window {
    __PYDANTIC_STUDIO__?: {
      basePath?: string;
    };
  }
}

function normalizedBasePath(): string {
  const raw = window.__PYDANTIC_STUDIO__?.basePath ?? "";
  const trimmed = raw.trim();
  if (trimmed === "" || trimmed === "/") {
    return "";
  }
  return `/${trimmed.replace(/^\/+|\/+$/g, "")}`;
}

export function studioUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBasePath()}${normalizedPath}`;
}
