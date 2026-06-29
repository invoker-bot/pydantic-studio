# Root model variants

Use root model variants when the user should choose which Pydantic model
class a new config represents. The feature is generic: pydantic-studio
stores stable ids and model classes, then each frontend renders the
selector in its own native way.

```python
from pydantic import BaseModel, Field
from pydantic_studio import VariantRegistry, VariantSpec, build_variant_form_tree, save_yaml


class EmailNotifier(BaseModel):
    address: str = Field(default="ops@example.com", description="Recipient address")


class SlackNotifier(BaseModel):
    channel: str = Field(default="#ops", description="Target Slack channel")


variants = VariantRegistry(
    [
        VariantSpec(id="email", model=EmailNotifier, label="Email"),
        VariantSpec(id="slack", model=SlackNotifier, label="Slack"),
    ]
)

tree = build_variant_form_tree(
    variants,
    selected_id="slack",
    discriminator="class_name",
    persistence="inline_discriminator",
)

save_yaml(tree, "notifier.yaml")
```

The saved YAML contains the selected id plus the selected model fields:

```yaml
class_name: slack
# Target Slack channel
channel: "#ops"
```

`persistence="metadata"` is the default. In that mode the selected
variant is available to the editor session but is not written into the
config file. Use `inline_discriminator` when downstream loaders expect a
key such as `class_name`, `type`, or `kind`.

## Frontend behavior

- Console prompts the root choice first:

  ```text
  variant (email/slack) [email]: slack
  channel [#ops]:
  ```

- TUI shows a `Variant` row at the top of the root form. Use `←` and
  `→` to switch; the field list is rebuilt for the selected model.

- Web renders a selector near the page header and sends the same
  `select_root_variant` mutation to the server.
