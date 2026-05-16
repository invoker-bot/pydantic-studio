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

### `edit <module:Class> [<file>] [--frontend tui|web]`

Launch an interactive editor. `tui` (default) launches the Textual UI;
`web` boots the FastAPI HTML renderer in your default browser.

```bash
$ pydantic-studio edit mypkg.config:AppSettings config.yaml
$ pydantic-studio edit --frontend web mypkg.config:AppSettings config.yaml
```

If `<file>` exists, it's loaded; otherwise a fresh tree is built from
the schema's defaults. On save, the tree is materialized via
`to_instance()` and written via `save_config` (extension picks format).

### `version`

```bash
$ pydantic-studio version
pydantic-studio 0.1.1
```

## Exit codes

- `0` — success
- `1` — validation failure (`run` / `check` / `edit`)
- `2` — argument or schema-resolution error
