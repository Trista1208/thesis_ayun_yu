import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, Search, ExternalLink } from "lucide-react";
import { Layout } from "../components/Layout";
import { useApp } from "../lib/context";
import {
  deleteKnowledgeNode,
  deleteKnowledgeQa,
  fetchEvipediaCatalog,
  fetchKnowledgeNodes,
  fetchKnowledgeProtocols,
  fetchKnowledgeSearch,
  fetchKnowledgeStats,
  fetchKnowledgeValidatedQa,
  fetchEvipediaMatch,
  type EvipediaReference,
  type KnowledgeSearchHit,
  type KnowledgeProtocol,
  type Ticket,
} from "../lib/api";

function ProtocolCard({ protocol }: { protocol: KnowledgeProtocol }) {
  const training = Object.entries(protocol.training || {});
  const lists = [
    ["Exercises", protocol.exercises],
    ["Structure", protocol.structure],
    ["Zones", protocol.zones],
    ["Tips", protocol.tips],
    ["Nutrition", protocol.nutrition_focus],
  ] as const;
  return (
    <details className="card-panel group">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-ayun-green/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-ayun-dark">
            {protocol.kind === "condition_protocol" ? "Condition protocol" : "Workout template"}
          </span>
          <h3 className="font-serif text-lg text-ink">{protocol.title}</h3>
        </div>
        {protocol.description ? (
          <p className="mt-2 text-sm text-ayun-muted">{protocol.description}</p>
        ) : null}
        <p className="mt-2 text-xs font-medium text-ayun-green group-open:hidden">Open protocol</p>
      </summary>
      <div className="mt-4 border-t border-rule pt-4 text-sm">
        {training.length ? (
          <dl className="grid gap-2 sm:grid-cols-2">
            {training.map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs font-semibold uppercase tracking-wide text-ayun-muted">
                  {label.replace(/_/g, " ")}
                </dt>
                <dd className="mt-0.5 text-ink">
                  {Array.isArray(value) ? value.join(" · ") : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
        {lists.map(([label, values]) =>
          values?.length ? (
            <div key={label} className="mt-4">
              <p className="font-semibold text-ink">{label}</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-ayun-muted">
                {values.map((value) => (
                  <li key={value}>{value}</li>
                ))}
              </ul>
            </div>
          ) : null,
        )}
        {protocol.related_templates?.length ? (
          <div className="mt-4">
            <p className="font-semibold text-ink">Related workout templates</p>
            <ul className="mt-1 space-y-1 text-ayun-muted">
              {protocol.related_templates.map((template) => (
                <li key={template.key}>
                  <span className="font-medium text-ink">{template.title}</span>
                  {template.description ? ` — ${template.description}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {protocol.recheck_interval ? (
          <p className="mt-4 text-ayun-muted">
            <span className="font-semibold text-ink">Recheck:</span> {protocol.recheck_interval}
          </p>
        ) : null}
        <p className="mt-4 text-xs text-ayun-muted">Source: {protocol.source}</p>
      </div>
    </details>
  );
}

export function KnowledgePage() {
  const { isExpert, activeMode } = useApp();
  const expertView = isExpert && activeMode === "expert";
  const [stats, setStats] = useState<Record<string, number | string> | null>(null);
  const [nodes, setNodes] = useState<Array<{
    id: string;
    title: string;
    category: string;
    summary: string;
    captured_by: string;
    created_at: string;
  }>>([]);
  const [validatedQa, setValidatedQa] = useState<Ticket[]>([]);
  const [protocols, setProtocols] = useState<KnowledgeProtocol[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [searchMode, setSearchMode] = useState<string>("");
  const [searchResults, setSearchResults] = useState<KnowledgeSearchHit[]>([]);
  const [searchTotal, setSearchTotal] = useState(0);
  const [evipediaRefs, setEvipediaRefs] = useState<EvipediaReference[]>([]);
  const [evipediaSearchQuery, setEvipediaSearchQuery] = useState("");
  const [evipediaSearchLoading, setEvipediaSearchLoading] = useState(false);
  const [evipediaSearchMode, setEvipediaSearchMode] = useState("");
  const [evipediaSearchResults, setEvipediaSearchResults] = useState<EvipediaReference[]>([]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [s, n, qa, evipedia, protocolResult] = await Promise.all([
        fetchKnowledgeStats(),
        fetchKnowledgeNodes(),
        fetchKnowledgeValidatedQa(),
        fetchEvipediaCatalog(),
        fetchKnowledgeProtocols()
          .then((resp) => ({ protocols: resp.protocols || [], error: "" }))
          .catch((err) => ({
            protocols: [] as KnowledgeProtocol[],
            error: err instanceof Error ? err.message : "Could not load AYUN protocols",
          })),
      ]);
      setStats(s);
      setNodes(n.nodes);
      setValidatedQa(qa.tickets);
      setEvipediaRefs(evipedia.references);
      setProtocols(protocolResult.protocols);
      if (protocolResult.error) {
        setError(protocolResult.error);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load knowledge base");
      setStats(null);
      setNodes([]);
      setValidatedQa([]);
      setEvipediaRefs([]);
      setProtocols([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!expertView) {
      setLoading(false);
      return;
    }
    loadAll();
  }, [expertView, loadAll]);

  useEffect(() => {
    if (!expertView) return;
    const q = searchQuery.trim();
    if (!q) {
      setSearchResults([]);
      setSearchTotal(0);
      setSearchMode("");
      setSearchError("");
      setSearchLoading(false);
      return;
    }

    setSearchLoading(true);
    setSearchError("");
    const timer = window.setTimeout(() => {
      fetchKnowledgeSearch(q)
        .then((resp) => {
          setSearchResults(resp.results);
          setSearchTotal(resp.total);
          setSearchMode(resp.mode);
        })
        .catch((err) => {
          setSearchError(err instanceof Error ? err.message : "Search failed");
          setSearchResults([]);
          setSearchTotal(0);
        })
        .finally(() => setSearchLoading(false));
    }, 300);

    return () => window.clearTimeout(timer);
  }, [expertView, searchQuery]);

  useEffect(() => {
    if (!expertView) return;
    const q = evipediaSearchQuery.trim();
    if (!q) {
      setEvipediaSearchResults([]);
      setEvipediaSearchMode("");
      setEvipediaSearchLoading(false);
      return;
    }

    setEvipediaSearchLoading(true);
    const timer = window.setTimeout(() => {
      fetchEvipediaMatch(q, "", 12)
        .then((resp) => {
          setEvipediaSearchResults(resp.matches);
          setEvipediaSearchMode(resp.mode);
        })
        .catch(() => {
          setEvipediaSearchResults([]);
          setEvipediaSearchMode("");
        })
        .finally(() => setEvipediaSearchLoading(false));
    }, 300);

    return () => window.clearTimeout(timer);
  }, [expertView, evipediaSearchQuery]);

  async function onDeleteNode(nodeId: string) {
    if (!window.confirm("Delete this knowledge node from the library?")) return;
    setDeletingId(`node:${nodeId}`);
    setMessage("");
    try {
      await deleteKnowledgeNode(nodeId);
      setMessage("Knowledge node deleted.");
      loadAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not delete node");
    } finally {
      setDeletingId(null);
    }
  }

  async function onDeleteQa(ticketId: string) {
    if (!window.confirm("Remove this Q&A from the knowledge library? The ticket returns to draft status.")) {
      return;
    }
    setDeletingId(`qa:${ticketId}`);
    setMessage("");
    try {
      await deleteKnowledgeQa(ticketId);
      setMessage("Validated Q&A removed from the knowledge library.");
      loadAll();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not delete Q&A");
    } finally {
      setDeletingId(null);
    }
  }

  const browsing = !searchQuery.trim();

  if (!expertView) {
    return (
      <Layout>
        <div className="card-panel text-center text-sm text-ayun-muted">
          <p>The knowledge library is for AYUN clinicians only.</p>
          <Link to="/login?tab=expert" className="btn-primary mt-4 inline-flex">
            Sign in as expert
          </Link>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <p className="label-eyebrow mb-2">Validated corpus</p>
      <h1 className="page-title mb-2">Knowledge library</h1>
      <p className="mb-6 max-w-2xl text-sm text-ayun-muted">
        Search AYUN scientist protocols, validated member Q&A, captured clinical knowledge, and curated{" "}
        <a href="https://evipedia.ai" target="_blank" rel="noreferrer" className="text-ayun-green underline">
          evipedia.ai
        </a>{" "}
        evidence reviews. evipedia links support clinician judgment and do not change member plans automatically.
      </p>

      <div className="relative mb-8 max-w-2xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ayun-muted" />
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Semantic knowledge search · e.g. zone 2, fatty liver, bone density"
          className="w-full rounded-xl border border-rule bg-white py-3 pl-10 pr-4 text-sm shadow-sm outline-none transition focus:border-ayun-green focus:ring-2 focus:ring-ayun-green/20"
        />
        {searchLoading && (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-ayun-green" />
        )}
      </div>

      {message ? (
        <p className="mb-4 rounded-lg bg-ayun-light px-4 py-3 text-sm text-ayun-dark">{message}</p>
      ) : null}

      {!browsing && (
        <section className="mb-10">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <h2 className="font-serif text-2xl text-ink">Search results</h2>
            {!searchLoading && searchMode && (
              <span className="rounded-full bg-ayun-light px-2.5 py-0.5 text-xs font-medium text-ayun-dark">
                {searchMode === "semantic" ? "Semantic match" : "Keyword match"}
                {searchTotal > 0 ? ` · ${searchTotal} found` : ""}
              </span>
            )}
          </div>
          {searchError ? (
            <div className="card-panel text-sm text-red-700">{searchError}</div>
          ) : searchLoading ? (
            <div className="card-panel flex items-center gap-2 text-sm text-ayun-muted">
              <Loader2 className="h-4 w-4 animate-spin text-ayun-green" />
              Searching…
            </div>
          ) : searchResults.length === 0 ? (
            <div className="card-panel text-sm text-ayun-muted">
              No matches for &ldquo;{searchQuery.trim()}&rdquo;. Try broader terms like exercise, VO2max,
              or bone health.
            </div>
          ) : (
            <div className="space-y-3">
              {searchResults.map((hit) => {
                const rawId = hit.id.includes(":") ? hit.id.split(":")[1] : hit.id;
                return (
                  <article key={hit.id} className="card-panel">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-ayun-light px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-ayun-dark">
                            {hit.kind === "qa"
                              ? "Validated Q&A"
                              : hit.kind === "protocol"
                                ? "AYUN protocol"
                              : hit.kind === "evipedia"
                                ? "evipedia review"
                                : "Knowledge node"}
                          </span>
                          <span className="rounded-full border border-rule px-2 py-0.5 text-xs text-ayun-muted">
                            {hit.category}
                          </span>
                          <span className="text-xs text-ayun-muted">
                            {Math.round(hit.score * 100)}% match
                            {hit.match_mode ? ` · ${hit.match_mode}` : ""}
                          </span>
                        </div>
                        <p className="mt-2 text-sm font-medium text-ink">{hit.title}</p>
                        <p className="mt-2 text-sm text-ayun-muted">{hit.snippet}</p>
                        {hit.kind === "evipedia" && hit.url ? (
                          <a
                            href={hit.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-2 inline-flex items-center gap-1 text-sm text-ayun-green underline"
                          >
                            Open on evipedia.ai
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        ) : null}
                        <p className="mt-2 text-xs text-ayun-muted">
                          {hit.kind === "qa" && hit.validated_by
                            ? `Validated by ${hit.validated_by}`
                            : hit.captured_by
                              ? `Captured by ${hit.captured_by}`
                              : null}
                          {hit.created_at ? ` · ${new Date(hit.created_at).toLocaleString()}` : ""}
                        </p>
                      </div>
                      {hit.kind === "qa" ? (
                        <button
                          type="button"
                          className="btn-secondary !px-3 !py-1.5 !text-xs !text-red-700 !border-red-200 hover:!bg-red-50"
                          disabled={deletingId === `qa:${rawId}`}
                          onClick={() => onDeleteQa(rawId)}
                        >
                          {deletingId === `qa:${rawId}` ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            "Delete"
                          )}
                        </button>
                      ) : hit.kind === "node" ? (
                        <button
                          type="button"
                          className="btn-secondary !px-3 !py-1.5 !text-xs !text-red-700 !border-red-200 hover:!bg-red-50"
                          disabled={deletingId === `node:${rawId}`}
                          onClick={() => onDeleteNode(rawId)}
                        >
                          {deletingId === `node:${rawId}` ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            "Delete"
                          )}
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}

      {loading ? (
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-ayun-green" />
      ) : error ? (
        <div className="card-panel text-sm text-red-700">{error}</div>
      ) : browsing ? (
        <>
          {stats && (
            <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {[
                ["AYUN protocols", protocols.length],
                ["Nodes", stats.nodes],
                ["All questions", stats.tickets_total ?? stats.tickets_open],
                ["Open", stats.tickets_open],
                ["Awaiting", stats.tickets_answered],
                ["Validated Q&A", stats.tickets_validated],
              ].map(([label, val]) => (
                <div key={String(label)} className="card-panel !p-4 text-center">
                  <p className="label-eyebrow">{label}</p>
                  <p className="mt-1 font-serif text-3xl text-ayun-dark">{val}</p>
                </div>
              ))}
            </div>
          )}

          <section className="mb-10">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="font-serif text-2xl text-ink">AYUN scientist protocols</h2>
                <p className="mt-1 max-w-2xl text-sm text-ayun-muted">
                  Official condition protocols and workout templates used to ground automatic plans and
                  expert AI recommendations.
                </p>
              </div>
              <span className="rounded-full bg-ayun-green/10 px-2.5 py-0.5 text-xs font-medium text-ayun-dark">
                {protocols.length} protocols & templates
              </span>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              {protocols.map((protocol) => (
                <ProtocolCard key={`${protocol.kind}:${protocol.key}`} protocol={protocol} />
              ))}
              {protocols.length === 0 ? (
                <div className="card-panel text-sm text-ayun-muted lg:col-span-2">
                  No AYUN protocols are available.
                </div>
              ) : null}
            </div>
          </section>

          <section className="mb-10">
            <h2 className="mb-4 font-serif text-2xl text-ink">Validated member Q&A</h2>
            <div className="space-y-3">
              {validatedQa.length === 0 && (
                <div className="card-panel text-sm text-ayun-muted">No validated Q&A yet.</div>
              )}
              {validatedQa.map((t) => (
                <article key={t.id} className="card-panel">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-mono text-ayun-muted">{t.id}</p>
                      <p className="mt-2 text-sm font-medium text-ink">{t.question}</p>
                      <p className="mt-3 text-sm text-ayun-muted">{t.draft_answer}</p>
                      <p className="mt-2 text-xs text-ayun-muted">
                        {t.from_name ? `${t.from_name} · ` : ""}
                        {t.validated_by ? `Validated by ${t.validated_by}` : ""}
                        {t.updated_at ? ` · ${new Date(t.updated_at).toLocaleString()}` : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn-secondary !px-3 !py-1.5 !text-xs !text-red-700 !border-red-200 hover:!bg-red-50"
                      disabled={deletingId === `qa:${t.id}`}
                      onClick={() => onDeleteQa(t.id)}
                    >
                      {deletingId === `qa:${t.id}` ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        "Delete"
                      )}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="mb-10">
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="font-serif text-2xl text-ink">Evidence references (evipedia)</h2>
                <p className="mt-1 max-w-2xl text-sm text-ayun-muted">
                  Curated links to Forever Healthy evidence reviews on{" "}
                  <a href="https://evipedia.ai" target="_blank" rel="noreferrer" className="text-ayun-green underline">
                    evipedia.ai
                  </a>
                  . Semantic search finds relevant reviews by meaning, e.g. &ldquo;keep bones strong&rdquo; matches
                  Vitamin D and resistance training even without exact keywords.
                </p>
              </div>
              <span className="rounded-full bg-ayun-light px-2.5 py-0.5 text-xs font-medium text-ayun-dark">
                {evipediaRefs.length} curated
              </span>
            </div>

            <div className="relative mb-4 max-w-2xl">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ayun-muted" />
              <input
                type="search"
                value={evipediaSearchQuery}
                onChange={(e) => setEvipediaSearchQuery(e.target.value)}
                placeholder="Search evipedia by meaning · e.g. bone health, aging, VO2max"
                className="w-full rounded-xl border border-rule bg-white py-2.5 pl-10 pr-4 text-sm shadow-sm outline-none transition focus:border-ayun-green focus:ring-2 focus:ring-ayun-green/20"
              />
              {evipediaSearchLoading && (
                <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-ayun-green" />
              )}
            </div>

            {evipediaSearchQuery.trim() ? (
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-ayun-light px-2.5 py-0.5 text-xs font-medium text-ayun-dark">
                  {evipediaSearchMode === "semantic"
                    ? "Semantic match"
                    : evipediaSearchMode === "keyword"
                      ? "Keyword match"
                      : "No matches"}
                  {evipediaSearchResults.length > 0 ? ` · ${evipediaSearchResults.length} found` : ""}
                </span>
              </div>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-2">
              {(evipediaSearchQuery.trim() ? evipediaSearchResults : evipediaRefs).map((ref) => (
                <article key={ref.id} className="card-panel !p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-rule px-2 py-0.5 text-xs text-ayun-muted">
                      {ref.category}
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-medium text-ink">{ref.title}</p>
                  <p className="mt-2 text-sm text-ayun-muted line-clamp-2">{ref.summary}</p>
                  {typeof ref.score === "number" ? (
                    <p className="mt-1 text-xs text-ayun-muted">
                      {Math.round(ref.score * 100)}% match
                      {ref.match_mode ? ` · ${ref.match_mode}` : ""}
                    </p>
                  ) : null}
                  <a
                    href={ref.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 inline-flex items-center gap-1 text-sm text-ayun-green underline"
                  >
                    Read review
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </article>
              ))}
              {evipediaSearchQuery.trim() && evipediaSearchResults.length === 0 && !evipediaSearchLoading ? (
                <div className="card-panel text-sm text-ayun-muted sm:col-span-2">
                  No evipedia matches for &ldquo;{evipediaSearchQuery.trim()}&rdquo;. Try broader terms like bone
                  health, aerobic fitness, or metabolic health.
                </div>
              ) : null}
            </div>
          </section>

          <section>
            <h2 className="mb-4 font-serif text-2xl text-ink">Knowledge nodes</h2>
            <div className="space-y-3">
              {nodes.length === 0 && (
                <div className="card-panel text-sm text-ayun-muted">No knowledge captured yet.</div>
              )}
              {nodes.map((n) => (
                <article key={n.id} className="card-panel">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-serif text-lg">{n.title}</h3>
                        <span className="rounded-full bg-ayun-light px-2 py-0.5 text-xs text-ayun-muted">
                          {n.category}
                        </span>
                      </div>
                      <p className="mt-2 text-sm text-ayun-muted line-clamp-3">{n.summary}</p>
                      <p className="mt-2 text-xs text-ayun-muted">
                        {n.captured_by} · {n.created_at}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="btn-secondary !px-3 !py-1.5 !text-xs !text-red-700 !border-red-200 hover:!bg-red-50"
                      disabled={deletingId === `node:${n.id}`}
                      onClick={() => onDeleteNode(n.id)}
                    >
                      {deletingId === `node:${n.id}` ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        "Delete"
                      )}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </Layout>
  );
}
