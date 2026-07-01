import { Chip } from "@/components/form/chrome/Chip";

type ConstraintValue = number | string | null | undefined;
type ConstraintKey = "ge" | "le" | "gt" | "lt" | "multiple_of";

type NumericConstraints = Partial<Record<ConstraintKey, ConstraintValue>>;

const CONSTRAINTS: Array<{ key: ConstraintKey; label: string; title: string }> = [
  { key: "ge", label: ">=", title: "ge" },
  { key: "le", label: "<=", title: "le" },
  { key: "gt", label: ">", title: "gt" },
  { key: "lt", label: "<", title: "lt" },
  { key: "multiple_of", label: "multiple", title: "multiple_of" },
];

function formatConstraintValue(value: Exclude<ConstraintValue, null | undefined>): string {
  return String(value);
}

export function NumericConstraintChips({ constraints }: { constraints: NumericConstraints }) {
  return (
    <>
      {CONSTRAINTS.map(({ key, label, title }) => {
        const value = constraints[key];
        if (value === null || value === undefined) return null;
        return (
          <Chip key={key} title={title}>
            {label} {formatConstraintValue(value)}
          </Chip>
        );
      })}
    </>
  );
}
