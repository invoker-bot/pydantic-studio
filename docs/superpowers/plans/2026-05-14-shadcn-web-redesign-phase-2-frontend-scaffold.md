# Shadcn Web Redesign — Phase 2: Frontend Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Vite + React + TypeScript + Tailwind CSS v4 + shadcn-CLI toolchain under `frontend/`, build an empty SPA that fetches `/api/tree` (Phase 1's endpoint) via TanStack Query, dump the JSON in the browser, commit the bundled output under `src/pydantic_studio/renderers/html/static/dist/`, and prove a TestClient request to `/static/dist/index.html` returns the built HTML.

**Architecture:** A new `frontend/` directory at the repo root holds the Node project (source, lockfile, configs) but does NOT ship in the wheel. Vite builds output to `src/pydantic_studio/renderers/html/static/dist/` (committed), which FastAPI already serves via its existing static mount — no new routes needed in Phase 2. Phase 6's "delete HTMX templates and swap `/` to serve the SPA" lands later; Phase 2 just proves the React app can be built and loaded.

**Tech Stack:** Node 20+ (24 available locally), pnpm 9 (installed via corepack), Vite 5, React 18, TypeScript 5 strict, Tailwind CSS v4 (via `@tailwindcss/vite`), TanStack Query 5. No shadcn primitives are *used* yet — Phase 2 only sets up the `components.json` so Phase 3 can `pnpm dlx shadcn@latest add <name>` on demand.

**Spec:** `docs/superpowers/specs/2026-05-14-shadcn-web-redesign-design.md`. This plan implements only §8 Phase 2 of that spec.

**Predecessor:** Phase 1 (`docs/superpowers/plans/2026-05-14-shadcn-web-redesign-phase-1-json-api.md`) shipped the JSON API the SPA consumes. Merged at `b1c0ff8`; tagged `v0.2.0-phase-1`.

---

## File Structure

**Create at repo root:**
- `frontend/package.json` — npm metadata + scripts + pinned dep versions. ~30 lines.
- `frontend/pnpm-lock.yaml` — pnpm's lockfile. Generated; commit.
- `frontend/tsconfig.json` — TypeScript strict config for the SPA. ~30 lines.
- `frontend/tsconfig.node.json` — TypeScript config for Vite-config-time code. ~15 lines.
- `frontend/vite.config.ts` — Vite + React plugin + Tailwind plugin + output dir + dev proxy. ~30 lines.
- `frontend/index.html` — Vite HTML entry; mounts React. ~15 lines.
- `frontend/components.json` — shadcn CLI config (so Phase 3 can `add button`). ~15 lines.
- `frontend/.gitignore` — `node_modules/`, `.vite/`. ~5 lines.
- `frontend/scripts/build.sh` — wrapper around `pnpm install --frozen-lockfile && pnpm build`. ~10 lines.
- `frontend/src/main.tsx` — React entry, mounts `<App>` inside `<QueryClientProvider>`. ~20 lines.
- `frontend/src/App.tsx` — calls `useQuery(['tree'], fetchTree)`, renders JSON in a `<pre>`. ~25 lines.
- `frontend/src/api/tree.ts` — `fetchTree()` helper. ~10 lines.
- `frontend/src/lib/utils.ts` — shadcn-CLI-expected `cn()` utility. ~8 lines.
- `frontend/src/styles/globals.css` — `@import "tailwindcss";`. 1 line.

**Create (built artifact, committed):**
- `src/pydantic_studio/renderers/html/static/dist/index.html` — Vite's processed HTML.
- `src/pydantic_studio/renderers/html/static/dist/assets/*.js` — bundled React + app code (hashed filename).
- `src/pydantic_studio/renderers/html/static/dist/assets/*.css` — Tailwind output (hashed filename).

**Create:**
- `tests/unit/test_html_static_bundle.py` — TestClient smoke for `/static/dist/index.html`. ~40 lines.

**Modify:**
- `.gitignore` — change root pattern `dist/` to `/dist/` so it stops matching `static/dist/`; matches Python build's root `dist/` unchanged. Also add `frontend/node_modules/` (defensive — the frontend's own `.gitignore` is the primary line of defense).
- `pyproject.toml` — under `[tool.uv.build]`, declare `data = [...]` (or similar; verify the exact key on uv_build) so the wheel includes `src/pydantic_studio/renderers/html/static/dist/**`. The implementer verifies the correct key via uv_build docs in Task 8.

