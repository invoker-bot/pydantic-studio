import { useQuery } from "@tanstack/react-query";

import { fetchTree } from "@/api/tree";
import { FormField } from "@/components/form/FormField";

export default function App() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree"],
    queryFn: fetchTree,
  });

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

  const schemaName = data.schema_name.includes(":")
    ? data.schema_name.split(":")[1]
    : data.schema_name;

  return (
    <div className="grid grid-cols-2 gap-8 p-8 font-sans min-h-screen bg-white">
      <section className="space-y-6">
        <header>
          <h1 className="text-2xl font-semibold">{schemaName}</h1>
          <p className="text-xs text-zinc-500 mt-1">{data.schema_name}</p>
        </header>
        <FormField node={data.root} path="" />
      </section>
      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Live preview
        </h2>
        <pre
          data-testid="tree-preview"
          className="bg-zinc-100 p-4 rounded text-xs overflow-auto max-h-[80vh]"
        >
          {JSON.stringify(data, null, 2)}
        </pre>
      </section>
    </div>
  );
}
