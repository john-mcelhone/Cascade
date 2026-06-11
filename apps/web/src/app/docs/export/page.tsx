import type { Metadata } from "next";
import Link from "next/link";
import { CodeTabs, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Geometry export" };

export default function ExportPage() {
  return (
    <DocPage slug="export">
      <Section id="formats" title="What you can export">
        <ParamTable title="Formats">
          <ParamRow name="GLB / STL / OBJ" type="mesh — base install">
            Triangulated meshes of the designed impeller. GLB is what the
            in-app 3D viewer renders; STL feeds printers and meshers; OBJ is
            the universal interchange.
          </ParamRow>
          <ParamRow name="STEP / IGES" type="CAD — requires cascade[cad]">
            True CAD geometry via OpenCASCADE for downstream CAD work. Also a
            fluid-volume STEP — the negative space of the passage, which is
            what CFD meshing actually wants.
          </ParamRow>
          <ParamRow name="TurboGrid NDF" type="meshing — base install">
            Blade definition for ANSYS TurboGrid’s turbomachinery meshing
            pipeline.
          </ParamRow>
          <ParamRow name="Surface point cloud" type="data — base install">
            Raw sampled surface points, when you’d rather run your own
            surfacing.
          </ParamRow>
        </ParamTable>
        <Callout kind="note" title="Why STEP is optional">
          The CAD stack is ~200 MB of compiled OpenCASCADE C++, so it ships
          as the optional{" "}
          <code className="font-mono text-[13px]">cascade[cad]</code> extra (
          <code className="font-mono text-[13px]">KG-G-08</code>); conda is
          the more reliable install channel. The geometry module imports it
          lazily — a vanilla install never touches that code path. Probe
          availability at{" "}
          <code className="font-mono text-[13px]">GET /api/health/cad</code>.
        </Callout>
      </Section>

      <Section id="lod" title="Level of detail">
        <p>
          Mesh resolution is explicit, so the browser preview and the export
          never silently share a mesh:
        </p>
        <ParamTable title="MeshLOD">
          <ParamRow name="PREVIEW" type="~3k vertices">
            Instant browser preview while browsing candidates.
          </ParamRow>
          <ParamRow name="STANDARD" type="~7k vertices">
            The canonical in-app 3D view.
          </ParamRow>
          <ParamRow name="HIGH" type="~21k vertices">
            Hero renders and presentations.
          </ParamRow>
          <ParamRow name="EXPORT" type="~83k vertices">
            What STL and CAD exports use.
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="how" title="Exporting">
        <CodeTabs
          tabs={[
            {
              label: "Python",
              lang: "python",
              code: `from cascade.geometry import (
    impeller_mesh, MeshLOD,
    export_glb, export_stl, export_obj,
    export_turbogrid_ndf,
    export_step, export_iges,        # cascade[cad] only
)

mesh = impeller_mesh(
    geometry=geom,                   # your CentrifugalCompressorGeometry
    lod=MeshLOD.EXPORT,
    with_splitter=True,
    with_back_face=True,
)
export_stl(mesh, "impeller.stl")
export_glb(mesh, "impeller.glb")
export_turbogrid_ndf(mesh, geom, "impeller.ndf")
export_step(mesh, "impeller.step")   # raises cleanly without cascade[cad]`,
            },
            {
              label: "HTTP",
              lang: "http",
              code: `GET /api/projects/{id}/candidates/{cid}/export.glb
GET /api/projects/{id}/candidates/{cid}/export.stl
GET /api/projects/{id}/candidates/{cid}/export.step
GET /api/projects/{id}/candidates/{cid}/export.iges
GET /api/projects/{id}/candidates/{cid}/export_fluid.step
GET /api/projects/{id}/candidates/{cid}/export_turbogrid.ndf
GET /api/projects/{id}/candidates/_cad/available`,
            },
          ]}
        />
        <p>In the web app, the same exports live on the candidate detail panel in Flow path.</p>
      </Section>

      <Section id="honesty" title="Honesty headers">
        <p>Two response headers keep degraded modes visible instead of silent:</p>
        <ul className="ml-5 list-disc space-y-2">
          <li>
            <code className="font-mono text-[13px]">X-Cascade-Stub: true</code>{" "}
            — returned only when the geometry engine is unavailable in a dev
            environment and a placeholder mesh was served. Real installs
            return <code className="font-mono text-[13px]">false</code>;
            check it if you script downloads.
          </li>
          <li>
            <code className="font-mono text-[13px]">X-Cascade-Warning</code>{" "}
            — set when, e.g., the fluid-volume Boolean operation failed and
            the response fell back to a simpler body. The file is still
            usable; the header tells you what it isn’t.
          </li>
        </ul>
      </Section>

      <Section id="downstream" title="Downstream: CFD and FEA">
        <p>
          Native CFD and full 3D FEA are out of scope by design — Cascade
          ships adapter contracts instead (an OpenFOAM stub and a CalculiX
          adapter; native stress analysis is 2D-axisymmetric disc only). The
          intended flow: design in Cascade → export fluid-volume STEP or
          TurboGrid NDF → mesh and solve in the tool your team already
          trusts. See{" "}
          <Link href="/docs/known-gaps" className="font-medium text-brand-text hover:underline">
            Known gaps
          </Link>{" "}
          for the scope rationale.
        </p>
      </Section>
    </DocPage>
  );
}
