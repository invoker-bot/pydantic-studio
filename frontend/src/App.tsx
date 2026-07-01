import { useEffect, useMemo, useRef, useState } from "react";
import { useMutationState, useQuery } from "@tanstack/react-query";
import { Redo2, Undo2 } from "lucide-react";

import { studioUrl } from "@/api/base";
import { fetchTree } from "@/api/tree";
import { APPLY_MUTATION_KEY, useApplyMutation } from "@/api/mutations";
import {
  useCancelEdit,
  useSubmitTree,
  type SubmitError,
} from "@/api/submit";
import { FormField } from "@/components/form/FormField";
import {
  FormFlagsContext,
  scrollToField,
  type FormFlags,
} from "@/components/form/errors";
import { Button } from "@/components/ui/button";
import { VariantSelector } from "@/components/form/VariantSelector";
import { missingRequiredPaths } from "@/lib/required";

type Status = "editing" | "saved" | "cancelled";

const HEARTBEAT_INTERVAL_MS = 10_000;
const EDITOR_HEADING_ID = "studio-editor-heading";
const PREVIEW_HEADING_ID = "studio-preview-heading";

function submitErrorHeading(errors: SubmitError[]): string {
  const allSaveErrors = errors.every((err) =>
    err.message.startsWith("could not save"),
  );
  const label = allSaveErrors ? "save error" : "validation error";
  return `${errors.length} ${label}${errors.length === 1 ? "" : "s"}:`;
}