**Do NOT touch:**
- `src/pydantic_studio/renderers/html/routes.py` — Phase 5/6 swaps `/` to the SPA; Phase 2 reaches the SPA via the existing `/static/` mount.
- `src/pydantic_studio/renderers/html/server.py` — no change. Existing `_mount_static` already mounts the whole `static/` tree.
- `src/pydantic_studio/renderers/html/templates/` — Phase 6 deletes these.
- Anything under `tests/unit/test_html_server.py` or `tests/unit/test_html_api_routes.py` — Phase 1 owns those.

---

## Prerequisites

Before starting Task 1, confirm Node + corepack are available:

```bash
node --version    # expect v20 or later (v24.15.0 on the host as of plan-time)
corepack --version  # expect 0.20 or later
```

`pnpm` does NOT need to be pre-installed — Task 1 installs it via corepack.

If `node` is missing entirely, escalate (`NEEDS_CONTEXT`) — installing Node is out of plan scope.

---

## Task 1: Initialize frontend/ with pnpm + package.json

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/.gitignore`

- [ ] **Step 1: Activate pnpm via corepack**

```bash
corepack enable
corepack prepare pnpm@9 --activate
pnpm --version    # expect 9.x
```

Expected: pnpm version is reported (e.g., `9.15.0`). If corepack refuses (rare), fall back to `npm install -g pnpm@9`.

- [ ] **Step 2: Create the frontend directory and package.json**

```bash
mkdir frontend
mkdir -p frontend/src/api frontend/src/lib frontend/src/styles frontend/scripts
```

Then create `frontend/package.json`:

```json
{
  "name": "pydantic-studio-frontend",
  "private": true,
  "version": "0.2.0-phase-2",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.59.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@types/node": "^22.0.0",
    "@types/react": "^18.3.10",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.2",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.6.0",
    "vite": "^5.4.0"
  },
  "packageManager": "pnpm@9.15.0"
}
```

- [ ] **Step 3: Create frontend/.gitignore**

```gitignore
# pnpm + Vite + TypeScript artifacts
node_modules/
.vite/
.cache/
*.tsbuildinfo
```

- [ ] **Step 4: Run pnpm install to generate the lockfile**

```bash
cd frontend
pnpm install
```

Expected: `pnpm-lock.yaml` is created; `node_modules/` populates; no errors. On Windows the first install may take 1–2 minutes (pnpm content-addressable store warming).

- [ ] **Step 5: Commit**

```bash
cd ..    # back to repo root
git add frontend/package.json frontend/pnpm-lock.yaml frontend/.gitignore
git commit -m "feat(frontend): scaffold pnpm-managed Vite/React/TS project

Phase 2 of the shadcn web redesign starts the React SPA toolchain.
This commit only adds the package.json + lockfile; subsequent tasks
add Vite/TS/Tailwind configs and the App component.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

---

## Task 2: Wire TypeScript configs (strict mode)

**Files:**
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`

- [ ] **Step 1: Write tsconfig.json (project config)**

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 2: Write tsconfig.node.json (for vite.config.ts itself)**

`frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 3: Verify TypeScript can parse the configs**

```bash
cd frontend
pnpm exec tsc -b --dry
```

Expected: no errors. (No source files yet; tsc just validates the configs are parseable. If you get an error about missing `src/` files, that's fine — Task 6 creates them.)

If `tsc` complains that `noEmit` and `composite` conflict, that's expected for the `--build` dry-run flow but doesn't block; just confirm the config files themselves are valid JSON.

- [ ] **Step 4: Commit**

```bash
git add frontend/tsconfig.json frontend/tsconfig.node.json
git commit -m "feat(frontend): TypeScript strict config + path alias

@/* maps to ./src/* so future imports read @/components/ui/button.
Composite project: tsconfig.node.json handles vite.config.ts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

---

## Task 3: Wire Vite config (React + Tailwind + output dir + dev proxy)

**Files:**
- Create: `frontend/vite.config.ts`

- [ ] **Step 1: Write vite.config.ts**

`frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Vite builds output INTO the Python package's static/ tree so the
// existing StudioServer._mount_static at "/static" serves it without
// any new route. Phase 6 will swap "/" to serve dist/index.html
// directly; Phase 2 reaches the SPA via /static/dist/index.html.
const PYTHON_DIST = path.resolve(
  __dirname,
  "../src/pydantic_studio/renderers/html/static/dist",
);

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: PYTHON_DIST,
    emptyOutDir: true,
  },
  server: {
    proxy: {
      // pnpm dev proxies /api/* to the local FastAPI process so the
      // dev SPA can hit the real backend during development.
      "/api": "http://127.0.0.1:8000",
    },
  },
});
```

- [ ] **Step 2: Verify the config loads (without source files yet)**

```bash
cd frontend
pnpm exec vite --version
```

Expected: Vite version number. No "config error" output. (Vite doesn't load `vite.config.ts` for `--version`, but this confirms the binary works.)

- [ ] **Step 3: Commit**

```bash
git add frontend/vite.config.ts
git commit -m "feat(frontend): Vite config - React + Tailwind + dist into Python package

