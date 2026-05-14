import { useQuery } from "@tanstack/react-query";
import { fetchTree } from "@/api/tree";

export default function App() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree"],
    queryFn: fetchTree,
  });

  if (isLoading) {
    return <div className="p-8 text-zinc-500">Loading tree...</div>;
  }
  if (error) {
    return (
      <div className="p-8 text-red-600">
        Failed to load tree: {error instanceof Error ? error.message : String(error)}
      </div>
    );
  }

  return (
    <div className="p-8 font-sans">
      <h1 className="text-2xl font-semibold mb-2">pydantic-studio</h1>
      <p className="text-sm text-zinc-500 mb-6">
        Phase 2 scaffold — raw <code>/api/tree</code> response below. Form
        components arrive in Phase 3.
      </p>
      <pre className="bg-zinc-100 p-4 rounded text-xs overflow-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