export default function App() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree"],
    queryFn: fetchTree,
  });

  const submit = useSubmitTree();
  const cancel = useCancelEdit();
  const history = useApplyMutation();
  const [status, setStatus] = useState<Status>("editing");
  const [submitErrors, setSubmitErrors] = useState<SubmitError[]>([]);
  const [actionError, setActionError] = useState<string | null>(null);
  const [requiredCursor, setRequiredCursor] = useState(0);
  const successfulMutationTimes = useMutationState({
    filters: { mutationKey: APPLY_MUTATION_KEY },
    select: (mutation) =>
      mutation.state.status === "success" ? mutation.state.submittedAt : 0,
  });
  const latestSuccessfulMutationAt = successfulMutationTimes.reduce(
    (latest, submittedAt) => Math.max(latest, submittedAt),
    0,
  );
  const lastSeenSuccessfulMutationAt = useRef(latestSuccessfulMutationAt);

  const flags = useMemo<FormFlags>(
    () => ({
      errorPaths: new Set(submitErrors.map((e) => e.path).filter(Boolean)),
      readonlyPaths: new Set(data?.readonly_paths ?? []),
    }),
    [submitErrors, data],
  );
  const missingRequired = useMemo(
    () => (data ? missingRequiredPaths(data.root) : []),
    [data],
  );

  useEffect(() => {
    const sendHeartbeat = () => {
      void fetch(studioUrl("/api/heartbeat"), {
        method: "GET",
        cache: "no-store",
      }).catch(() => {
        // Submit/cancel can shut down the local server before React unmounts.
      });
    };

    void sendHeartbeat();
    const intervalId = window.setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, []);

  useEffect(() => {
    if (latestSuccessfulMutationAt <= lastSeenSuccessfulMutationAt.current) return;
    lastSeenSuccessfulMutationAt.current = latestSuccessfulMutationAt;
    if (submitErrors.length > 0) setSubmitErrors([]);
    if (actionError) setActionError(null);
  }, [latestSuccessfulMutationAt, submitErrors.length, actionError]);

  // A failed submit scrolls straight to the first offending field —
  // the banner is the summary, the field is the destination.
  useEffect(() => {
    if (submitErrors.length > 0 && submitErrors[0].path) {
      scrollToField(submitErrors[0].path);
    }
  }, [submitErrors]);

  if (isLoading) {
    return (
      <div
        role="status"
        aria-busy="true"
        aria-live="polite"
        className="p-8 text-zinc-500"
      >
        Loading tree...
      </div>
    );
  }
  if (error || !data) {
    return (
      <div role="alert" aria-atomic="true" className="p-8 text-red-600">
        Failed to load tree:{" "}
        {error instanceof Error ? error.message : String(error)}
      </div>
    );
  }

  if (status === "saved") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div
          role="status"
          aria-atomic="true"
          className="text-center space-y-2"
        >
          <h1 className="text-3xl font-semibold text-emerald-600">Saved</h1>
          <p className="text-sm text-zinc-500">You may close this tab.</p>
        </div>
      </div>
    );
  }
  if (status === "cancelled") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div
          role="status"
          aria-atomic="true"
          className="text-center space-y-2"
        >
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
    setActionError(null);
    submit.mutate(undefined, {
      onSuccess: (response) => {
        if (response.ok) {
          setStatus("saved");
        } else {
          setSubmitErrors(response.errors);
        }
      },
      onError: (err) => {
        setActionError(
          `Save failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      },
    });
  };

  const handleCancel = () => {
    setActionError(null);
    cancel.mutate(undefined, {
      onSuccess: () => setStatus("cancelled"),
      onError: (err) => {
        setActionError(
          `Cancel failed: ${err instanceof Error ? err.message : String(err)}`,
        );
      },
    });
  };
  const handleHistoryAction = (label: "Undo" | "Redo", op: "undo" | "redo") => {
    setActionError(null);
    history.mutate(
      { op },
      {
        onError: (err) => {
          setActionError(
            `${label} failed: ${err instanceof Error ? err.message : String(err)}`,
          );
        },
      },
    );
  };
  const isActionPending = submit.isPending || cancel.isPending || history.isPending;

  return (
    <div className="grid min-h-screen grid-cols-1 gap-6 bg-white p-4 font-sans sm:p-6 lg:grid-cols-2 lg:gap-8 lg:p-8">
      <section
        aria-labelledby={EDITOR_HEADING_ID}
        className="min-w-0 space-y-6"
      >
        <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
          <div className="min-w-0">
            <h1 id={EDITOR_HEADING_ID} className="text-2xl font-semibold">
              {schemaName}
            </h1>
            <p className="mt-1 break-words text-xs text-zinc-500">
              {data.schema_name}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
            {missingRequired.length > 0 && (
              <button
                type="button"
                data-testid="required-jump"
                onClick={() => {
                  const target =
                    missingRequired[requiredCursor % missingRequired.length];
                  setRequiredCursor((c) => c + 1);
                  scrollToField(target);
                }}
                className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-800 hover:bg-amber-100"
                title="jump to the next missing required field"
              >
                {missingRequired.length} required missing →
              </button>
            )}
            <Button
              variant="outline"
              size="icon"
              aria-label="Undo"
              title="Undo"
              onClick={() => handleHistoryAction("Undo", "undo")}
              disabled={isActionPending || !data.history.can_undo}
            >
              <Undo2 aria-hidden="true" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              aria-label="Redo"
              title="Redo"
              onClick={() => handleHistoryAction("Redo", "redo")}
              disabled={isActionPending || !data.history.can_redo}
            >
              <Redo2 aria-hidden="true" />
            </Button>
            <Button
              variant="outline"
              onClick={handleCancel}
              disabled={isActionPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isActionPending}
            >
              {submit.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </header>
        <FormFlagsContext.Provider value={flags}>
          {data.variant && <VariantSelector variant={data.variant} />}
          {actionError && (
            <div
              data-testid="action-error"
              role="alert"
              aria-atomic="true"
              className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800"
            >
              {actionError}
            </div>
          )}
          {submitErrors.length > 0 && (
            <div
              data-testid="submit-errors"
              role="alert"
              aria-atomic="true"
              className="rounded border border-red-300 bg-red-50 p-3 text-sm"
            >
              <p className="font-semibold text-red-900 mb-1">
                {submitErrorHeading(submitErrors)}
              </p>
              <ul className="text-red-700 list-disc list-inside space-y-1">
                {submitErrors.map((err, idx) => (
                  <li key={`${err.path}-${idx}`}>
                    <button
                      type="button"
                      className="font-mono underline decoration-dotted underline-offset-2 hover:text-red-900"
                      onClick={() => err.path && scrollToField(err.path)}
                      title="jump to this field"
                    >
                      {err.path || "(root)"}
                    </button>
                    {": "}
                    {err.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <FormField node={data.root} path="" />
        </FormFlagsContext.Provider>
      </section>
      <section
        aria-labelledby={PREVIEW_HEADING_ID}
        className="min-w-0 space-y-2"
      >
        <h2
          id={PREVIEW_HEADING_ID}
          className="text-xs font-semibold uppercase tracking-wide text-zinc-500"
        >
          Live YAML preview
        </h2>
        <pre
          data-testid="tree-preview"
          className="max-h-[60vh] overflow-auto rounded bg-zinc-100 p-4 font-mono text-xs whitespace-pre-wrap break-words lg:max-h-[80vh]"
        >
          {data.preview}
        </pre>
      </section>
    </div>
  );
}
