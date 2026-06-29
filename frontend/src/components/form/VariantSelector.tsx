import type { VariantStateData } from "@/api/schemas";
import { useApplyMutation } from "@/api/mutations";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function VariantSelector({ variant }: { variant: VariantStateData }) {
  const mutation = useApplyMutation();
  const selected = variant.options.find(
    (option) => option.id === variant.selected_id,
  );

  return (
    <div className="space-y-2 rounded-md border border-zinc-200 bg-zinc-50 p-3">
      <Label htmlFor="variant-selector" className="text-sm font-medium">
        Variant
      </Label>
      <Select
        value={variant.selected_id}
        onValueChange={(variant_id) =>
          mutation.mutate({ op: "select_root_variant", variant_id })
        }
      >
        <SelectTrigger id="variant-selector" aria-label="Variant">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {variant.options.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {selected?.description && (
        <p className="text-xs text-zinc-500">{selected.description}</p>
      )}
    </div>
  );
}
