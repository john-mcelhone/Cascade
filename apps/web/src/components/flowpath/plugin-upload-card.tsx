"use client";

/**
 * PluginUploadCard — Project Settings panel for custom-loss-model plugins.
 *
 * ADAPT-035 surface. Fetches `/api/projects/{id}/loss-models` on mount,
 * renders the built-in + user cohorts, exposes a "Upload plugin" file
 * input that POSTs to `/api/projects/{id}/loss-models/upload`, and
 * lets the user pick one as the project's active loss model.
 *
 * Security note (rendered in the UI as a warning banner): plugin code
 * runs in-process. Only upload code you trust.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Upload, Trash2, CheckCircle2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getApiClient } from "@/lib/api";
import type {
  PluginLossModelInfo,
  PluginUploadResponse,
} from "@/lib/api/types";

interface Props {
  projectId: string;
}

export function PluginUploadCard({ projectId }: Props) {
  const [plugins, setPlugins] = useState<PluginLossModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<
    | { kind: "idle" }
    | { kind: "uploading" }
    | { kind: "ok"; name: string }
    | { kind: "error"; message: string }
  >({ kind: "idle" });
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await getApiClient().listProjectLossModels(projectId);
      setPlugins(list);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onFile = async (file: File) => {
    setUploadStatus({ kind: "uploading" });
    try {
      const resp: PluginUploadResponse =
        await getApiClient().uploadLossModelPlugin(projectId, file);
      setUploadStatus({ kind: "ok", name: resp.plugin.name });
      await refresh();
    } catch (err) {
      const msg =
        err && typeof err === "object" && "message" in err
          ? String((err as { message: unknown }).message)
          : "Upload failed.";
      setUploadStatus({ kind: "error", message: msg });
    }
  };

  const onSelect = async (name: string) => {
    try {
      await getApiClient().selectLossModel(projectId, name);
      setActive(name);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("Failed to select loss model", err);
    }
  };

  const onDelete = async (name: string) => {
    if (
      !window.confirm(
        `Remove plugin "${name}"? This deletes the on-disk file as well.`,
      )
    )
      return;
    try {
      await getApiClient().deleteLossModelPlugin(projectId, name);
      await refresh();
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("Failed to delete plugin", err);
    }
  };

  return (
    <Card className="p-4 lg:col-span-2">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-md font-medium">Loss models</h3>
          <p className="mt-1 text-sm text-text-muted">
            Built-in models ship with Cascade. Upload a Python file to add
            a custom <code>LossModel</code> subclass.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".py"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onFile(f);
              // Allow re-upload of same file
              e.target.value = "";
            }}
          />
          <Button
            type="button"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadStatus.kind === "uploading"}
          >
            <Upload className="mr-1 h-3 w-3" />
            {uploadStatus.kind === "uploading"
              ? "Uploading…"
              : "Upload plugin"}
          </Button>
        </div>
      </div>

      {/* Security banner — required by ADAPT-035 spec */}
      <div className="mt-3 flex items-start gap-2 rounded-sm border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-text">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
        <div>
          <strong>Plugins run in the same process as Cascade.</strong> Only
          upload code from sources you trust. There is no sandbox in v1.
          Future v1.1 will add subprocess isolation.
        </div>
      </div>

      {uploadStatus.kind === "ok" && (
        <div className="mt-3 flex items-center gap-2 rounded-sm border border-emerald-500/40 bg-emerald-500/5 px-3 py-2 text-xs">
          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          <span>
            Loaded <strong>{uploadStatus.name}</strong>.
          </span>
        </div>
      )}
      {uploadStatus.kind === "error" && (
        <div className="mt-3 rounded-sm border border-red-500/40 bg-red-500/5 px-3 py-2 text-xs text-red-700">
          {uploadStatus.message}
        </div>
      )}

      <div className="mt-4">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-text-muted">
            <tr>
              <th className="pb-1">Name</th>
              <th className="pb-1">Origin</th>
              <th className="pb-1">Machine class</th>
              <th className="pb-1">Version</th>
              <th className="pb-1 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="py-3 text-xs text-text-muted">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && plugins.length === 0 && (
              <tr>
                <td colSpan={5} className="py-3 text-xs text-text-muted">
                  No plugins registered.
                </td>
              </tr>
            )}
            {plugins.map((p) => (
              <tr key={p.name} className="border-t border-border-subtle">
                <td className="py-2 font-mono text-xs">{p.name}</td>
                <td className="py-2">
                  <Badge
                    variant={p.origin === "builtin" ? "outline" : "brand"}
                  >
                    {p.origin}
                  </Badge>
                </td>
                <td className="py-2 text-xs text-text-muted">
                  {p.applicable_machine_classes.join(", ")}
                </td>
                <td className="py-2 font-mono text-xs text-text-muted">
                  {p.version || "—"}
                </td>
                <td className="py-2 text-right">
                  <Button
                    size="sm"
                    variant={active === p.name ? "default" : "outline"}
                    onClick={() => onSelect(p.name)}
                  >
                    {active === p.name ? "Active" : "Set active"}
                  </Button>
                  {p.origin === "user" && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="ml-1 text-red-600"
                      onClick={() => onDelete(p.name)}
                      aria-label={`Delete plugin ${p.name}`}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
