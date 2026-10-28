import { Link, useLocation } from "react-router-dom";
import { Layout } from "./Layout";
import { useApp } from "../lib/context";

export function loginPath(next: string) {
  return `/login?next=${encodeURIComponent(next)}`;
}

export function RequireMember({
  children,
  title,
  message,
}: {
  children: React.ReactNode;
  title: string;
  message: string;
}) {
  const { isMember, memberLoading } = useApp();
  const location = useLocation();
  const next = `${location.pathname}${location.search}`;

  if (memberLoading) {
    return (
      <Layout>
        <p className="text-sm text-ayun-muted">Checking your session…</p>
      </Layout>
    );
  }

  if (!isMember) {
    return (
      <Layout>
        <div className="card-panel mx-auto max-w-md text-center">
          <h1 className="page-title mb-3">{title}</h1>
          <p className="mb-6 text-sm text-ayun-muted">{message}</p>
          <Link to={loginPath(next)} className="btn-primary">
            Sign in to continue
          </Link>
        </div>
      </Layout>
    );
  }

  return <>{children}</>;
}
