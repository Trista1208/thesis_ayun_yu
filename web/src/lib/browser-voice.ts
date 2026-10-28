import { speakElevenLabs, type JouleVoice } from "./api";

export const JOULE_DEFAULT_VOICE_ID = "6q2fEVEF7Uvhqy2k7Ep5";

export const JOULE_VOICES: JouleVoice[] = [
  {
    id: "6q2fEVEF7Uvhqy2k7Ep5",
    name: "Jiaqi",
    vibe: "Talk to a real person",
    lang: "en",
  },
  {
    id: "iP95p4xoKVk53GoZ742B",
    name: "Male coach",
    vibe: "Warm, calm American — conversational",
    lang: "en",
  },
  {
    id: "pFZP5JQG7iQjIQuC4Bku",
    name: "Female coach",
    vibe: "Light British — warm, not a narrator",
    lang: "en",
  },
  {
    id: "Cqbq4nsuUe1we6J45miU",
    name: "German male coach",
    vibe: "Deutsch — talk in German",
    lang: "de",
  },
];

const SILENT_WAV =
  "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";

// Browser dictation needs no application API credential. The browser may use its
// own speech service; the UI discloses that before the user starts the microphone.
export interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
export type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

export function browserSpeechRecognition(): SpeechRecognitionConstructor | undefined {
  if (typeof window === 'undefined') return undefined;
  const browser = window as unknown as { SpeechRecognition?: SpeechRecognitionConstructor; webkitSpeechRecognition?: SpeechRecognitionConstructor };
  return browser.SpeechRecognition || browser.webkitSpeechRecognition;
}

export function speechSupported() {
  return Boolean(browserSpeechRecognition());
}

