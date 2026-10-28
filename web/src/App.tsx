import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppProvider } from "./lib/context";
import { HomePage } from "./pages/HomePage";
import { AssessmentPage } from "./pages/AssessmentPage";
import { PlanPage } from "./pages/PlanPage";
import { AskPage } from "./pages/AskPage";
import { TicketsPage } from "./pages/TicketsPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { LoginPage } from "./pages/LoginPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ExpertReviewPage } from "./pages/ExpertReviewPage";
import { ExpertMembersPage } from "./pages/ExpertMembersPage";
import { ExpertLoginPage } from "./pages/ExpertLoginPage";

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/assessment" element={<AssessmentPage />} />
          <Route path="/plan" element={<PlanPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/tickets" element={<TicketsPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/expert/review" element={<ExpertReviewPage />} />
          <Route path="/expert/members" element={<ExpertMembersPage />} />
          <Route path="/expert" element={<ExpertLoginPage />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}
