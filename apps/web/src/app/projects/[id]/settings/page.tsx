"use client";

import { use } from "react";
import { PageHeader } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { PluginUploadCard } from "@/components/flowpath/plugin-upload-card";
import { useProject, useProjectDisplayName } from "@/lib/api/hooks";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function SettingsPage({ params }: PageProps) {
  const { id } = use(params);
  const { data: project } = useProject(id);
  const projectName = useProjectDisplayName(id);

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        breadcrumb={[
          { label: "Projects", href: "/projects" },
          { label: projectName, href: `/projects/${id}` },
          { label: "Settings" },
        ]}
        title="Settings"
        description="Working fluid, units, density preference, and members. Project file is canonical; changes here write to the deck."
      />

      <div className="flex-1 overflow-auto scrollbar-subtle px-5 py-5">
        <div className="grid gap-4 lg:grid-cols-2 max-w-4xl">
          <Card className="p-4">
            <h3 className="text-md font-medium">General</h3>
            <p className="mt-1 text-sm text-text-muted">
              The project file is a TOML deck. These fields write into it.
            </p>
            <div className="mt-4 flex flex-col gap-3">
              <Field label="Name">
                <Input defaultValue={project?.name} />
              </Field>
              <Field label="Description">
                <Input defaultValue={project?.description} />
              </Field>
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="text-md font-medium">Working fluid</h3>
            <p className="mt-1 text-sm text-text-muted">
              Real-fluid properties come from CoolProp by default; switch to
              REFPROP for cases that need it.
            </p>
            <div className="mt-4 flex flex-col gap-3">
              <Field label="Fluid">
                <Select defaultValue={project?.workingFluid ?? "air"}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="air">Air (CoolProp)</SelectItem>
                    <SelectItem value="co2">CO₂ (CoolProp)</SelectItem>
                    <SelectItem value="n2">N₂ (CoolProp)</SelectItem>
                    <SelectItem value="h2">H₂ (CoolProp)</SelectItem>
                    <SelectItem value="methane">Methane (CoolProp)</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="text-md font-medium">Units</h3>
            <p className="mt-1 text-sm text-text-muted">
              SI by default; toggle to US customary. Per-cell overrides on
              every input.
            </p>
            <div className="mt-4 flex items-center gap-3 text-sm">
              <Switch id="us" />
              <Label htmlFor="us">Use US customary units</Label>
            </div>
          </Card>

          <Card className="p-4">
            <h3 className="text-md font-medium">Density</h3>
            <p className="mt-1 text-sm text-text-muted">
              Comfortable mode widens every row and panel by 8 px. Engineers
              who screen-share often prefer it.
            </p>
            <div className="mt-4 flex items-center gap-3 text-sm">
              <Switch id="comfortable" />
              <Label htmlFor="comfortable">Comfortable density</Label>
            </div>
          </Card>

          <PluginUploadCard projectId={id} />

          <Card className="p-4 lg:col-span-2">
            <h3 className="text-md font-medium">Members</h3>
            <p className="mt-1 text-sm text-text-muted">
              Members can view, edit, or run this project. v1 has one viewer
              (you).
            </p>
            <div className="mt-4 flex items-center gap-3">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand text-xs font-medium text-text-inverse">
                DU
              </span>
              <div>
                <div className="text-sm">Demo User</div>
                <div className="text-xs text-text-muted">
                  demo@americanturbines.com · owner
                </div>
              </div>
              <Button variant="outline" size="sm" className="ml-auto">
                Invite
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label className="text-xs text-text-muted">{label}</Label>
      {children}
    </div>
  );
}
