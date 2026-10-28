import { Link } from "react-router-dom";
import { ArrowRight, BookOpen, ClipboardCheck, ClipboardList, Ticket, Users } from "lucide-react";
import { JouleMark } from "../components/JouleRunner";
import { BodyAtlas } from "../components/BodyAtlas";
import { Layout } from "../components/Layout";
import { loginPath } from "../components/RequireMember";
import { getExpertName } from "../lib/api";
import { useApp } from "../lib/context";

export function HomePage() {
  const { assessment, memberName, isMember, memberLoading, activeMode, isExpert } = useApp();
  const expertView = activeMode === "expert" && isExpert;
  const expertName = getExpertName();

  const welcomeTitle = expertView
    ? expertName
      ? `Welcome, ${expertName.split(" ")[0]}`
      : "Expert tools"
    : memberName
      ? `Welcome, ${memberName.split(" ")[0]}`
      : "Personalised sport & health plans";

  return (
    <Layout>
      <div className="home">
        <div className="home-stage">
          <div className="home-copy">
            <p className="label-eyebrow">{expertView ? "Expert tools" : "Sport plan"}</p>
            <h1 className="page-title">{welcomeTitle}</h1>
            <p className="home-lede">
              {expertView
                ? "Review member plans, answer tickets, and manage the validated knowledge library."
                : "Exercise recommendations from your health profile — age- and sex-stratified, with AYUN-validated knowledge and Joule alongside."}
            </p>
            <div className="home-actions">
              {expertView ? (
                <>
                  <Link to="/expert/members" className="btn-primary">
                    <Users className="h-4 w-4" />
                    Member profiles
                  </Link>
                  <Link to="/expert/review" className="btn-secondary">
                    <ClipboardCheck className="h-4 w-4" />
                    Plan review
                  </Link>
                  <Link to="/tickets" className="btn-secondary">
                    <Ticket className="h-4 w-4" />
                    Ticket inbox
                  </Link>
                  <Link to="/knowledge" className="btn-secondary">
                    <BookOpen className="h-4 w-4" />
                    Knowledge library
                  </Link>
                </>
              ) : (
                <>
                  <Link
                    to={isMember ? "/assessment" : loginPath("/assessment")}
                    className="btn-primary"
                  >
                    <ClipboardList className="h-4 w-4" />
                    Start assessment
                  </Link>
                  {!isMember && !memberLoading && (
                    <Link to={loginPath("/assessment")} className="btn-secondary">
                      Sign in
                    </Link>
                  )}
                  {assessment && (
                    <Link to="/plan" className="btn-secondary">
                      View plan
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  )}
                  <Link to={isMember ? "/ask" : loginPath("/ask")} className="btn-secondary">
                    <JouleMark size={16} />
                    Ask Joule
                  </Link>
                </>
              )}
            </div>
          </div>

          {expertView ? (
            <div className="card-panel">
              <p className="label-eyebrow mb-4">Expert workflow</p>
              <ol className="space-y-4 text-sm text-ayun-muted">
                <li>
                  <span className="font-semibold text-ink">1. Member profiles</span>: personal context and checkup results
                  from saved assessments
                </li>
                <li>
                  <span className="font-semibold text-ink">2. Plan review</span>: edit preliminary member plans and publish
                  clinician-reviewed versions
                </li>
                <li>
                  <span className="font-semibold text-ink">3. Tickets</span>: answer member questions and validate responses
                </li>
                <li>
                  <span className="font-semibold text-ink">4. Knowledge library</span>: curated Q&A feeds Ask Joule for all
                  members
                </li>
              </ol>
            </div>
          ) : (
            <div className="home-atlas">
              <BodyAtlas />
            </div>
          )}
        </div>

        {!expertView && (
          <section className="home-flow" aria-label="How Joule works">
            <p className="label-eyebrow">How Joule works</p>
            <ol className="home-steps">
              <li>
                <Link to={isMember ? "/profile" : "/login"}>
                  <span>01</span>
                  <p>
                    <strong>Sign in</strong>
                    Create an account to unlock the rest of Joule.
                  </p>
                </Link>
              </li>
              <li>
                <Link to={isMember ? "/profile" : loginPath("/profile")}>
                  <span>02</span>
                  <p>
                    <strong>Create your profile</strong>
                    Add goals and notes, or drop in a clinic report.
                  </p>
                </Link>
              </li>
              <li>
                <Link to={isMember ? "/assessment" : loginPath("/assessment")}>
                  <span>03</span>
                  <p>
                    <strong>Run an assessment</strong>
                    Get a preliminary plan AYUN can review later.
                  </p>
                </Link>
              </li>
              <li>
                <Link to={isMember ? "/ask" : loginPath("/ask")}>
                  <span>04</span>
                  <p>
                    <strong>Ask Joule</strong>
                    One chat: cited protocol answers, or a conversation with optional voice.
                  </p>
                </Link>
              </li>
              <li>
                <Link to={isMember ? "/tickets" : loginPath("/tickets")}>
                  <span>05</span>
                  <p>
                    <strong>Ask a clinician</strong>
                    Send a ticket when you want an AYUN expert to review.
                  </p>
                </Link>
              </li>
            </ol>
          </section>
        )}
      </div>
    </Layout>
  );
}