Vite output lands at src/pydantic_studio/renderers/html/static/dist/
so the existing StudioServer static mount serves it without new
routes. Dev-mode proxy forwards /api to localhost:8000 for HMR
against the real FastAPI backend.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

---

## Task 4: Tailwind CSS v4 setup

**Files:**
- Create: `frontend/src/styles/globals.css`

- [ ] **Step 1: Write globals.css**

Tailwind v4 needs only a single `@import` directive — the `@tailwindcss/vite` plugin (registered in Task 3) discovers source files automatically and emits the bundled CSS.

`frontend/src/styles/globals.css`:

```css
@import "tailwindcss";
```

That's it. No `tailwind.config.ts` is required for v4 unless you're customizing the theme (we'll add one in Phase 5 when light/dark themes ship).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/styles/globals.css
git commit -m "feat(frontend): Tailwind CSS v4 entry stylesheet

Single @import is enough for v4 + the @tailwindcss/vite plugin.
A tailwind.config.ts lands in Phase 5 when theming is needed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

---

## Task 5: Wire shadcn CLI config (no primitives yet)

**Files:**
- Create: `frontend/components.json`
- Create: `frontend/src/lib/utils.ts`

- [ ] **Step 1: Write components.json**

The shadcn CLI reads `components.json` to know where to drop primitive source files and what aliases to use. Setting it up now means Phase 3 just runs `pnpm dlx shadcn@latest add button` and the file lands at `frontend/src/components/ui/button.tsx`.

`frontend/components.json`:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/styles/globals.css",
    "baseColor": "zinc",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

`baseColor: "zinc"` matches the spec's neutral-palette intent from §6 mockups; can be swapped later via the CLI.
`tailwind.config: ""` is correct for Tailwind v4 (no JS config file exists; v4 reads CSS theme directives).

- [ ] **Step 2: Write the cn() utility shadcn primitives expect**

Every shadcn primitive imports `cn` from `@/lib/utils` for class-name merging. Without it, future `pnpm dlx shadcn add ...` invocations will create broken components.

`frontend/src/lib/utils.ts`:

```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 3: Add the cn() dependencies**

```bash
cd frontend
pnpm add clsx tailwind-merge
```

Expected: `package.json` `dependencies` grows by two; `pnpm-lock.yaml` updated.

- [ ] **Step 4: Verify TypeScript compiles utils.ts**

```bash
pnpm exec tsc --noEmit
```

Expected: no errors (the rest of `src/` is empty; only `utils.ts` is checked).

- [ ] **Step 5: Commit**

```bash
git add frontend/components.json frontend/src/lib/utils.ts \
  frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat(frontend): shadcn CLI config + cn() utility

components.json points the shadcn CLI at zinc base color, CSS
variables on, and @/components/ui as the install target. The cn()
utility (clsx + tailwind-merge) is the class-name merger shadcn
primitives import from @/lib/utils. No primitives installed yet;
Phase 3 will run pnpm dlx shadcn@latest add <name> per primitive.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

---

## Task 6: App scaffold — index.html + main.tsx + App.tsx + fetchTree

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/tree.ts`

- [ ] **Step 1: Write index.html (Vite's HTML entry)**

`frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>pydantic-studio</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Write the tree API client**

`frontend/src/api/tree.ts`:

```typescript
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
```

- [ ] **Step 3: Write the React entry (main.tsx)**

`frontend/src/main.tsx`:

```typescript
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./styles/globals.css";

const queryClient = new QueryClient();

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing <div id='root'> in index.html");
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
```

- [ ] **Step 4: Write the App component**

`frontend/src/App.tsx`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchTree } from "@/api/tree";

