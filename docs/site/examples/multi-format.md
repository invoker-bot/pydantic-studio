# Example: Multi-format I/O

The same FormTree round-trips cleanly through YAML, TOML, and JSON.

```python
from pydantic import BaseModel, Field
from pydantic_studio import build_form_tree, save_config, load_config


class Settings(BaseModel):
    name: str = Field(default="prod", description="Service identifier")
    port: int = Field(default=8080, description="Listening port")


tree = build_form_tree(Settings)
tree.set_value("port", 9090)

save_config(tree, "config.yaml")
save_config(tree, "config.toml")
save_config(tree, "config.json")
```

The dispatcher picks the format from the extension. Each file:

```yaml
# config.yaml — comments preserved on edit
# Service identifier
name: prod
# Listening port
port: 9090
```

```toml
# config.toml — comments preserved
# Service identifier
name = "prod"
# Listening port
port = 9090
```

```json
{
  "name": "prod",
  "port": 9090
}
```

(JSON has no comments — accepted limitation.)

## Round-trip

```python
yaml_tree = load_config("config.yaml", Settings)
toml_tree = load_config("config.toml", Settings)
json_tree = load_config("config.json", Settings)

yaml_tree.to_instance() == toml_tree.to_instance() == json_tree.to_instance()
```

## Format-specific helpers

If you want to bypass dispatch:

```python
from pydantic_studio import (
    load_yaml, save_yaml,
    load_toml, save_toml,
    load_json, save_json,
)
```