export function ttsSupported() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function stripForSpeech(text: string) {
  return (text || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/<!--[\s\S]*?-->/g, " ")
    .replace(/^\s*TICKET:\s*.+$/gim, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\[(?:\d+|Member|Protocol[^\]]*|Web[^\]]*|AYUN[^\]]*)\]/gi, " ")
    .replace(/[#*_`>]/g, "")
    .replace(/^\s*[-•]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

let speakGeneration = 0;
let player: HTMLAudioElement | null = null;
let objectUrl: string | null = null;
let speakAbort: AbortController | null = null;
let playbackDone: ((result: "done" | "stopped") => void) | null = null;

function getPlayer() {
  if (typeof window === "undefined") return null;
  if (!player) {
    player = new Audio();
    player.preload = "auto";
    player.setAttribute("playsinline", "true");
  }
  return player;
}

function hushBrowserVoice() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

function clearAudio() {
  speakAbort?.abort();
  speakAbort = null;
  const done = playbackDone;
  playbackDone = null;
  if (player) {
    player.onended = null;
    player.onerror = null;
    player.pause();
  }
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
  hushBrowserVoice();
  done?.("stopped");
}

export function unlockPlayback() {
  hushBrowserVoice();
  const audio = getPlayer();
  if (!audio) return;
  audio.muted = false;
  audio.volume = 1;
  audio.src = SILENT_WAV;
  void audio.play().catch(() => undefined);
}

export function stopSpeaking() {
  speakGeneration += 1;
  clearAudio();
}

export async function speakJoule(
  text: string,
  options: { voiceId?: string; useElevenLabs?: boolean } = {},
): Promise<"done" | "stopped" | "fallback"> {
  const spoken = stripForSpeech(text);
  const generation = ++speakGeneration;
  clearAudio();
  hushBrowserVoice();
  if (!spoken) return "done";

  const voiceId = options.voiceId || JOULE_DEFAULT_VOICE_ID;
  const abort = new AbortController();
  speakAbort = abort;
  try {
    const blob = await speakElevenLabs(spoken, voiceId, abort.signal);
    if (speakGeneration !== generation) return "stopped";
    const audioBlob = blob.type.includes("audio") ? blob : new Blob([await blob.arrayBuffer()], { type: "audio/mpeg" });
    const url = URL.createObjectURL(audioBlob);
    objectUrl = url;
    const audio = getPlayer();
    if (!audio) return "stopped";
    audio.muted = false;
    audio.volume = 1;
    audio.src = url;
    const result = await new Promise<"done" | "stopped">((resolve, reject) => {
      playbackDone = resolve;
      audio.onended = () => {
        playbackDone = null;
        resolve(speakGeneration === generation ? "done" : "stopped");
      };
      audio.onerror = () => {
        playbackDone = null;
        reject(new Error("audio"));
      };
      void audio.play().catch((err) => {
        playbackDone = null;
        reject(err);
      });
    });
    return result;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return "stopped";
    if (speakGeneration !== generation) return "stopped";
    return "fallback";
  }
}

export function speakText(
  text: string,
  callbacks: { onStart?: () => void; onEnd?: () => void } = {},
) {
  callbacks.onStart?.();
  void speakJoule(text).then((result) => {
    if (result === "done") callbacks.onEnd?.();
  });
  return () => stopSpeaking();
}

export function speechError(code: string) {
  if (code === 'not-allowed') return 'Microphone access was denied. Allow microphone access for this site in your browser settings, then try again.';
  if (code === 'audio-capture') return 'Your microphone could not be opened. Check that it is connected and available, then try again.';
  if (code === 'no-speech') return 'No speech was detected. Try speaking a little closer to your microphone.';
  if (code === 'network') return 'The browser’s speech service could not connect. Check your connection and try again.';
  if (code === 'language-not-supported') return 'Your browser does not support dictation in its current language. Try another browser language.';
  return 'This browser could not start dictation. Open the app in Chrome or Safari; Safari may also need Siri enabled.';
}

export function startBrowserDictation(Recognition: SpeechRecognitionConstructor, language: string, callbacks: {
  onStart: () => void;
  onText: (text: string) => void;
  onEnd: (text: string, error?: string) => void;
}, timeoutMs = 30000) {
  const recognition = new Recognition();
  recognition.lang = language || 'en-US';
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  let active = true, text = '', startup: ReturnType<typeof setTimeout> | undefined;
  function detach() {
    clearTimeout(startup);
    recognition.onstart = null; recognition.onresult = null;
    recognition.onerror = null; recognition.onend = null;
  }
  function finish(error?: string) {
    if (!active) return;
    active = false; detach();
    callbacks.onEnd(text.trim(), error);
  }
  recognition.onstart = () => { clearTimeout(startup); if (active) callbacks.onStart(); };
  recognition.onresult = event => {
    if (!active) return;
    // Results are cumulative: replace the preview rather than appending repeated
    // interim hypotheses and duplicating every word in the completed transcript.
    text = Array.from(event.results).map(result => result[0]?.transcript || '').join(' ').trim();
    callbacks.onText(text);
  };
  recognition.onerror = event => {
    finish(speechError(event.error));
    try { recognition.abort(); } catch { /* Already stopped. */ }
  };
  recognition.onend = () => finish();
  startup = setTimeout(() => {
    finish(speechError('service-not-allowed'));
    try { recognition.abort(); } catch { /* Already stopped. */ }
  }, timeoutMs);
  try { recognition.start(); }
  catch (error) {
    active = false; detach();
    try { recognition.abort(); } catch { /* No session was started. */ }
    throw error;
  }
  return {
    stop() {
      if (!active) return;
      // Give the engine a chance to return its last words before ending. Engines
      // that omit onend must not leave the composer permanently disabled.
      clearTimeout(startup);
      startup = setTimeout(() => {
        finish();
        try { recognition.abort(); } catch { /* Already stopped. */ }
      }, 3000);
      try { recognition.stop(); } catch { finish(); }
    },
    cancel() {
      active = false; detach();
      try { recognition.abort(); } catch { /* Already stopped. */ }
    },
  };
}
