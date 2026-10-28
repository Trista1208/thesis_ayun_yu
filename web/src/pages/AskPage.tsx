import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Mic, Send, Ticket } from "lucide-react";
import { JouleLeap, JouleMark, JouleThinking } from "../components/JouleRunner";
import { Layout } from "../components/Layout";
import { RequireMember } from "../components/RequireMember";
import { MarkdownContent } from "../components/MarkdownContent";
import { TalkStage, type AskMode } from "../components/TalkStage";
import { useApp } from "../lib/context";
import { buildPersonalContext } from "../lib/profileFields";
import {
  JOULE_DEFAULT_VOICE_ID,
  JOULE_VOICES,
  browserSpeechRecognition,
  speakJoule,
  speechSupported,
  startBrowserDictation,
  stopSpeaking,
  unlockPlayback,
} from "../lib/browser-voice";
import {
  chatAsk,
  chatMessageStream,
  calmAiMessage,
  clearAskHistory,
  closeMemorySession,
  fetchAskHistory,
  saveAskExchange,
  createTicket,
  fetchHealth,
  fetchJouleVoices,
  addGuestTicketId,
  getMemberToken,
  type JouleVoice,
} from "../lib/api";

import { SourcePanel } from "../components/SourcePanel";
import { normalizeCitations, type AnswerCitation } from "../lib/sources";

const JOULE_VOICE_KEY = "ayun_joule_voice";
const JOULE_ASK_MODE_KEY = "ayun_ask_mode";

type ChatTurn = {
  role: "user" | "assistant";
  content: string;
  mode?: AskMode;
  citations?: AnswerCitation[];
  confidence?: string;
  ticketId?: string;
  proposedTicket?: string;
  ticketPending?: boolean;
  ticketError?: string;
  isError?: boolean;
};

