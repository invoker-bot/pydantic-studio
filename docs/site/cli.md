# CLI Reference

```bash
pydantic-studio --help
```

## Commands

### `show <module:Class>`

Inspect a schema's form-tree shape.

```bash
$ pydantic-studio show mypkg.config:AppSettings
AppSettings
├── name (str)
├── port (int)
└── api_url (url)
```

### `fill <module:Class> [--out FILE]`

Emit a config stub populated with defaults. Writes YAML to stdout if
`--out` is omitted; format inferred from extension otherwise.
Required YAML fields without defaults are emitted as the quoted string
`'?'` so the stub is still valid YAML while you fill it in.

```bash
$ pydantic-studio fill mypkg.config:AppSettings --out config.yaml
$ pydantic-studio fill mypkg.config:AppSettings --out config.toml
$ pydantic-studio fill mypkg.config:AppSettings --out config.json
```

### `run <module:Class> <file>`

Load a file, validate, print the model dump.

```bash
$ pydantic-studio run mypkg.config:AppSettings config.yaml
AppSettings(name='prod', port=8080, ...)
```

Exits non-zero if validation fails.

### `check <module:Class> <file>`

Same as `run` but silent on success — for CI integration.

```bash
$ pydantic-studio check mypkg.config:AppSettings config.yaml
config.yaml: OK
```

### `edit <module:Class> [<file>] [--frontend console|tui|web]`

Launch an interactive editor. `console` (default) asks one prompt per field
and writes the save target after the final answer. `tui` launches the Textual
UI; `web` boots the FastAPI HTML renderer in your default browser.

```bash
$ pydantic-studio edit mypkg.config:AppSettings config.yaml
$ pydantic-studio edit mypkg.config:AppSettings
$ pydantic-studio edit --frontend tui mypkg.config:AppSettings config.yaml
$ pydantic-studio edit --frontend web mypkg.config:AppSettings config.yaml
```

If `<file>` exists, it's loaded; if it does not exist, it is used as the save
target for a fresh tree. If `<file>` is omitted, the editor starts from the
schema's defaults and saves to `<Class>.yaml` in the current directory. On save,
the tree is materialized via `to_instance()` and written to the configured
save target. In console mode, press Enter to keep the displayed value.

### `version`

```bash
$ pydantic-studio version
pydantic-studio 0.1.2
```

## Exit codes

- `0` — success
- `1` — validation failure (`run` / `check` / `edit`)
- `2` — argument or schema-resolution error
