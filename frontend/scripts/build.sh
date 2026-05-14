#!/usr/bin/env bash
# Wrapper around `pnpm build` so CI and contributors run the same
# command. Uses --frozen-lockfile to ensure reproducibility.
set -euo pipefail

cd "$(dirname "$0")/.."
pnpm install --frozen-lockfile
pnpm build
echo "Bundle written to $(realpath ../src/pydantic_studio/renderers/html/static/dist)"