export default function App() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree"],
    queryFn: fetchTree,
  });

  if (isLoading) {
    return <div className="p-8 text-zinc-500">Loading tree...</div>;
  }
  if (error) {
    return (
      <div className="p-8 text-red-600">
        Failed to load tree: {error instanceof Error ? error.message : String(error)}
      </div>
    );
  }

  return (
    <div className="p-8 font-sans">
      <h1 className="text-2xl font-semibold mb-2">pydantic-studio</h1>
      <p className="text-sm text-zinc-500 mb-6">
        Phase 2 scaffold — raw <code>/api/tree</code> response below. Form
        components arrive in Phase 3.
      </p>
      <pre className="bg-zinc-100 p-4 rounded text-xs overflow-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
```

- [ ] **Step 5: Type-check the App**

```bash
cd frontend
pnpm exec tsc --noEmit
```

Expected: no errors. If errors appear about missing JSX runtime, double-check `tsconfig.json` has `"jsx": "react-jsx"`.

- [ ] **Step 6: Commit**

```bash
git add frontend/index.html frontend/src/main.tsx frontend/src/App.tsx \
  frontend/src/api/tree.ts
git commit -m "feat(frontend): minimal SPA - mount React, fetch /api/tree, dump JSON

App.tsx uses TanStack Query to fetch /api/tree (Phase 1 endpoint)
and renders the raw JSON in a <pre>. This is the Phase 2 milestone:
prove the toolchain end-to-end without any form components.

api/tree.ts is the seam Phase 3 grows into typed parsers (zod).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

---

## Task 7: First production build

**Files:**
- Create: `src/pydantic_studio/renderers/html/static/dist/index.html`
- Create: `src/pydantic_studio/renderers/html/static/dist/assets/*.js`
- Create: `src/pydantic_studio/renderers/html/static/dist/assets/*.css`

- [ ] **Step 1: Build the bundle**

```bash
cd frontend
pnpm build
```

Expected output: `vite v5.x.x building for production...` then a summary table showing files emitted into `../src/pydantic_studio/renderers/html/static/dist/`. Total bundle should be well under the spec's 250 KB gzip budget — for an empty page it'll be around 50–80 KB.

If the build fails with "ENOENT static/dist" or similar, manually create the parent: `mkdir -p ../src/pydantic_studio/renderers/html/static/dist` and re-run.

- [ ] **Step 2: Inspect the output**

```bash
ls ../src/pydantic_studio/renderers/html/static/dist/
ls ../src/pydantic_studio/renderers/html/static/dist/assets/
```

Expected: `index.html` + an `assets/` directory containing one `.js` and one `.css` file with hashed filenames (e.g., `index-DxR9wK.js`).

- [ ] **Step 3: Spot-check the built HTML**

```bash
cat ../src/pydantic_studio/renderers/html/static/dist/index.html
```

Expected: the original `index.html` rewritten with hashed asset URLs (e.g., `<script src="/assets/index-DxR9wK.js">`). Note the absolute `/assets/...` paths — this is intentional and is why the bundle has to be served from the path that maps to it.

Important nuance: the built `<script>` tag uses `/assets/...` (root-relative). That points at `/assets/<hash>.js`, which would resolve under FastAPI's mount as `http://server/assets/...` — but the actual mount serves at `/static/dist/assets/...`. **This mismatch is real and Phase 5 fixes it** by setting `base: "/static/dist/"` in `vite.config.ts` once the bundle is consumed via the static mount path, OR by adding the SPA-serve route at `/` (which is the eventual Phase 6 destination — then `/assets/...` resolves at root).

For Phase 2, the smoke test in Task 9 fetches `/static/dist/index.html` and asserts the HTML is served — it does NOT load the bundled JS. The actual end-to-end smoke (does the SPA execute in a browser?) is deferred. **This is a known limitation flagged in the Phase 2 plan.**

- [ ] **Step 4: Commit the built artifact**

```bash
cd ..    # repo root
git add src/pydantic_studio/renderers/html/static/dist
git commit -m "build(frontend): commit initial production bundle (Phase 2 milestone)

vite build output committed for downstream wheel inclusion. Bundle
references /assets/* root-relative; Phase 5 (or 6) fixes the
base-path so the SPA executes in-browser via FastAPI's serve. For
Phase 2 the bundle exists to prove the build pipeline works
end-to-end; the static smoke test in T9 only asserts index.html is
reachable.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

---

## Task 8: Wheel packaging + root .gitignore correction

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Fix root .gitignore so static/dist/ isn't ignored**

Read the current `.gitignore`. Line 8 is `dist/` — this matches `dist/` at any depth and would silently exclude `src/pydantic_studio/renderers/html/static/dist/`. Change it to `/dist/` (root-anchored) so only the top-level Python build directory is ignored.

Update the `# Python` block of `.gitignore`. Change:

```
build/
dist/
```

to:

```
build/
/dist/
```

Then add a defensive entry below the existing Python block (does not duplicate frontend/.gitignore but covers root-level installs):

```

# Frontend (Vite + pnpm) - frontend/.gitignore is authoritative,
# this is just a guard against tools accidentally writing to the root.
/frontend/node_modules/
```

- [ ] **Step 2: Verify the dist files are now tracked**

```bash
git check-ignore -v src/pydantic_studio/renderers/html/static/dist/index.html || echo "OK: not ignored"
```

Expected: prints `OK: not ignored`. If `git check-ignore` reports a match, the gitignore change didn't take effect — debug.

- [ ] **Step 3: Tell uv_build to include static/dist/ in the wheel**

Read the existing `pyproject.toml`. Look for `[tool.uv]` and `[tool.uv.build]` (the project already uses `uv_build` per `[build-system]`).

Add or update the wheel's data inclusion. The uv_build documentation key is `module-root-include` for file globs. As of uv 0.8+, the correct mechanism is `[tool.uv.build] data = { "dist" = "src/pydantic_studio/renderers/html/static/dist" }` OR via package-data through hatch-style globs.

**Verify the exact key** by reading `uv build --help` OR checking the uv_build source. If the project's `[build-system]` says `requires = ["uv_build>=0.8,<0.12"]`, then run:

```bash
uv build --wheel
unzip -l dist/pydantic_studio-*.whl | grep static/dist
```

Expected: lists the bundled `index.html`, `assets/*.js`, `assets/*.css`. If the dist/ files are MISSING from the wheel, the include directive is wrong — adjust until they appear.

The default uv_build behavior includes everything under `src/<package_name>/**` that's NOT in `.gitignore`. Since Step 1 fixed `.gitignore`, the default may already do the right thing — verify by running the build above. If `.gitignore` fix alone is sufficient, NO pyproject.toml change is needed; document this in the commit.

- [ ] **Step 4: Commit**

If pyproject.toml was modified:

```bash
git add .gitignore pyproject.toml
git commit -m "chore(build): include frontend bundle in wheel + fix .gitignore scope

Root-anchor the Python build's dist/ ignore (was matching every
dist/ in the tree, silently excluding the new bundled SPA at
src/pydantic_studio/renderers/html/static/dist/). Tell uv_build
to include the bundle in the wheel so 'pip install' ships the
ready-to-serve SPA without requiring Node on the user's machine.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

If only `.gitignore` changed (uv_build defaults already handle dist):

```bash
git add .gitignore
git commit -m "chore(build): root-anchor dist/ ignore so static/dist/ is tracked

Was: dist/ (matched at any depth, silently excluded the new bundled
SPA at src/pydantic_studio/renderers/html/static/dist/).
Now:  /dist/ (root-anchored; Python build's dist/ still ignored).

Verified uv_build's default file inclusion picks up the static/dist
tree once .gitignore stops excluding it; no pyproject.toml change
needed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

---

## Task 9: TestClient smoke for the bundled SPA

**Files:**
- Create: `tests/unit/test_html_static_bundle.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_html_static_bundle.py`:

```python
"""Smoke test: the committed Vite bundle is reachable via FastAPI's
existing /static mount. Phase 5 / 6 will move the SPA's index.html
to be served at / directly; for Phase 2 we only verify it's
reachable AT ALL via the path the static mount already provides.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import BaseModel

from pydantic_studio import build_form_tree
from pydantic_studio.renderers.html import StudioServer


class _Demo(BaseModel):
    name: str = ""


def test_static_dist_index_is_served() -> None:
    tree = build_form_tree(_Demo)
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)

    response = client.get("/static/dist/index.html")
    assert response.status_code == 200
    text = response.text
    # Vite always emits a div#root mount point.
    assert 'id="root"' in text
    # And a <script type="module"> tag for the bundled entry.
    assert '<script type="module"' in text


def test_static_dist_assets_are_served() -> None:
    tree = build_form_tree(_Demo)
    server = StudioServer(tree=tree, save_path=None)
    client = TestClient(server.app)

    # Find the bundled JS file via the HTML to avoid hard-coding the hash.
    html = client.get("/static/dist/index.html").text
    # crude scrape: pull the first /assets/...js path from the HTML
    import re

    js_match = re.search(r'/assets/[A-Za-z0-9_-]+\.js', html)
    assert js_match is not None, f"no /assets/*.js found in built index.html:\n{html}"
    js_path = js_match.group(0)

    # The HTML references it as /assets/<hash>.js (root-relative),
    # but the static mount serves it at /static/dist/assets/<hash>.js.
    mounted_path = f"/static/dist{js_path}"
    response = client.get(mounted_path)
    assert response.status_code == 200, (
        f"GET {mounted_path} returned {response.status_code}; "
        f"the bundle's index.html points at {js_path} which is "
        f"root-relative and won't work in-browser via the static "
        f"mount alone. Phase 5/6 fixes this by either setting "
        f"vite's base option OR by serving the SPA at /."
    )
    # Bundled JS must be a non-trivial size.
    assert len(response.content) > 1000
```

- [ ] **Step 2: Run the test to verify it currently passes**

```bash
uv run python -m pytest tests/unit/test_html_static_bundle.py -q
```

**Expected: 2 passed.** The static mount serves the bundle as-is; the index.html test just confirms 200 + correct mount-point markers; the assets test confirms the hashed JS is reachable when accessed via `/static/dist/assets/<hash>.js`.

**If `test_static_dist_assets_are_served` FAILS with 404** on the mounted asset, the cause is one of:
- The bundle commit (Task 7) was skipped or partial. Re-run `pnpm build` and re-commit.
- The static mount isn't finding the dist dir. Check `StudioServer._mount_static` and confirm the directory exists at the path it tries to mount.

The test is structured to give a useful error message ("the bundle's index.html points at ... which is root-relative...") so the failure mode at Phase 5 is well-flagged in advance.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_html_static_bundle.py
git commit -m "test(html): smoke-test the Phase 2 bundled SPA via static mount

Asserts /static/dist/index.html returns the built Vite HTML with the
React mount point, and that the hashed asset JS is reachable when
accessed via the mounted path. Documents the known root-relative
asset-path limitation that Phase 5/6 fixes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

---

## Task 10: Build script + dev-mode README hint + full-suite verify

**Files:**
- Create: `frontend/scripts/build.sh`
- Modify: `README.md` (add a short "Frontend development" section if not present)

- [ ] **Step 1: Write the build script wrapper**

`frontend/scripts/build.sh`:

```bash
#!/usr/bin/env bash
# Wrapper around `pnpm build` so CI and contributors run the same
# command. Uses --frozen-lockfile to ensure reproducibility.
set -euo pipefail

cd "$(dirname "$0")/.."
pnpm install --frozen-lockfile
pnpm build
echo "Bundle written to $(realpath ../src/pydantic_studio/renderers/html/static/dist)"
```

Make it executable:

```bash
chmod +x frontend/scripts/build.sh
```

- [ ] **Step 2: Add a short README note for frontend development**

Read the existing `README.md`. If it has no Frontend section, append (after the existing usage / install sections):

```markdown

## Frontend development (Phase 2+)

The Textual TUI and CLI are pure Python — `uv sync && uv run python examples/02_server_config.py tui` is enough.

The web renderer is a React SPA built with Vite, source under `frontend/`. End users do NOT need Node — `pip install pydantic-studio` ships the pre-built bundle. To modify the SPA:

```bash
cd frontend
corepack enable && corepack prepare pnpm@9 --activate   # one-time
pnpm install
pnpm dev              # Vite dev server with HMR; proxies /api/* to FastAPI on :8000
# in another terminal:
uv run python examples/02_server_config.py web
# then open http://localhost:5173 (Vite's port; not the FastAPI port)

# To refresh the committed bundle:
pnpm build            # or frontend/scripts/build.sh
git add ../src/pydantic_studio/renderers/html/static/dist
```

The bundled output (`src/pydantic_studio/renderers/html/static/dist/`) is committed to the repo so CI and downstream users don't need a Node toolchain.
```

If `README.md` already has a Frontend section (unlikely for this repo at Phase 2 start), append a "Phase 2 onward" subsection or merge the content into the existing structure.

- [ ] **Step 3: Run the full Python test suite**

```bash
uv run python -m pytest tests/ -q --deselect tests/unit/test_docs_build.py
```

Expected: all tests pass (499 from main + 2 new from Task 9 = 501). The `test_docs_build.py` deselection is the pre-existing mkdocs trampoline issue unrelated to this work.

If any HTML server test or HTML API test fails, the static mount may have been disturbed by the new dist/ tree — investigate.

- [ ] **Step 4: Run ruff on touched Python files**

```bash
uv run ruff check tests/unit/test_html_static_bundle.py
```

Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add frontend/scripts/build.sh README.md
git commit -m "chore(frontend): build script wrapper + README dev-loop note

build.sh is the canonical 'install + build' command for CI and
contributors. README documents the dev loop: pnpm dev with proxy
to a separately-running FastAPI process.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"
```

- [ ] **Step 6: Phase 2 done — handoff note**

Phase 2 ships:

- Working Vite/React/TS/Tailwind toolchain under `frontend/`
- TanStack Query setup + a `useQuery(['tree'], fetchTree)` flow
- Committed `static/dist/` bundle (no Node needed for end users)
- Wheel packaging that includes the bundle
- TestClient smoke confirming the bundle is reachable
- Documented dev loop in README

Known limitation flagged for Phase 5/6:
- The built `index.html` references `/assets/<hash>.js` (root-relative), which would 404 if served at `/static/dist/index.html` in a browser. The smoke test scopes around this by fetching the asset via its mounted path directly. **Phase 5 OR 6 fixes this** by either setting `base: "/static/dist/"` in `vite.config.ts` OR by adding the SPA-serve route at `/`. The latter is the spec's eventual goal (Phase 6 deletes the HTMX `/` route and replaces with `dist/index.html`).

Recommended branch name: `feature/shadcn-redesign-phase-2-frontend-scaffold`; merge with `--no-ff` per the codebase convention; tag the feature tip as `v0.2.0-phase-2` before merging.

---

## Self-review checklist (already applied)

- ✅ **Spec §8 Phase 2 ("Scaffold frontend/")**: Tasks 1–6 set up Vite + React + Tailwind + shadcn CLI (no primitives used).
- ✅ **Spec §4 repo layout**: `frontend/` at repo root, bundled output to `src/pydantic_studio/renderers/html/static/dist/`. Task 3 sets `outDir`; Task 7 commits the result.
- ✅ **Spec §4.1 wheel packaging**: Task 8 fixes `.gitignore` and verifies the wheel includes the bundle. Defers to actual `uv build` output to determine whether a `pyproject.toml` directive is needed.
- ✅ **Spec §4.2 contributor experience**: Task 10 documents the dev loop (`pnpm dev` + FastAPI in another terminal); CI guard explicitly deferred (it's a future task, not a Phase 2 blocker).
- ✅ **Spec §7 build pipeline**: Tasks 1–7 implement pnpm + Vite + Tailwind v4. The `frontend/scripts/build.sh` wrapper lands in Task 10.
- ✅ **Spec §8 acceptance**: Task 9 is the spec-required "smoke test that static/dist/index.html loads under TestClient". Plus a stronger asset-fetch assertion so the root-relative-base limitation gets flagged immediately, not silently.
- ✅ **No placeholders**: every step has the exact code/command to run. No "TBD", no "add appropriate ... handling".
- ✅ **Type consistency**: `fetchTree`, `App`, `cn`, `QueryClient`, and the file paths under `frontend/src/...` are used consistently across tasks 5–9.
- ✅ **Known unknowns documented**: Task 7 explicitly flags the root-relative asset path; Task 8 explicitly says "verify the uv_build directive" rather than guessing the exact key; Task 9's failure-mode assertion text tells future debuggers what to check.
- ✅ **YAGNI**: no zod (Phase 3 introduces typed parsers), no shadcn primitives copied (Phase 3 installs as needed), no light/dark theme (Phase 5), no CI workflow (separate follow-up if/when needed).
- ✅ **Frequent commits**: 10 task-aligned commits, each a logical unit. Mirrors the Phase 1 cadence.