function newSessionId() {
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function storedMode(): AskMode {
  return localStorage.getItem(JOULE_ASK_MODE_KEY) === "cited" ? "cited" : "talk";
}

export function AskPage() {
  const { assessment, memberName, memberData, personalProfile, isMember } = useApp();
  const [mode, setMode] = useState<AskMode>(storedMode);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState<ChatTurn[]>([]);
  const [voiceState, setVoiceState] = useState<"idle" | "listening" | "thinking" | "speaking">("idle");
  const [voiceHint, setVoiceHint] = useState("");
  const [jouleSpeaks, setJouleSpeaks] = useState(true);
  const [voiceLoop, setVoiceLoop] = useState(false);
  const [elevenlabs, setElevenlabs] = useState<boolean | null>(null);
  const [voices, setVoices] = useState<JouleVoice[]>(JOULE_VOICES);
  const [voiceId, setVoiceId] = useState(
    () => localStorage.getItem(JOULE_VOICE_KEY) || JOULE_DEFAULT_VOICE_ID,
  );
  const sessionId = useRef(newSessionId());
  const chatGen = useRef(0);
  const chatLogRef = useRef(chatLog);
  const chatScroller = useRef<HTMLDivElement>(null);
  const dictationRef = useRef<ReturnType<typeof startBrowserDictation> | null>(null);
  const loopRef = useRef(false);
  const speakOnRef = useRef(true);
  const elevenRef = useRef(false);
  const voiceIdRef = useRef(voiceId);
  const voicesRef = useRef(voices);
  const modeRef = useRef(mode);
  const listenAgainRef = useRef<(fromLoop?: boolean) => void>(() => undefined);
  const [apiOk, setApiOk] = useState<boolean | null>(null);

  const profileContext = buildPersonalContext(personalProfile, {
    age: memberData["Demographic::Age"],
    gender: memberData["Demographic::Sex"],
    height_cm: memberData["Demographic::Height (cm)"],
    weight_kg: memberData["Demographic::Weight (kg)"],
  });
  const context = [assessment?.context_for_llm || "", profileContext].filter(Boolean).join("\n\n");

  useEffect(() => {
    chatLogRef.current = chatLog;
  }, [chatLog]);

  useEffect(() => {
    speakOnRef.current = jouleSpeaks;
  }, [jouleSpeaks]);

  useEffect(() => {
    loopRef.current = voiceLoop;
  }, [voiceLoop]);

  useEffect(() => {
    elevenRef.current = elevenlabs === true;
  }, [elevenlabs]);

  useEffect(() => {
    voiceIdRef.current = voiceId;
    if (voiceId) localStorage.setItem(JOULE_VOICE_KEY, voiceId);
  }, [voiceId]);

  useEffect(() => {
    voicesRef.current = voices;
  }, [voices]);

  useEffect(() => {
    modeRef.current = mode;
    localStorage.setItem(JOULE_ASK_MODE_KEY, mode);
  }, [mode]);

  function selectedVoice(id = voiceIdRef.current) {
    return voicesRef.current.find((voice) => voice.id === id);
  }

  function talkLanguage(id = voiceIdRef.current) {
    return selectedVoice(id)?.lang === "de" ? "de" : "en";
  }

  useEffect(() => {
    return () => {
      dictationRef.current?.cancel();
      stopSpeaking();
    };
  }, []);

  useEffect(() => {
    const scroller = chatScroller.current;
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [chatLog, chatLoading]);

  useEffect(() => {
    if (!isMember || !getMemberToken()) return;
    let cancelled = false;
    fetchAskHistory()
      .then((data) => {
        if (cancelled || chatLogRef.current.length) return;
        const restored: ChatTurn[] = [];
        for (const item of data.exchanges) {
          if (!item.question || !item.answer) continue;
          restored.push({ role: "user", content: item.question, mode: item.mode === "talk" ? "talk" : "cited" });
          restored.push({
            role: "assistant",
            content: item.answer,
            mode: item.mode === "talk" ? "talk" : "cited",
            citations: normalizeCitations(item.citations),
            confidence: item.confidence,
          });
        }
        if (restored.length) {
          chatLogRef.current = restored;
          setChatLog(restored);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [isMember]);

  useEffect(() => {
    fetchHealth()
      .then((health) => {
        setApiOk(true);
        setElevenlabs(!!health.elevenlabs);
      })
      .catch(() => setApiOk(false));
    fetchJouleVoices()
      .then((catalog) => {
        setElevenlabs(catalog.configured);
        setVoices(catalog.voices.length ? catalog.voices : JOULE_VOICES);
        if (catalog.hint) setVoiceHint(catalog.hint);
        setVoiceId((current) =>
          catalog.voices.some((voice) => voice.id === current) ? current : catalog.default_voice_id,
        );
      })
      .catch(() => undefined);

    return () => {
      const messages = chatLogRef.current;
      const userTurns = messages.filter((m) => m.role === "user").length;
      if (isMember && getMemberToken() && userTurns >= 2) {
        closeMemorySession({
          session_id: sessionId.current,
          messages: messages.map((m) => ({ role: m.role, content: m.content })),
          member_name: memberName || "",
        }).catch(() => {
          /* best-effort, ignore */
        });
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function sendCited(question: string, history: ChatTurn[], fromVoice: boolean) {
    const gen = chatGen.current;
    const stillCurrent = () => gen === chatGen.current;
    try {
      const resp = await chatAsk(question, context, memberName || "Member", memberData);
      if (!stillCurrent()) return;
      const isError = !!(resp.error && !resp.answer);
      const content = isError ? resp.error || "Ask failed" : resp.answer;
      setChatLog([
        ...history,
        {
          role: "assistant",
          content,
          mode: "cited",
          citations: isError ? [] : normalizeCitations(resp.citations),
          confidence: isError ? "" : resp.confidence,
          isError,
        },
      ]);
      if (resp.ticket_id && !getMemberToken()) addGuestTicketId(resp.ticket_id);
      if (!isError && getMemberToken()) {
        saveAskExchange({
          question,
          answer: content,
          mode: "cited",
          citations: isError ? [] : normalizeCitations(resp.citations),
          confidence: resp.confidence,
        }).catch(() => undefined);
      }
    } catch (err) {
      if (!stillCurrent()) return;
      setChatLog([
        ...history,
        {
          role: "assistant",
          content: calmAiMessage(err instanceof Error ? err.message : "Ask failed"),
          mode: "cited",
          isError: true,
        },
      ]);
    } finally {
      if (stillCurrent()) setChatLoading(false);
    }
    if (fromVoice && stillCurrent()) {
      setVoiceState("idle");
    }
  }

  async function sendTalk(history: ChatTurn[], fromVoice: boolean) {
    const gen = chatGen.current;
    const stillCurrent = () => gen === chatGen.current;
    const messages = history
      .filter((m) => !m.isError)
      .map((m) => ({ role: m.role, content: m.content }));
    setChatLog([...history, { role: "assistant", content: "", mode: "talk" }]);
    let reply = "";
    let ticketId = "";
    let proposedTicket = "";
    try {
      const streamed = await chatMessageStream(
        messages,
        context,
        (full) => {
          if (!stillCurrent()) return;
          setChatLog([...history, { role: "assistant", content: full, mode: "talk" }]);
        },
        talkLanguage(),
        { fromName: memberName || "Member", memberSnapshot: memberData },
      );
      if (!stillCurrent()) return;
      reply = streamed.reply;
      ticketId = streamed.ticketId;
      proposedTicket = streamed.proposedQuestion;
      if (proposedTicket) {
        loopRef.current = false;
        setVoiceLoop(false);
      }
      setChatLog([
        ...history,
        {
          role: "assistant",
          content: reply,
          mode: "talk",
          ticketId: ticketId || undefined,
          proposedTicket: proposedTicket || undefined,
        },
      ]);
      const asked = [...history].reverse().find((turn) => turn.role === "user")?.content || "";
      if (reply && asked && getMemberToken()) {
        saveAskExchange({ question: asked, answer: reply, mode: "talk" }).catch(() => undefined);
      }
    } catch (err) {
      if (!stillCurrent()) return;
      reply = calmAiMessage(err instanceof Error ? err.message : "Chat failed.");
      setChatLog([...history, { role: "assistant", content: reply, mode: "talk", isError: true }]);
    } finally {
      if (stillCurrent()) setChatLoading(false);
    }
    if (!stillCurrent()) return;
    if (!speakOnRef.current || !reply) {
      if (fromVoice && loopRef.current && !proposedTicket) {
        setVoiceState("idle");
        listenAgainRef.current(true);
      } else if (fromVoice) {
        setVoiceState("idle");
      }
      return;
    }
    if (fromVoice) setVoiceState("speaking");
    const result = await speakJoule(reply, { voiceId: voiceIdRef.current || JOULE_DEFAULT_VOICE_ID });
    if (!stillCurrent()) return;
    if (result === "fallback") {
      setVoiceHint("Joule’s voice did not play. Tap Start talking once, then try again.");
    }
    if (proposedTicket || !fromVoice) {
      setVoiceState("idle");
      return;
    }
    if (result === "stopped" || !loopRef.current) {
      setVoiceState("idle");
      return;
    }
    setVoiceState("idle");
    listenAgainRef.current(true);
  }

  async function confirmProposedTicket(index: number) {
    const turn = chatLogRef.current[index];
    if (!turn?.proposedTicket || turn.ticketPending) return;
    setChatLog((prev) =>
      prev.map((item, i) => (i === index ? { ...item, ticketPending: true, ticketError: "" } : item)),
    );
    try {
      const ticket = await createTicket({
        question: turn.proposedTicket,
        from_name: memberName || "Member",
        category: "General",
        assigned_expert_id: "general_pool",
        source: "talk_agent",
        member_snapshot: memberData,
        chat_context: chatLogRef.current
          .slice(-8)
          .map((m) => `${m.role === "user" ? "Member" : "Joule"}: ${m.content}`)
          .join("\n"),
      });
      setChatLog((prev) =>
        prev.map((item, i) =>
          i === index
            ? {
                ...item,
                ticketId: ticket.id,
                proposedTicket: undefined,
                ticketPending: false,
                ticketError: "",
              }
            : item,
        ),
      );
    } catch (err) {
      setChatLog((prev) =>
        prev.map((item, i) =>
          i === index
            ? {
                ...item,
                ticketPending: false,
                ticketError: err instanceof Error ? err.message : "Could not send the ticket.",
              }
            : item,
        ),
      );
    }
  }

  function dismissProposedTicket(index: number) {
    setChatLog((prev) =>
      prev.map((item, i) =>
        i === index ? { ...item, proposedTicket: undefined, ticketPending: false, ticketError: "" } : item,
      ),
    );
  }

  async function sendChat(raw: string, fromVoice = false) {
    const text = raw.trim();
    if (!text) return;
    const userMsg: ChatTurn = { role: "user", content: text, mode: modeRef.current };
    const next = [...chatLogRef.current, userMsg];
    setChatLog(next);
    setChatInput("");
    setChatLoading(true);
    if (fromVoice) setVoiceState("thinking");
    if (modeRef.current === "cited") {
      await sendCited(text, next, fromVoice);
      return;
    }
    await sendTalk(next, fromVoice);
  }

  function startListening(fromLoop = false) {
    const Recognition = browserSpeechRecognition();
    if (!Recognition) {
      setVoiceHint("Voice works in Chrome or Safari on this computer. Allow the microphone when asked.");
      return;
    }
    dictationRef.current?.cancel();
    stopSpeaking();
    unlockPlayback();
    setVoiceHint("");
    setVoiceLoop(true);
    try {
      dictationRef.current = startBrowserDictation(
        Recognition,
        talkLanguage() === "de" ? "de-DE" : "en-US",
        {
          onStart: () => setVoiceState("listening"),
          onText: (live) => setChatInput(live),
          onEnd: (finalText, error) => {
            dictationRef.current = null;
            if (error) {
              setVoiceHint(error);
              setVoiceState("idle");
              return;
            }
            if (finalText) {
              void sendChat(finalText, true);
            } else {
              setVoiceState("idle");
              if (fromLoop && loopRef.current) {
                setVoiceHint("I didn’t catch that. Tap the mic and try again.");
              }
            }
          },
        },
        90000,
      );
      setVoiceState("listening");
    } catch {
      setVoiceHint("Could not start the microphone. Check browser permission for this site.");
      setVoiceState("idle");
    }
  }
  listenAgainRef.current = startListening;

  function stopListeningAndSend() {
    dictationRef.current?.stop();
  }

  function endVoiceCall() {
    loopRef.current = false;
    setVoiceLoop(false);
    dictationRef.current?.cancel();
    dictationRef.current = null;
    stopSpeaking();
    setVoiceState("idle");
    setVoiceHint("");
  }

  function cancelConversation() {
    chatGen.current += 1;
    endVoiceCall();
    setChatLoading(false);
    setChatLog([]);
    chatLogRef.current = [];
    setChatInput("");
    sessionId.current = newSessionId();
    if (getMemberToken()) {
      clearAskHistory().catch(() => {
        setVoiceHint("The chat was cleared here, but the saved copy could not be removed. Try Clear again.");
      });
    }
  }

  function toggleTalk() {
    if (voiceState === "listening") {
      stopListeningAndSend();
      return;
    }
    if (voiceState === "speaking") {
      stopSpeaking();
      startListening(true);
      return;
    }
    if (voiceState === "thinking") return;
    startListening();
  }

  async function onChat(e: React.FormEvent) {
    e.preventDefault();
    if (voiceState === "listening") {
      stopListeningAndSend();
      return;
    }
    await sendChat(chatInput, false);
  }

  function chooseVoice(id: string) {
    setVoiceId(id);
  }

  function previewVoice(id: string) {
    if (voiceState !== "idle") return;
    unlockPlayback();
    const voice = selectedVoice(id);
    const greeting =
      voice?.greeting ||
      "Hey... I'm Joule, your sports scientist assistant. Feel free to talk with me.";
    void speakJoule(greeting, { voiceId: id });
  }

  function chooseMode(next: AskMode) {
    setMode(next);
    if (next === "cited" && (voiceLoop || voiceState !== "idle")) {
      endVoiceCall();
    }
  }

  const composerPlaceholder =
    voiceState === "listening"
      ? "Listening…"
      : mode === "cited"
        ? "Ask about your plan, training zones, or protocols…"
        : "Type a message";

  return (
    <RequireMember
      title="Ask Joule"
      message="Sign in to talk with Joule and get plan-grounded answers."
    >
      <Layout>
        <div className="ask-hero">
          <JouleMark size={42} title="Joule" />
          <div>
            <p className="label-eyebrow">Joule · sports scientist</p>
            <h1 className="page-title">Ask Joule</h1>
          </div>
        </div>

        <section className="ask-talk">
          <TalkStage
            mode={mode}
            onMode={chooseMode}
            voiceState={voiceState}
            voiceLoop={voiceLoop}
            voiceHint={voiceHint}
            jouleSpeaks={jouleSpeaks}
            speechOk={speechSupported()}
            elevenlabs={elevenlabs}
            voices={voices}
            voiceId={voiceId}
            canClear={chatLog.length > 0 || chatLoading || voiceLoop || voiceState !== "idle"}
            onHangup={endVoiceCall}
            onClear={cancelConversation}
            onMute={() => {
              setJouleSpeaks((on) => {
                if (on) stopSpeaking();
                return !on;
              });
            }}
            onVoiceId={chooseVoice}
            onPreview={previewVoice}
          />
          <div ref={chatScroller} className="ask-transcript">
            {chatLog.length === 0 && !chatLoading ? (
              <p className="ask-empty-hint">
                {assessment
                  ? mode === "talk"
                    ? "One chat. Type, or use Voice to talk with Joule."
                    : "One chat. Type a question about your plan. Switch to Talk to use your voice."
                  : "One chat. Switch mode above. Run an assessment for a plan-grounded reply."}
              </p>
            ) : null}
            {chatLog.map((m, i) =>
              m.role === "assistant" ? (
                <div key={i} className="ask-bubble-assistant">
                  <JouleMark size={20} className="chat-avatar" />
                  <div className="ask-answer">
                    {m.confidence && !m.isError ? (
                      <span className="label-eyebrow mb-2 block">Confidence: {m.confidence}</span>
                    ) : null}
                    {m.isError ? <p>{m.content}</p> : <MarkdownContent content={m.content} citations={m.citations} />}
                    {m.citations?.length ? <SourcePanel citations={m.citations} /> : null}
                    {m.proposedTicket ? (
                      <div className="talk-ticket-ask">
                        <p>
                          Send this to an AYUN expert?
                          <strong> {m.proposedTicket}</strong>
                        </p>
                        {m.ticketError ? <p className="talk-ticket-error">{m.ticketError}</p> : null}
                        <div className="talk-ticket-ask-actions">
                          <button
                            type="button"
                            className="talk-ticket-yes"
                            disabled={m.ticketPending}
                            onClick={() => void confirmProposedTicket(i)}
                          >
                            {m.ticketPending ? "Sending…" : "Send ticket"}
                          </button>
                          <button
                            type="button"
                            className="talk-ticket-no"
                            disabled={m.ticketPending}
                            onClick={() => dismissProposedTicket(i)}
                          >
                            Don’t send
                          </button>
                        </div>
                      </div>
                    ) : null}
                    {m.ticketId ? (
                      <Link to="/tickets" className="talk-ticket">
                        <Ticket className="h-3.5 w-3.5" />
                        Sent to an AYUN expert
                      </Link>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div key={i} className="ask-bubble-user">
                  <p className="whitespace-pre-wrap">{m.content}</p>
                </div>
              ),
            )}
            {chatLoading && (chatLog[chatLog.length - 1]?.content || "") === "" && <JouleThinking />}
          </div>
          <form onSubmit={onChat} className="ask-composer">
            {mode === "talk" ? (
              <button
                type="button"
                className={`talk-option${voiceLoop || voiceState !== "idle" ? " is-on" : ""}`}
                onClick={toggleTalk}
                disabled={apiOk === false || voiceState === "thinking"}
                aria-label={
                  voiceState === "listening"
                    ? "Stop listening"
                    : voiceState === "speaking"
                      ? "Interrupt Joule"
                      : "Talk or dictate instead of typing"
                }
                title="Voice — talk or dictate"
              >
                <Mic className="h-3.5 w-3.5" />
                Voice
              </button>
            ) : null}
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder={composerPlaceholder}
              disabled={voiceState === "listening"}
            />
            <button
              type="submit"
              className={`ask-send${chatLoading ? " is-thinking" : ""}`}
              disabled={chatLoading || apiOk === false}
              aria-label={chatLoading ? "Answer in progress" : "Send message"}
            >
              {chatLoading ? <JouleLeap compact /> : <Send className="h-4 w-4" />}
            </button>
          </form>
        </section>
      </Layout>
    </RequireMember>
  );
}
