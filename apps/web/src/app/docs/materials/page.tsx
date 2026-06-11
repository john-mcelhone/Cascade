import type { Metadata } from "next";
import { CodeTabs, DocPage, ParamRow, ParamTable } from "@/components/docs";
import { Callout, Section } from "@/components/learn/content";

export const metadata: Metadata = { title: "Materials database" };

export default function MaterialsPage() {
  return (
    <DocPage slug="materials">
      <Section id="what" title="What ships">
        <p>
          Ten alloys that cover the microturbine-class design space, each
          with temperature-dependent property tables and a stated source —
          because a yield strength without a temperature and a citation is a
          rumor, not a property:
        </p>
        <div className="flex flex-wrap gap-1.5">
          {[
            "Inconel 625",
            "Inconel 718",
            "Inconel 738",
            "MAR-M 247",
            "Haynes 282",
            "A286",
            "17-4PH",
            "AISI 4340",
            "316L",
            "Ti-6Al-4V",
          ].map((m) => (
            <span
              key={m}
              className="rounded-sm border border-border-subtle bg-surface-subtle px-2 py-0.5 font-mono text-xs text-text-subtle"
            >
              {m}
            </span>
          ))}
        </div>
        <ParamTable title="Properties per material">
          <ParamRow name="density / E(T) / sigma_y(T) / UTS(T)" type="mechanical">
            Density, Young’s modulus, yield, and ultimate strength — the
            rotor model and disc stress checks draw from these.
          </ParamRow>
          <ParamRow name="alpha(T) / k(T) / cp(T)" type="thermal">
            Expansion coefficient, conductivity, and specific heat as
            temperature tables.
          </ParamRow>
          <ParamRow name="source / notes" type="provenance">
            Where each table came from, in the record itself.
          </ParamRow>
        </ParamTable>
      </Section>

      <Section id="access" title="Looking up properties">
        <CodeTabs
          tabs={[
            {
              label: "Python",
              lang: "python",
              code: `from cascade.materials import MaterialDB

inco = MaterialDB.get("INCONEL_718")
for T in (300, 700, 900):
    print(f"T={T} K  E={inco.E(T=T)/1e9:6.1f} GPa  "
          f"σ_y={inco.sigma_y(T=T)/1e6:6.0f} MPa")`,
            },
            {
              label: "HTTP",
              lang: "http",
              code: `GET /api/materials                 # all records (?family= to filter)
GET /api/materials/_/families      # the family names
GET /api/materials/INCONEL_718     # full temperature tables`,
            },
          ]}
        />
      </Section>

      <Section id="where-used" title="Where the database is used">
        <p>
          Rotor sections reference materials by name (
          <code className="font-mono text-[13px]">{`material="STEEL_AISI4340"`}</code>),
          which supplies density and elastic properties to the beam-FEM —
          optionally evaluated at an operating temperature per section. The
          material picker in the web app reads the same records, so the UI
          and a script can never disagree about what Inconel 718 does at
          900 K.
        </p>
        <Callout kind="note">
          Need an alloy that isn’t here? Property tables with sources are an
          easy, high-value contribution — the record format is visible in
          any <code className="font-mono text-[13px]">GET /api/materials/{"{name}"}</code>{" "}
          response.
        </Callout>
      </Section>
    </DocPage>
  );
}
