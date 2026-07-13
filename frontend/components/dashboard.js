"use client";
import { Icon } from "./Icons";

const STATUS_STYLES = {
  eligible: "border-india-green/40 bg-india-green/10 text-india-green-600",
  likely: "border-saffron/50 bg-saffron/10 text-saffron-600",
  review: "border-saffron/50 bg-saffron/10 text-saffron-600",
  not_eligible: "border-red-300 bg-red-50 text-red-600",
};
const STATUS_LABEL = { eligible: "Eligible", likely: "Likely", review: "Review", not_eligible: "Not eligible" };

export function StatusBadge({ status }) {
  return (
    <span className={`shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLES[status] || STATUS_STYLES.review}`}>
      {STATUS_LABEL[status] || status}
    </span>
  );
}

const FIELD_LABELS = {
  name: "Name", age: "Age", gender: "Gender", annual_income: "Annual income",
  occupation: "Occupation", category: "Category", state: "State", area: "Area",
  is_bpl: "BPL", disability_percent: "Disability", marital_status: "Marital status",
  is_student: "Student", land_holding_acres: "Land (acres)", is_pregnant: "Pregnant",
  num_children: "Children",
};

function fmtValue(k, v) {
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (k === "annual_income") return `₹${Number(v).toLocaleString("en-IN")}`;
  if (k === "disability_percent") return `${v}%`;
  if (typeof v === "string") return v.charAt(0).toUpperCase() + v.slice(1);
  return String(v);
}

export function ProfileCard({ profile, summary, tr }) {
  const entries = Object.entries(profile).filter(
    ([k, v]) => v !== null && v !== "" && k !== "flags" && !(Array.isArray(v) && v.length === 0)
  );
  return (
    <div className="gcard overflow-hidden animate-rise">
      <div className="tricolour-line" />
      <div className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Icon.User className="h-5 w-5 text-ashoka" />
          <h3 className="font-semibold text-ashoka-900">{tr.profile}</h3>
          <span className="ml-auto rounded-md border border-line bg-canvas px-2 py-0.5 text-xs font-medium text-ink-soft">
            {summary.extraction_source === "groq" ? "Llama 3" : "Rule-based"} · {Math.round(summary.confidence * 100)}%
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {entries.map(([k, v]) => (
            <div key={k} className="rounded-md border border-line bg-canvas px-3 py-1.5 text-sm">
              <span className="text-ink-soft">{FIELD_LABELS[k] || k}: </span>
              <span className="font-semibold text-ink">{fmtValue(k, v)}</span>
            </div>
          ))}
          {entries.length === 0 && <p className="text-sm text-ink-soft">No details detected yet.</p>}
        </div>
        {summary.missing_fields?.length > 0 && (
          <p className="mt-4 rounded-md border border-saffron/30 bg-saffron/5 px-3 py-2 text-xs text-saffron-600">
            {tr.missing}: {summary.missing_fields.map((f) => FIELD_LABELS[f] || f).join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}

export function AgentTrace({ trace, tr }) {
  return (
    <div className="gcard p-5 animate-rise">
      <div className="mb-4 flex items-center gap-2">
        <Icon.Bolt className="h-5 w-5 text-ashoka" />
        <h3 className="font-semibold text-ashoka-900">{tr.trace}</h3>
      </div>
      <ol className="space-y-3">
        {trace.map((step, i) => (
          <li key={i} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span className="grid h-6 w-6 place-items-center rounded-full bg-ashoka text-xs font-bold text-white">
                {i + 1}
              </span>
              {i < trace.length - 1 && <span className="mt-1 h-full w-px flex-1 bg-line" />}
            </div>
            <div className="pb-1">
              <div className="text-sm font-semibold text-ink">{step.agent}</div>
              <div className="text-xs text-ink-soft">{step.detail}</div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function SchemeCard({ scheme, tr }) {
  return (
    <div className="gcard p-5 transition hover:border-ashoka/30">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="font-semibold leading-snug text-ashoka-900">{scheme.name}</h4>
          <div className="mt-0.5 text-xs text-ink-soft">{scheme.category}</div>
        </div>
        <StatusBadge status={scheme.status} />
      </div>
      <p className="mt-3 text-sm text-ink">
        <span className="font-medium text-ink-soft">{tr.benefit}: </span>
        {scheme.benefit}
      </p>
      {scheme.matched_criteria?.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs font-semibold text-ink-soft">{tr.criteria}</div>
          <div className="flex flex-wrap gap-1.5">
            {scheme.matched_criteria.map((c, i) => (
              <span key={i} className="inline-flex items-center gap-1 rounded-md bg-india-green/10 px-2 py-0.5 text-xs font-medium text-india-green-600">
                <Icon.Check className="h-3 w-3" /> {c}
              </span>
            ))}
            {scheme.failed_criteria?.filter((c) => c.includes("unconfirmed")).map((c, i) => (
              <span key={`u${i}`} className="rounded-md bg-saffron/10 px-2 py-0.5 text-xs text-saffron-600">
                {c}
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-1.5">
        {scheme.documents?.map((d) => (
          <span key={d.key} className="rounded-md border border-line px-2 py-0.5 text-xs text-ink-soft">
            {d.label}
          </span>
        ))}
      </div>
      <a
        href={scheme.official_link}
        target="_blank"
        rel="noreferrer"
        className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-ashoka hover:underline"
      >
        Official portal <Icon.Arrow className="h-3.5 w-3.5" />
      </a>
    </div>
  );
}

export function Checklist({ checklist, tr }) {
  if (!checklist?.items?.length) return null;
  return (
    <div className="gcard overflow-hidden animate-rise">
      <div className="tricolour-line" />
      <div className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <Icon.Doc className="h-5 w-5 text-ashoka" />
          <h3 className="font-semibold text-ashoka-900">{checklist.title}</h3>
          <span className="ml-auto rounded-md border border-line bg-canvas px-2 py-0.5 text-xs font-medium text-ink-soft">
            {checklist.total_documents}
          </span>
          <button
            onClick={() => window.print()}
            className="no-print rounded-md border border-line bg-white px-2 py-0.5 text-xs font-medium text-ashoka hover:bg-canvas"
          >
            {tr.print}
          </button>
        </div>
        <ul className="space-y-2">
          {checklist.items.map((item) => (
            <li key={item.key} className="flex items-start gap-3 rounded-md border border-line bg-canvas px-3 py-2">
              <span className="mt-0.5 grid h-5 w-5 place-items-center rounded border-2 border-india-green/50 text-india-green-600">
                <Icon.Check className="h-3.5 w-3.5" />
              </span>
              <div>
                <div className="text-sm font-semibold text-ink">{item.label}</div>
                <div className="text-xs text-ink-soft">
                  {tr.neededFor}: {item.needed_for.slice(0, 3).join(", ")}
                  {item.needed_for.length > 3 ? ` +${item.needed_for.length - 3}` : ""}
                </div>
              </div>
              <span className="ml-auto rounded-full bg-white px-2 py-0.5 text-xs font-medium text-ink-soft ring-1 ring-line">×{item.count}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
