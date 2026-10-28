import { NavLink, useNavigate } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BookOpen,
  ClipboardCheck,
  ClipboardList,
  Home,
  Ticket,
  User,
  Users,
} from "lucide-react";
import { JouleMark } from "./JouleRunner";
import { hasProblemRating } from "../lib/protocols";
import { useApp } from "../lib/context";
import {
  clearExpertSession,
  expertLogout,
  getExpertName,
  getMemberEmail,
  memberLogout,
} from "../lib/api";

type NavIcon = LucideIcon | "joule";

const memberLinks: Array<{ to: string; label: string; icon: NavIcon; end?: boolean }> = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/profile", label: "Profile", icon: User },
  { to: "/assessment", label: "Assessment", icon: ClipboardList },
  { to: "/plan", label: "Plan", icon: Activity },
  { to: "/ask", label: "Ask Joule", icon: "joule" },
  { to: "/tickets", label: "Ask Expert", icon: Ticket },
];

const expertLinks = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/expert/members", label: "Members", icon: Users },
  { to: "/expert/review", label: "Plan review", icon: ClipboardCheck },
  { to: "/tickets", label: "Tickets", icon: Ticket },
  { to: "/knowledge", label: "Knowledge", icon: BookOpen },
];

function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex shrink-0 items-center ${compact ? "gap-2" : "gap-2.5"}`}>
      <img
        src="/joule-logo.png"
        alt="Joule"
        className={`shrink-0 rounded-[6px] object-cover ${compact ? "h-8 w-8" : "h-9 w-9"}`}
      />
      <span className="hidden text-[10px] font-semibold uppercase tracking-[0.16em] text-ayun-muted xl:inline">for</span>
      <img
        src="/ayun-logo-color.png"
        alt="AYUN"
        className={`hidden w-auto shrink-0 xl:block ${compact ? "h-[26px]" : "h-7"}`}
      />
    </div>
  );
}

export function TopNav() {
  const navigate = useNavigate();
  const {
    activeMode,
    setActiveMode,
    isExpert,
    setIsExpert,
    isMember,
    clearMember,
    assessment,
  } = useApp();
  const expertName = getExpertName();
  const memberEmail = getMemberEmail();
  const links = activeMode === "expert" ? expertLinks : memberLinks;
  const planCount =
    assessment && activeMode === "member" && hasProblemRating(assessment.ratings)
      ? assessment.triggered.length
      : 0;

  async function signOutExpert() {
    try {
      await expertLogout();
    } catch {
      /* clear local session anyway */
    }
    clearExpertSession();
    setIsExpert(false);
    setActiveMode("member");
  }

  async function signOutMember() {
    try {
      await memberLogout();
    } catch {
      /* clear local session anyway */
    }
    clearMember();
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/70 bg-white/72 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-5 md:px-6">
        <BrandLockup />

        <nav className="hidden min-w-0 flex-1 overflow-x-auto [scrollbar-width:none] md:flex">
          <div className="mx-auto flex w-max items-center gap-1 lg:gap-2">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={label}
              className={({ isActive }) =>
                `relative flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-2 text-[13px] font-medium transition lg:px-3 ${
                  isActive ? "text-ayun-dark" : "text-ayun-muted hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {Icon === "joule" ? (
                    <JouleMark size={15} />
                  ) : (
                    <Icon className="h-3.5 w-3.5 shrink-0" />
                  )}
                  <span className="hidden lg:inline">{label}</span>
                  {to === "/plan" && planCount > 0 && (
                    <span title={`${planCount} recommendations`} className="ml-0.5 rounded-full bg-ayun-green px-1.5 text-[10px] font-semibold leading-4 text-white">
                      {planCount}
                    </span>
                  )}
                  {isActive && (
                    <span className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-ayun-green lg:left-3 lg:right-3" />
                  )}
                </>
              )}
            </NavLink>
          ))}
          </div>
        </nav>

        <div className="flex shrink-0 items-center gap-2 text-right text-xs text-ayun-muted sm:gap-3">
          <div className="flex rounded-md border border-rule bg-ayun-light/40 p-0.5">
            <button
              type="button"
              className={`rounded px-2 py-1 text-[11px] font-medium transition ${
                activeMode === "member" ? "bg-white text-ayun-dark shadow-sm" : "hover:text-ink"
              }`}
              onClick={() => setActiveMode("member")}
            >
              Member
            </button>
            <button
              type="button"
              className={`rounded px-2 py-1 text-[11px] font-medium transition ${
                activeMode === "expert" ? "bg-white text-ayun-dark shadow-sm" : "hover:text-ink"
              } ${!isExpert ? "opacity-60" : ""}`}
              onClick={() => {
                if (!isExpert) {
                  navigate("/login?tab=expert");
                  return;
                }
                setActiveMode("expert");
              }}
            >
              Expert
            </button>
          </div>

          {activeMode === "expert" ? (
            <button type="button" className="btn-secondary !px-3 !py-1.5 !text-xs" onClick={signOutExpert}>
              <span className="hidden xl:inline">{expertName || "Clinician"} · </span>Sign out
            </button>
          ) : isMember ? (
            <button type="button" className="btn-secondary !px-3 !py-1.5 !text-xs" onClick={signOutMember}>
              <span className="hidden xl:inline">{memberEmail?.split("@")[0] || "Member"} · </span>Sign out
            </button>
          ) : (
            <NavLink to="/login" className="btn-secondary !px-3 !py-1.5 !text-xs">
              Sign in
            </NavLink>
          )}
        </div>
      </div>
    </header>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
    </div>
  );
}

export { BrandLockup };
