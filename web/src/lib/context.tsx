import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
import type { AssessmentResult } from "./api";
import {
  clearExpertSession,
  clearGuestTicketIds,
  clearMemberSession,
  claimMemberTickets,
  fetchExpertMe,
  fetchLatestAssessment,
  fetchMemberMe,
  getExpertToken,
  getGuestTicketIds,
  getMemberToken,
  getStoredActiveMode,
  getStoredAssessmentId,
  setStoredActiveMode,
  setStoredAssessmentId,
  type ActiveMode,
} from "./api";
import { DEFAULT_ENABLED_SECTIONS } from "./assessmentFields";
import {
  DEFAULT_PERSONAL_PROFILE,
  type AppUser,
  type PersonalProfile,
} from "./profileFields";

type AppContextValue = {
  memberName: string;
  setMemberName: (v: string) => void;
  pseudonym: string;
  setPseudonym: (v: string) => void;
  memberData: Record<string, unknown>;
  setMemberData: (v: Record<string, unknown>) => void;
  personalProfile: PersonalProfile;
  setPersonalProfile: (v: PersonalProfile) => void;
  enabledSections: Record<string, boolean>;
  setEnabledSections: Dispatch<SetStateAction<Record<string, boolean>>>;
  assessment: AssessmentResult | null;
  setAssessment: (v: AssessmentResult | null) => void;
  assessmentId: string | null;
  setAssessmentId: (v: string | null) => void;
  isMember: boolean;
  memberUser: AppUser | null;
  applyMemberUser: (user: AppUser) => void;
  restoreMemberAssessment: () => Promise<void>;
  clearMember: () => void;
  isExpert: boolean;
  setIsExpert: (v: boolean) => void;
  activeMode: ActiveMode;
  setActiveMode: (mode: ActiveMode) => void;
  memberLoading: boolean;
};

const AppContext = createContext<AppContextValue | null>(null);

const DEFAULT_MEMBER_DATA: Record<string, unknown> = {
  "Demographic::Age": 35,
  "Demographic::Sex": "Male",
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [memberName, setMemberName] = useState("");
  const [pseudonym, setPseudonym] = useState("");
  const [memberData, setMemberData] = useState<Record<string, unknown>>(DEFAULT_MEMBER_DATA);
  const [personalProfile, setPersonalProfile] = useState<PersonalProfile>(DEFAULT_PERSONAL_PROFILE);
  const [enabledSections, setEnabledSections] = useState<Record<string, boolean>>(DEFAULT_ENABLED_SECTIONS);
  const [assessment, setAssessmentState] = useState<AssessmentResult | null>(null);
  const [assessmentId, setAssessmentIdState] = useState<string | null>(() => getStoredAssessmentId());

  const setAssessment = useCallback((v: AssessmentResult | null) => {
    setAssessmentState(v);
    const id = v?.assessment_id || null;
    setAssessmentIdState(id);
    setStoredAssessmentId(id);
  }, []);

  const setAssessmentId = useCallback((v: string | null) => {
    setAssessmentIdState(v);
    setStoredAssessmentId(v);
  }, []);
  const [isExpert, setIsExpert] = useState(!!getExpertToken());
  const [isMember, setIsMember] = useState(!!getMemberToken());
  const [memberUser, setMemberUser] = useState<AppUser | null>(null);
  const [memberLoading, setMemberLoading] = useState(!!getMemberToken());
  const [activeMode, setActiveModeState] = useState<ActiveMode>(() => {
    const stored = getStoredActiveMode();
    if (stored === "expert" && getExpertToken()) return "expert";
    return "member";
  });

  const applyMemberUser = useCallback((user: AppUser) => {
    setMemberUser(user);
    setIsMember(true);
    if (user.member_data && Object.keys(user.member_data).length) {
      setMemberData(user.member_data);
    }
    if (user.personal_profile) {
      setPersonalProfile({ ...DEFAULT_PERSONAL_PROFILE, ...user.personal_profile });
    }
    if (user.enabled_sections && Object.keys(user.enabled_sections).length) {
      setEnabledSections({ ...DEFAULT_ENABLED_SECTIONS, ...user.enabled_sections });
    }
    setPseudonym(user.pseudonym || "");
    const name = user.personal_profile?.name?.trim() || user.display_name || "";
    setMemberName(name);
  }, []);

  const restoreMemberAssessment = useCallback(async () => {
    if (!getMemberToken()) {
      setAssessment(null);
      return;
    }
    try {
      const data = await fetchLatestAssessment();
      setAssessment(data.assessment);
    } catch {
      setAssessment(null);
    }
  }, [setAssessment]);

  const clearMember = useCallback(() => {
    clearMemberSession();
    setMemberUser(null);
    setIsMember(false);
    setAssessment(null);
    setMemberName("");
    setPseudonym("");
    setMemberData(DEFAULT_MEMBER_DATA);
    setPersonalProfile(DEFAULT_PERSONAL_PROFILE);
    setEnabledSections(DEFAULT_ENABLED_SECTIONS);
  }, [setAssessment]);

  const setActiveMode = useCallback(
    (mode: ActiveMode) => {
      if (mode === "expert" && !getExpertToken()) return;
      setActiveModeState(mode);
      setStoredActiveMode(mode);
    },
    [],
  );

  useEffect(() => {
    const token = getExpertToken();
    if (!token) return;
    fetchExpertMe()
      .then(() => setIsExpert(true))
      .catch(() => {
        clearExpertSession();
        setIsExpert(false);
      });
  }, []);

  useEffect(() => {
    const token = getMemberToken();
    if (!token) {
      setMemberLoading(false);
      return;
    }
    fetchMemberMe()
      .then(async (user) => {
        applyMemberUser(user);
        const guestIds = getGuestTicketIds();
        if (guestIds.length) {
          try {
            await claimMemberTickets(guestIds);
            clearGuestTicketIds();
          } catch {
            /* best-effort on session restore */
          }
        }
        await restoreMemberAssessment();
      })
      .catch(() => clearMember())
      .finally(() => setMemberLoading(false));
  }, [applyMemberUser, clearMember, restoreMemberAssessment]);

  useEffect(() => {
    if (activeMode === "expert" && !isExpert) {
      setActiveModeState("member");
      setStoredActiveMode("member");
    }
  }, [activeMode, isExpert]);

  const value = useMemo(
    () => ({
      memberName,
      setMemberName,
      pseudonym,
      setPseudonym,
      memberData,
      setMemberData,
      personalProfile,
      setPersonalProfile,
      enabledSections,
      setEnabledSections,
      assessment,
      setAssessment,
      assessmentId,
      setAssessmentId,
      isMember,
      memberUser,
      applyMemberUser,
      restoreMemberAssessment,
      clearMember,
      isExpert,
      setIsExpert,
      activeMode,
      setActiveMode,
      memberLoading,
    }),
    [
      memberName,
      pseudonym,
      memberData,
      personalProfile,
      enabledSections,
      assessment,
      setAssessment,
      assessmentId,
      setAssessmentId,
      isMember,
      memberUser,
      applyMemberUser,
      restoreMemberAssessment,
      clearMember,
      isExpert,
      activeMode,
      setActiveMode,
      memberLoading,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
