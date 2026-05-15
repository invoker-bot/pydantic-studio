import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchTree } from "@/api/tree";
import {
  useCancelEdit,
  useSubmitTree,
  type SubmitError,
} from "@/api/submit";
import { FormField } from "@/components/form/FormField";
import { Button } from "@/components/ui/button";

type Status = "editing" | "saved" | "cancelled";

export default function App() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree"],
    queryFn: fetchTree,
  });

  const submit = useSubmitTree();
  const cancel = useCancelEdit();
  const [status, setStatus] = useState<Status>("editing");
  const [submitErrors, setSubmitErrors] = useState<SubmitError[]>([]);

  if (isLoading) {
    return <div className="p-8 text-zinc-500">Loading tree...</div>;
  }
  if (error || !data) {
    return (
      <div className="p-8 text-red-600">
        Failed to load tree:{" "}
        {error instanceof Error ? error.message : String(error)}
      </div>
    );
  }

  if (status === "saved") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-semibold text-emerald-600">Saved</h1>
          <p className="text-sm text-zinc-500">You may close this tab.</p>
        </div>
      </div>
    );
  }
  if (status === "cancelled") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-semibold text-zinc-500">Cancelled</h1>
          <p className="text-sm text-zinc-500">No changes were saved.</p>
        </div>
      </div>
    );
  }

  const schemaName = data.schema_name.includes(":")
    ? data.schema_name.split(":")[1]
    : data.schema_name;

  const handleSave = () => {
    setSubmitErrors([]);
    submit.mutate(undefined, {
      onSuccess: (response) => {
        if (response.ok) {
          setStatus("saved");
        } else {
          setSubmitErrors(response.errors);
        }
      },
    });
  };

  const handleCancel = () => {
    cancel.mutate(undefined, {
      onSuccess: () => setStatus("cancelled"),
    });
  };

  return (
    <div className="grid grid-cols-2 gap-8 p-8 font-sans min-h-screen bg-white">
      <section className="space-y-6">
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">{schemaName}</h1>
            <p className="text-xs text-zinc-500 mt-1">{data.schema_name}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button
              variant="outline"
              onClick={handleCancel}
              disabled={cancel.isPending || submit.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={submit.isPending || cancel.isPending}
            >
              {submit.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </header>
        {submitErrors.length > 0 && (
          <div
            data-testid="submit-errors"
            className="rounded border border-red-300 bg-red-50 p-3 text-sm"
          >
            <p className="font-semibold text-red-900 mb-1">
              {submitErrors.length} validation error
              {submitErrors.length === 1 ? "" : "s"}:
            </p>
            <ul className="text-red-700 list-disc list-inside space-y-1">
              {submitErrors.map((err, idx) => (
                <li key={`${err.path}-${idx}`}>
                  <span className="font-mono">{err.path || "(root)"}</span>
                  {": "}
                  {err.message}
                </li>
              ))}
            </ul>
          </div>
        )}
        <FormField node={data.root} path="" />
      </section>
      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Live YAML preview
        </h2>
        <pre
          data-testid="tree-preview"
          className="bg-zinc-100 p-4 rounded text-xs overflow-auto max-h-[80vh] font-mono"
        >
          {data.preview}
        </pre>
      </section>
    </div>
  );
}
