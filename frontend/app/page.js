import Link from "next/link";
import { Logo, GovStrip, Chakra } from "@/components/Brand";
import { Icon } from "@/components/Icons";

const FEATURES = [
  {
    icon: Icon.User,
    title: "Conversational Data Entry",
    hindi: "बातचीत से डेटा प्रविष्टि",
    body: "Operators type or speak a citizen's details in any language. The system builds a clean, structured profile — no tedious form-filling.",
  },
  {
    icon: Icon.Bolt,
    title: "Two-Tier Scheme Matching",
    hindi: "दो-स्तरीय योजना मिलान",
    body: "22 Central schemes carry hand-verified rules, so the system can state eligibility. A further 1,966 are searchable but never asserted — you get the government's own criteria and a link, and you decide.",
  },
  {
    icon: Icon.Doc,
    title: "Smart Document Checklists",
    hindi: "स्मार्ट दस्तावेज़ सूची",
    body: "Auto-generates a consolidated checklist in Hindi or Punjabi so citizens know exactly what to bring — in a single visit.",
  },
  {
    icon: Icon.Spark,
    title: "Built for Zero-Cost Scale",
    hindi: "शून्य-लागत पर संचालन",
    body: "Runs on a free-tier architecture with a human-in-the-loop design, costing the CSC operator nothing to use.",
  },
];

// Every number here is either an external fact or something this repo
// measures. "10x faster processing" used to sit in this list; nothing
// measured it, so it is gone. "1,000+ schemes" was also ambiguous — it
// described how many schemes exist in India, but read as a product claim.
const STATS = [
  { value: "5.5 Lakh", label: "Common Service Centres in India" },
  { value: "22 + 1,966", label: "Rule-verified + searchable schemes" },
  { value: "0", label: "Hallucinated fields in 170 checks" },
  { value: "₹0", label: "Operational cost" },
];

export default function Landing() {
  return (
    <div>
      <GovStrip />

      {/* App header */}
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
          <Logo />
          <Link
            href="/dashboard"
            className="rounded-md bg-ashoka px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-ashoka-700"
          >
            Open Operator Console
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 pb-20">
        {/* Hero */}
        <section className="grid items-center gap-10 py-14 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="animate-rise">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-line bg-white px-3 py-1 text-xs font-medium text-ashoka">
              <span className="h-1.5 w-1.5 rounded-full bg-india-green" />
              Build for Bharat · Agentic AI
            </div>
            <h1 className="text-4xl font-extrabold leading-[1.12] tracking-tight text-ashoka-900 sm:text-5xl">
              Delivering welfare schemes to every citizen,{" "}
              <span className="text-saffron-700">at the last mile.</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg text-ink-soft">
              Adhikar.AI is an agentic copilot for Common Service Centre operators. It reads a
              citizen's details, identifies every government scheme they are entitled to, and prints
              a localized document checklist — in seconds.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/dashboard"
                className="group inline-flex items-center gap-2 rounded-md bg-saffron px-6 py-3 font-semibold text-ashoka-900 shadow-sm transition hover:bg-saffron-600 hover:text-white"
              >
                Launch the Console
                <Icon.Arrow className="h-5 w-5 transition group-hover:translate-x-0.5" />
              </Link>
              <a
                href="#how"
                className="rounded-md border border-line bg-white px-6 py-3 font-medium text-ashoka transition hover:bg-canvas"
              >
                How it works
              </a>
            </div>
          </div>

          {/* Emblem panel */}
          <div className="gcard relative overflow-hidden p-8 text-center animate-rise">
            <div className="tricolour-line absolute inset-x-0 top-0" />
            <div className="mx-auto grid h-24 w-24 place-items-center rounded-full border-4 border-ashoka/15 text-ashoka">
              <Chakra size={72} className="text-ashoka" />
            </div>
            <div className="mt-4 text-sm font-semibold uppercase tracking-wide text-ink-soft">
              सत्यमेव जयते
            </div>
            <p className="mt-2 text-lg font-bold text-ashoka-900">
              Digital access to entitlements
            </p>
            <p className="mt-1 text-sm text-ink-soft">
              Empowering Village-Level Entrepreneurs across rural India.
            </p>
          </div>
        </section>

        {/* Stats */}
        <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {STATS.map((s) => (
            <div key={s.label} className="gcard p-5 text-center">
              <div className="text-2xl font-extrabold text-ashoka sm:text-3xl">{s.value}</div>
              <div className="mt-1 text-xs font-medium text-ink-soft">{s.label}</div>
            </div>
          ))}
        </section>

        {/* Problem statement */}
        <section className="mt-16 gcard overflow-hidden">
          <div className="tricolour-line" />
          <div className="grid gap-6 p-8 md:grid-cols-3">
            {[
              ["Scheme Complexity", "Citizens are unaware of strict eligibility criteria, leaving allocated welfare funds under-utilised."],
              ["Operator Bottlenecks", "CSC operators are overwhelmed by manual paperwork and error-prone document verification."],
              ["Last-Mile Drop-off", "Even when a scheme is found, citizens abandon it for want of the right prerequisite documents."],
            ].map(([t, b]) => (
              <div key={t}>
                <div className="mb-2 h-1 w-10 rounded bg-saffron" />
                <h3 className="font-semibold text-ashoka-900">{t}</h3>
                <p className="mt-1.5 text-sm text-ink-soft">{b}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Features */}
        <section id="how" className="mt-16">
          <h2 className="text-center text-2xl font-bold text-ashoka-900 sm:text-3xl">
            One operator input. A full application, prepared.
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-ink-soft">
            Six agents — Intake, Extraction, Eligibility, Discovery, Checklist and Synthesis —
            run in a single, traceable pipeline.
          </p>
          <div className="mt-9 grid gap-5 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <div key={f.title} className="gcard p-6 transition hover:border-ashoka/30">
                <div className="grid h-11 w-11 place-items-center rounded-lg bg-canvas-2 text-ashoka">
                  <f.icon className="h-6 w-6" />
                </div>
                <h3 className="mt-4 text-lg font-semibold text-ashoka-900">{f.title}</h3>
                <div className="text-xs font-medium text-saffron-700">{f.hindi}</div>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Pipeline strip */}
        <section className="mt-14 gcard p-7">
          <div className="flex flex-wrap items-center justify-center gap-3 text-sm">
            {[
              "Intake",
              "Extraction (Llama 3)",
              "Eligibility (Rule base)",
              "Discovery (Search)",
              "Checklist (Localized)",
              "Synthesis",
            ].map(
              (step, i, arr) => (
                <span key={step} className="flex items-center gap-3">
                  <span className="rounded-md border border-line bg-canvas px-3 py-2 font-medium text-ashoka">
                    {step}
                  </span>
                  {i < arr.length - 1 && <Icon.Arrow className="h-4 w-4 text-saffron-700" />}
                </span>
              )
            )}
          </div>
        </section>
      </main>

      {/* Official footer */}
      <footer className="border-t border-line bg-white">
        <div className="tricolour-line" />
        <div className="mx-auto max-w-7xl px-6 py-8 text-sm text-ink-soft">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Logo compact />
            <p className="max-w-md text-xs">
              An assistive tool for the theme <em>Build for Bharat & Agentic AI</em>.
              Not an official Government of India service. Built with Next.js, FastAPI, Llama 3 (Groq)
              and PostgreSQL.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
