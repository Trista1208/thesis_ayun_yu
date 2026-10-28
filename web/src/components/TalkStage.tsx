import { PhoneOff, Volume2, VolumeX, X } from "lucide-react";
import type { JouleVoice } from "../lib/api";

type VoiceState = "idle" | "listening" | "thinking" | "speaking";
export type AskMode = "cited" | "talk";

type Props = {
  mode: AskMode;
  onMode: (mode: AskMode) => void;
  voiceState: VoiceState;
  voiceLoop: boolean;
  voiceHint: string;
  jouleSpeaks: boolean;
  speechOk: boolean;
  elevenlabs: boolean | null;
  voices: JouleVoice[];
  voiceId: string;
  canClear: boolean;
  onHangup: () => void;
  onClear: () => void;
  onMute: () => void;
  onVoiceId: (id: string) => void;
  onPreview: (id: string) => void;
};

function promptFor(state: VoiceState, hint: string, speechOk: boolean, voiceName: string) {
  if (state === "listening") return "Listening — tap Voice when you are done";
  if (state === "thinking") return "Joule is thinking…";
  if (state === "speaking") return "Speaking — click to interrupt";
  if (hint) return hint;
  if (!speechOk) return "This browser cannot dictate. Type below, or use Chrome or Safari.";
  return voiceName ? `Talk · ${voiceName}` : "Talk";
}

export function TalkStage({
  mode,
  onMode,
  voiceState,
  voiceLoop,
  voiceHint,
  jouleSpeaks,
  speechOk,
  elevenlabs,
  voices,
  voiceId,
  canClear,
  onHangup,
  onClear,
  onMute,
  onVoiceId,
  onPreview,
}: Props) {
  const inCall = voiceLoop || voiceState !== "idle";
  const voiceName = voices.find((voice) => voice.id === voiceId)?.name || "";

  return (
    <div className={`talk-stage is-${voiceState}`}>
      <div className="talk-head">
        <h2>{mode === "cited" ? "Cited Q&A" : "Talk"}</h2>
        <div className="talk-head-tools">
          <button
            type="button"
            className={`talk-tool${jouleSpeaks ? " is-on" : ""}`}
            onClick={onMute}
            aria-label={jouleSpeaks ? "Mute Joule" : "Let Joule speak"}
            title={jouleSpeaks ? "Mute Joule" : "Let Joule speak"}
          >
            {jouleSpeaks ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
          </button>
          {inCall ? (
            <button type="button" className="talk-tool is-hangup" onClick={onHangup} aria-label="End voice conversation">
              <PhoneOff className="h-4 w-4" />
              End
            </button>
          ) : null}
          {canClear ? (
            <button
              type="button"
              className="talk-tool is-clear"
              onClick={onClear}
              aria-label="Clear saved questions and answers"
              title="Remove this conversation from your account"
            >
              <X className="h-4 w-4" />
              Clear
            </button>
          ) : null}
        </div>
      </div>
      <div className="talk-voices ask-modes" role="radiogroup" aria-label="Choose how to ask">
        <span className="talk-voices-label">Mode</span>
        <button
          type="button"
          role="radio"
          aria-checked={mode === "cited"}
          className={`talk-voice${mode === "cited" ? " is-on" : ""}`}
          onClick={() => onMode("cited")}
        >
          Cited Q&amp;A
        </button>
        <button
          type="button"
          role="radio"
          aria-checked={mode === "talk"}
          className={`talk-voice${mode === "talk" ? " is-on" : ""}`}
          onClick={() => onMode("talk")}
        >
          Talk
        </button>
      </div>
      <p className="talk-mode-lede">
        {mode === "cited"
          ? "Plan-grounded answers with AYUN protocol and Evipedia sources."
          : "Short conversation. Optional voice. Joule can send a ticket to an expert."}
      </p>
      {mode === "talk" ? (
        <div className="talk-voices" role="radiogroup" aria-label="Choose a tone">
          <span className="talk-voices-label">Tone</span>
          {voices.map((voice) => (
            <button
              key={voice.id}
              type="button"
              role="radio"
              aria-checked={voice.id === voiceId}
              className={`talk-voice${voice.id === voiceId ? " is-on" : ""}`}
              title={voice.vibe}
              onClick={() => {
                onVoiceId(voice.id);
                if (voice.id !== voiceId && voiceState === "idle") onPreview(voice.id);
              }}
            >
              {voice.name}
            </button>
          ))}
        </div>
      ) : null}

      {mode === "talk" && (inCall || voiceHint || elevenlabs === false) && (
        <div className="talk-live">
          <p className="talk-prompt" aria-live="polite">
            {promptFor(voiceState, voiceHint, speechOk, voiceName)}
          </p>
          {elevenlabs === false ? (
            <p className="talk-note">{voiceHint || "Connect ElevenLabs with a secret key that starts with sk_"}</p>
          ) : null}
        </div>
      )}
    </div>
  );
}
