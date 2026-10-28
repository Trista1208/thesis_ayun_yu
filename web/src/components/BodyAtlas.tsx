import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowLeft, Maximize, Minus, Move, Plus, Rotate3D } from "lucide-react";
import { AnatomyScene, type AnatomyFrame, type AnatomyGraph, type AnatomyManifest } from "../lib/anatomy-scene";
import styles from "./BodyAtlas.module.css";

const initialFrame: AnatomyFrame = {
  zoom: 1,
  labels: [],
  detailReady: false,
  detailError: false,
  region: "",
  rotated: false,
};

export function BodyAtlas() {
  const canvas = useRef<HTMLCanvasElement>(null);
  const atlas = useRef<HTMLElement>(null);
  const scene = useRef<AnatomyScene | null>(null);
  const [frame, setFrame] = useState<AnatomyFrame>(initialFrame);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [pan, setPan] = useState(false);
  const [intro, setIntro] = useState<"in" | "out" | "gone">("in");

  useEffect(() => {
    let active = true;
    const abort = new AbortController();
    setLoading(true);
    setError("");
    setFrame(initialFrame);
    setPan(false);
    setIntro("in");
    Promise.all([
      fetch("/models/anatomy/surface.json", { signal: abort.signal }).then(async (response) => {
        if (!response.ok) throw new Error();
        return response.json() as Promise<AnatomyGraph>;
      }),
      fetch("/models/anatomy/manifest.json", { signal: abort.signal }).then(async (response) => {
        if (!response.ok) throw new Error();
        return response.json() as Promise<AnatomyManifest>;
      }),
    ])
      .then(([graph, manifest]) => {
        if (!active || !canvas.current) return;
        scene.current = new AnatomyScene(
          canvas.current,
          graph,
          manifest,
          (next) => {
            if (active) setFrame(next);
          },
          () => {
            if (active) setError("The 3D view was interrupted. Reload the body to continue.");
          },
        );
        setLoading(false);
      })
      .catch(() => {
        if (active) {
          setLoading(false);
          setError("The 3D body could not be loaded. Please try again.");
        }
      });
    return () => {
      active = false;
      abort.abort();
      scene.current?.dispose();
      scene.current = null;
    };
  }, [attempt]);

  useEffect(() => {
    if (loading || error || !atlas.current) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let fade = 0;
    let gone = 0;
    const start = () => {
      fade = window.setTimeout(() => setIntro("out"), reduce ? 1600 : 2600);
      gone = window.setTimeout(() => setIntro("gone"), reduce ? 1600 : 3500);
    };
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        io.disconnect();
        start();
      },
      { threshold: 0.4 },
    );
    io.observe(atlas.current);
    return () => {
      io.disconnect();
      window.clearTimeout(fade);
      window.clearTimeout(gone);
    };
  }, [loading, error, attempt]);

  function dismissIntro() {
    setIntro((current) => (current === "gone" ? current : "out"));
    window.setTimeout(() => setIntro("gone"), 850);
  }

  function keyDown(event: KeyboardEvent<HTMLCanvasElement>) {
    const arrows: Record<string, [number, number]> = {
      ArrowLeft: [0.12, 0],
      ArrowRight: [-0.12, 0],
      ArrowUp: [0, -0.1],
      ArrowDown: [0, 0.1],
    };
    if (arrows[event.key]) {
      event.preventDefault();
      scene.current?.rotateBy(...arrows[event.key]);
    } else if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      scene.current?.zoomBy(1.3);
    } else if (event.key === "-") {
      event.preventDefault();
      scene.current?.zoomBy(1 / 1.3);
    } else if (event.key === "0" || event.key === "Escape") {
      event.preventDefault();
      scene.current?.reset();
    }
  }

  return (
    <section ref={atlas} className={styles.atlas} aria-label="Interactive body map">
      <canvas
        ref={canvas}
        className={`${styles.body} ${intro !== "in" ? styles.bodyReady : ""}`}
        tabIndex={0}
        aria-label="3D human body"
        aria-describedby="home-atlas-instructions"
        onKeyDown={keyDown}
      />
      {error && (
        <div className={styles.loading} role="status">
          {error}
          <button onClick={() => setAttempt((value) => value + 1)}>Reload body</button>
        </div>
      )}
      {!error && intro !== "gone" && (
        <div
          className={`${styles.intro} ${intro === "out" ? styles.introOut : ""}`}
          aria-hidden={intro === "out"}
          onClick={dismissIntro}
        >
          <p className={styles.introTitle}>
            Your health
            <br />
            digital twin
            <br />
            is coming soon.
          </p>
          <span className={styles.introRule} />
          <p className={styles.introSub}>Explore yourself more with data.</p>
        </div>
      )}
      {!loading && !error && (
        <>
          {(frame.zoom > 1.05 || frame.rotated) && (
            <div className={styles.breadcrumb}>
              <button onClick={() => scene.current?.reset()}>
                <ArrowLeft size={14} />
                Whole body
              </button>
            </div>
          )}
          {frame.detailError && (
            <div className={styles.detailStatus} role="status">
              <button onClick={() => setAttempt((value) => value + 1)}>Retry anatomical detail</button>
            </div>
          )}
        </>
      )}
      <p className={styles.srOnly} id="home-atlas-instructions">
        Click the body to zoom into organs. Drag to rotate. Scroll to zoom.
      </p>
      <p className={styles.credit}>
        3D anatomy from{" "}
        <a href="https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html">BodyParts3D</a>
        , © Database Center for Life Science.{" "}
        <a href="/models/anatomy/NOTICE.md">CC BY 4.0; lungs CC BY-SA 2.1 JP</a>.
      </p>
      <div className={`${styles.footer} ${intro !== "in" ? styles.footerReady : ""}`}>
        <div className={styles.controls} role="group" aria-label="Body view controls">
          <button
            onClick={() => {
              scene.current?.setPanMode(!pan);
              setPan(!pan);
            }}
            aria-label={pan ? "Switch to rotation" : "Switch to panning"}
            aria-pressed={pan}
          >
            {pan ? <Move size={16} /> : <Rotate3D size={18} />}
          </button>
          <span />
          <button onClick={() => scene.current?.zoomBy(1 / 1.3)} disabled={frame.zoom <= 1.001} aria-label="Zoom out">
            <Minus size={16} />
          </button>
          <output aria-label="Zoom level">{Math.round(frame.zoom * 100)}%</output>
          <button onClick={() => scene.current?.zoomBy(1.3)} disabled={frame.zoom >= 13.999} aria-label="Zoom in">
            <Plus size={16} />
          </button>
          <button onClick={() => scene.current?.reset()} aria-label="Reset body view">
            <Maximize size={15} />
          </button>
        </div>
      </div>
    </section>
  );
}
