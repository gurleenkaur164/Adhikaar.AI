"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Logo, GovStrip, Chakra } from "@/components/Brand";
import { Icon } from "@/components/Icons";
import { ProfileCard, AgentTrace, SchemeCard, Checklist, DiscoverySection } from "@/components/dashboard";
import { api } from "@/lib/api";
import { LANGS, t, EXAMPLES } from "@/lib/i18n";

export default function Dashboard() {
  const [lang, setLang] = useState("en");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [health, setHealth] = useState(null);
  const [saved, setSaved] = useState(false);

  const tr = t[lang];

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: "down" }));
  }, []);

  async function run() {
    if (!text.trim()) return;
    setLoading(true);
    setError("");
    setSaved(false);
    try {
      const res = await api.process(text, lang);
      setResult(res);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  // re-run when language changes so scheme/doc labels re-localize
  useEffect(() => {
    if (result && !loading) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  async function save() {
    if (!result) return;
    try {
      await api.saveApplication({
        citizen_name: result.profile.name,
        raw_input: text,
        profile: result.profile,
        matched_schemes: result.matches,
        language: lang,
      });
      setSaved(true);
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  function reset() {
    setText("");
    setResult(null);
    setError("");
    setSaved(false);
  }

  const eligible = result?.matches.filter((m) => m.status === "eligible") || [];
  const likely = result?.matches.filter((m) => ["likely", "review"].includes(m.status)) || [];

  return (
    <div>
      <GovStrip />

      {/* Header */}
      <header className="no-print border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-3">
          <Link href="/">
            <Logo />
          </Link>
          <div className="flex items-center gap-3">
            {health && (
              <span className="hidden items-center gap-2 rounded-md border border-line bg-canvas px-3 py-1.5 text-xs font-medium text-ink-soft sm:inline-flex">
                <span className={`h-1.5 w-1.5 rounded-full ${health.status === "ok" ? "bg-india-green" : "bg-red-500"}`} />
                {/* Two counts, never one total. "1,988 schemes" would imply
                    the service can rule on all of them — it can rule on 22. */}
                {health.status === "ok"
                  ? `${health.extraction_mode === "groq" ? "Llama 3" : "Rule-based"} · ${
                      health.schemes_verified ?? health.schemes_loaded
                    } verified${
                      health.schemes_discovery
                        ? ` · ${health.schemes_discovery.toLocaleString("en-IN")} to search`
                        : ""
                    }`
                  : "API offline"}
              </span>
            )}
            <div className="flex overflow-hidden rounded-md border border-line bg-white">
              {LANGS.map((l) => (
                <button
                  key={l.code}
                  onClick={() => setLang(l.code)}
                  className={`px-3 py-1.5 text-sm font-medium transition ${
                    lang === l.code ? "bg-ashoka text-white" : "text-ink-soft hover:bg-canvas"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        <div className="no-print mb-6">
          <h1 className="text-xl font-bold text-ashoka-900">Operator Console</h1>
          <p className="text-sm text-ink-soft">{tr.tagline}</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
          {/* Left: input */}
          <div className="no-print space-y-4">
            <div className="gcard overflow-hidden">
              <div className="tricolour-line" />
              <div className="p-5">
                <div className="mb-3 flex items-center gap-2">
                  <Icon.User className="h-5 w-5 text-ashoka" />
                  <h2 className="font-semibold text-ashoka-900">{tr.entryTitle}</h2>
                </div>
                <p className="mb-3 text-sm text-ink-soft">{tr.entryHint}</p>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run();
                  }}
                  rows={5}
                  placeholder="e.g. 45 year old widow, BPL, lives in a village…"
                  className="w-full resize-y rounded-md border border-line bg-white p-3 text-sm text-ink outline-none transition placeholder:text-ink-soft/60 focus:border-ashoka focus:ring-2 focus:ring-ashoka/15"
                />
                <div className="mt-3 flex items-center gap-3">
                  <button
                    onClick={run}
                    disabled={loading || !text.trim()}
                    className="inline-flex flex-1 items-center justify-center gap-2 rounded-md bg-saffron px-5 py-2.5 font-semibold text-ashoka-900 transition hover:bg-saffron-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {loading ? (
                      <>
                        <Chakra size={18} spin className="text-ashoka-900" />
                        {tr.analyzing}
                      </>
                    ) : (
                      <>
                        <Icon.Bolt className="h-5 w-5" /> {tr.analyze}
                      </>
                    )}
                  </button>
                  {result && (
                    <button onClick={reset} className="rounded-md border border-line bg-white px-4 py-2.5 text-sm font-medium text-ashoka hover:bg-canvas">
                      {tr.reset}
                    </button>
                  )}
                </div>
                {error && <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
              </div>
            </div>

            <div className="gcard p-5">
              <div className="mb-2 text-sm font-semibold text-ink-soft">{tr.examples}</div>
              <div className="space-y-2">
                {EXAMPLES.map((ex, i) => (
                  <button
                    key={i}
                    onClick={() => setText(ex)}
                    className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-left text-sm text-ink transition hover:border-ashoka/40 hover:bg-white"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Right: results */}
          <div className="space-y-5">
            {!result && !loading && (
              <div className="gcard grid min-h-[320px] place-items-center p-10 text-center">
                <div>
                  <div className="mx-auto grid h-16 w-16 place-items-center rounded-full border-4 border-canvas-2 text-ashoka">
                    <Chakra size={44} className="text-ashoka" />
                  </div>
                  <p className="mt-4 text-ink-soft">{tr.empty}</p>
                </div>
              </div>
            )}

            {loading && (
              <div className="gcard grid min-h-[320px] place-items-center p-10 text-center">
                <div className="flex items-center gap-3 text-ink-soft">
                  <Chakra size={22} spin className="text-ashoka" />
                  {tr.analyzing}
                </div>
              </div>
            )}

            {result && !loading && (
              <>
                <ProfileCard profile={result.profile} summary={result.summary} tr={tr} />

                {eligible.length > 0 && (
                  <section>
                    <h3 className="mb-3 flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-india-green-600">
                      <Icon.Check className="h-4 w-4" /> {tr.eligible} · {eligible.length}
                    </h3>
                    <div className="grid gap-4 sm:grid-cols-2">
                      {eligible.map((s) => (
                        <SchemeCard key={s.scheme_id} scheme={s} tr={tr} />
                      ))}
                    </div>
                  </section>
                )}

                <Checklist checklist={result.checklist} tr={tr} />

                {likely.length > 0 && (
                  <section>
                    <h3 className="mb-3 text-sm font-bold uppercase tracking-wide text-saffron-700">
                      {tr.likely} · {likely.length}
                    </h3>
                    <div className="grid gap-4 sm:grid-cols-2">
                      {likely.map((s) => (
                        <SchemeCard key={s.scheme_id} scheme={s} tr={tr} />
                      ))}
                    </div>
                  </section>
                )}

                {/* Tier 2. Placed after every verified result and after the
                    checklist, so leads can never be mistaken for the decisions
                    above them. DiscoverySection carries its own warning and is
                    no-print — the printed checklist is what the citizen acts
                    on, and only verified schemes belong on it. */}
                <DiscoverySection discovery={result.discovery} tr={tr} />

                <AgentTrace trace={result.trace} tr={tr} />

                <div className="no-print flex items-center gap-3">
                  <button
                    onClick={save}
                    disabled={saved}
                    className="inline-flex items-center gap-2 rounded-md bg-ashoka px-5 py-2.5 font-semibold text-white transition hover:bg-ashoka-700 disabled:opacity-60"
                  >
                    <Icon.Check className="h-5 w-5" /> {saved ? tr.saved : tr.save}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
