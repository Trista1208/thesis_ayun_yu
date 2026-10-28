import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Layout } from "../components/Layout";
import {
  expertLogin,
  fetchExpertStatus,
  exchangeGoogleSignIn,
  fetchGoogleAuthStatus,
  fetchMemberMe,
  memberLogin,
  memberRegister,
  setExpertSession,
  setMemberSession,
  startGoogleSignIn,
  claimMemberTickets,
  getGuestTicketIds,
  clearGuestTicketIds,
} from "../lib/api";
import type { AppUser } from "../lib/profileFields";
import { useApp } from "../lib/context";

type Tab = "member" | "expert";

export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { applyMemberUser, restoreMemberAssessment, setIsExpert, setActiveMode } = useApp();

  const initialTab = params.get("tab") === "expert" ? "expert" : "member";
  const [tab, setTab] = useState<Tab>(initialTab);
  const [isRegister, setIsRegister] = useState(false);

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [expertName, setExpertName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [expertConfigured, setExpertConfigured] = useState<boolean | null>(null);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    fetchExpertStatus()
      .then((s) => setExpertConfigured(s.configured))
      .catch(() => setExpertConfigured(null));
    fetchGoogleAuthStatus()
      .then((s) => setGoogleEnabled(s.googleEnabled === true))
      .catch(() => setGoogleEnabled(false));
  }, []);

  async function finishMemberLogin(user: AppUser, token: string) {
    setMemberSession(token, user.email);
    applyMemberUser(user);
    await restoreMemberAssessment();
    const guestIds = getGuestTicketIds();
    if (guestIds.length) {
      try {
        await claimMemberTickets(guestIds);
        clearGuestTicketIds();
      } catch {
        /* tickets still visible via /mine legacy claim on next load */
      }
    }
    setActiveMode("member");
    const fromQuery = params.get("next");
    const fromStore = sessionStorage.getItem("ayun_login_next");
    sessionStorage.removeItem("ayun_login_next");
    const raw = fromQuery || fromStore || "";
    const next = raw.startsWith("/") && !raw.startsWith("//") ? raw : "/profile";
    navigate(next, { replace: true });
  }

  useEffect(() => {
    const google = params.get("google");
    const code = params.get("code");
    const state = params.get("state");
    if (google === "error") {
      setError("Google sign-in could not finish. Try again, or use email.");
      return;
    }
    if (code && state) {
      setLoading(true);
      exchangeGoogleSignIn(code, state)
        .then((resp) => finishMemberLogin(resp.user, resp.token))
        .catch((err) => setError(err instanceof Error ? err.message : "Google sign-in could not finish. Try again, or use email."))
        .finally(() => setLoading(false));
      return;
    }
    if (google !== "ok") return;
    const token = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token");
    if (!token) {
      setError("Google sign-in could not finish. Try again, or use email.");
      return;
    }
    setLoading(true);
    setMemberSession(token, "");
    fetchMemberMe()
      .then((user) => finishMemberLogin(user, token))
      .catch(() => setError("Google sign-in could not finish. Try again, or use email."))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onGoogle() {
    setError("");
    setLoading(true);
    try {
      const next = params.get("next");
      if (next && next.startsWith("/") && !next.startsWith("//")) {
        sessionStorage.setItem("ayun_login_next", next);
      }
      const { url } = await startGoogleSignIn();
      window.location.assign(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google sign-in could not start.");
      setLoading(false);
    }
  }

  async function onMemberSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const resp = isRegister
        ? await memberRegister(email, password, displayName)
        : await memberLogin(email, password);
      await finishMemberLogin(resp.user, resp.token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  }

  async function onExpertSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const resp = await expertLogin(expertName, password);
      setExpertSession(resp.token, resp.name);
      setIsExpert(true);
      setActiveMode("expert");
      const next = params.get("next");
      navigate(next && next.startsWith("/") ? next : "/expert/review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Layout>
      <div className="mx-auto max-w-md">
        <p className="label-eyebrow mb-2">Account</p>
        <h1 className="page-title mb-6">Sign in</h1>

        <div className="mb-6 flex rounded-lg border border-rule bg-ayun-light/40 p-1">
          <button
            type="button"
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
              tab === "member" ? "bg-white text-ayun-dark shadow-sm" : "text-ayun-muted hover:text-ink"
            }`}
            onClick={() => {
              setTab("member");
              setError("");
            }}
          >
            Member
          </button>
          <button
            type="button"
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
              tab === "expert" ? "bg-white text-ayun-dark shadow-sm" : "text-ayun-muted hover:text-ink"
            }`}
            onClick={() => {
              setTab("expert");
              setError("");
            }}
          >
            Expert
          </button>
        </div>

        {tab === "member" ? (
          <>
            <p className="mb-4 text-sm text-ayun-muted">
              Save your assessment data and personal profile so you don&apos;t re-enter it each visit.
            </p>
            <form onSubmit={onMemberSubmit} className="card-panel space-y-4">
              <button
                className="google-sign-in"
                type="button"
                aria-label="Sign in with Google"
                onClick={() => void onGoogle()}
                disabled={!googleEnabled || loading}
              >
                <img src="/brand/google-sign-in.svg" width="180" height="40" alt="" />
              </button>
              {!googleEnabled && (
                <p className="auth-small">Google sign-in is coming soon. You can use email below.</p>
              )}
              <div className="auth-divider">
                <span>or use email</span>
              </div>
              <div>
                <label className="text-sm font-medium">Email</label>
                <input
                  type="email"
                  required
                  className="mt-1 w-full rounded-lg border border-rule px-3 py-2"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              {isRegister && (
                <div>
                  <label className="text-sm font-medium">Display name</label>
                  <input
                    className="mt-1 w-full rounded-lg border border-rule px-3 py-2"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Optional"
                  />
                </div>
              )}
              <div>
                <label className="text-sm font-medium">Password</label>
                <input
                  type="password"
                  required
                  minLength={6}
                  className="mt-1 w-full rounded-lg border border-rule px-3 py-2"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button type="submit" className="btn-primary w-full" disabled={loading}>
                {loading ? "Please wait…" : isRegister ? "Create account" : "Sign in"}
              </button>
              <button
                type="button"
                className="w-full text-sm text-ayun-muted hover:text-ink"
                onClick={() => {
                  setIsRegister(!isRegister);
                  setError("");
                }}
              >
                {isRegister ? "Already have an account? Sign in" : "New here? Create an account"}
              </button>
            </form>
          </>
        ) : (
          <>
            {expertConfigured === false && (
              <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                Expert login is not configured on the server. Contact your admin.
              </div>
            )}
            <form onSubmit={onExpertSubmit} className="card-panel space-y-4">
              <div>
                <label className="text-sm font-medium">Clinician name</label>
                <input
                  className="mt-1 w-full rounded-lg border border-rule px-3 py-2"
                  value={expertName}
                  onChange={(e) => setExpertName(e.target.value)}
                  placeholder="e.g. Manuel"
                  autoComplete="name"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Expert password</label>
                <input
                  type="password"
                  className="mt-1 w-full rounded-lg border border-rule px-3 py-2"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Password"
                  autoComplete="current-password"
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button type="submit" className="btn-primary w-full" disabled={loading}>
                {loading ? "Please wait…" : "Expert sign in"}
              </button>
            </form>
          </>
        )}
      </div>
    </Layout>
  );
}
