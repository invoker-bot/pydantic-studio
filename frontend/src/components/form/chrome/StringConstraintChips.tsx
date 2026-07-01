import { Chip } from "@/components/form/chrome/Chip";

type StringConstraints = {
  min_length?: number | null;
  max_length?: number | null;
  pattern?: string | null;
};

export function StringConstraintChips({ constraints }: { constraints: StringConstraints }) {
  return (
    <>
      {constraints.min_length !== null && constraints.min_length !== undefined && (
        <Chip title="min_length">min {constraints.min_length}</Chip>
      )}
      {constraints.max_length !== null && constraints.max_length !== undefined && (
        <Chip title="max_length">max {constraints.max_length}</Chip>
      )}
      {constraints.pattern && <Chip title="pattern">pattern {constraints.pattern}</Chip>}
    </>
  );
}
