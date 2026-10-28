"""Generate Ask Joule (Cited Q&A) answers for dummy profiles x fixed questions, saving the exact prompt."""
import sys, json, os, time
sys.path[:0] = ["/Users/jiaqiyu/Desktop/AYUN/backend", "/Users/jiaqiyu/Desktop/AYUN"]
from api.deps import load_env; load_env()
import chatbot as cb
MODEL = sys.argv[1]  # gemini | qwen
OUT = sys.argv[2]
if MODEL == "qwen":
    cb._free_cloud_settings = lambda embed: None
    os.environ["OLLAMA_MODEL"] = "qwen2.5:7b"
from recommendation_api import get_recommendations
from protocol_library import enrich_member_context
import ask_engine

CAPTURE = {}
_orig_build = cb._build_client
def _build():
    client = _orig_build()
    orig_create = client.chat.completions.create
    def create(**kw):
        CAPTURE["request"] = {k: v for k, v in kw.items() if k in ("model", "messages", "temperature", "max_tokens")}
        resp = orig_create(**kw)
        CAPTURE["raw"] = cb._message_text(resp.choices[0].message)
        return resp
    client.chat.completions.create = create
    return client
cb._build_client = _build

def ctx(lines): return "\n".join(lines)
PROFILES = {
 "F31_dexa_only": ({"Demographic::Age": 31, "Demographic::Sex": "Female", "Demographic::Height (cm)": 170, "Demographic::Weight (kg)": 60,
   "Body Composition::Muscle Mass Index (LMI)": 17.1, "Body Composition::ALMI": 8.0, "Body Composition::Fat percentage": 15.7,
   "Body Composition::Visceral Fat Index (raw value from DEXA)": 73, "Body Composition::Bone mineral density": 0.7},
   ctx(["Age: 31", "Gender: Female", "Height: 170 cm", "Weight: 60 kg", "BMI: 20.8 kg/m²", "Geographic area: Switzerland — urban (Basel)",
        "General health status: Good health — no known conditions", "Existing conditions / diagnoses: I am having allergy, scratches at night",
        "Smoking status: Non-smoker", "Alcohol use: None", "Typical sleep: 5–6 hours",
        "Diet / dietary notes: Pescatarian, 4000+ kcal/day, large amounts of chips, chocolate and cakes",
        "Health goals: Weight management, Improve bone health, Longevity & disease prevention, Athletic performance",
        "Current activity level: Very Active (4–7h/week)", "Preferred activities: Gym / weight training, CrossFit / HIIT",
        "Stress level: Moderate", "Depression level: Low", "Optimism level: High", "Injuries / limitations: No recent injuries"]), None),
 "M51_full": ({"Demographic::Age": 51, "Demographic::Sex": "Male", "Demographic::Height (cm)": 184, "Demographic::Weight (kg)": 92,
   "Body Composition::Muscle Mass Index (LMI)": 18.1, "Body Composition::ALMI": 8.2, "Body Composition::Fat percentage": 30.4,
   "Body Composition::Visceral Fat Index (raw value from DEXA)": 1722, "Body Composition::Bone mineral density": 0.4,
   "Physiological::Vo2Max": 38.5, "Physiological::HR max": 167, "Physiological::HR at VT1": 115, "Physiological::HR at VT2": 151,
   "Physiological::Gripstrength Rechts": 55.5, "Physiological::Gripstrength Links": 50.3, "Physiological::Counter movement jump": 26.4,
   "Physiological::Y-Balance Composite Score": 95, "Blood Biomarkers::LDL": 2.3, "Blood Biomarkers::HbA1c": 5.2,
   "Blood Biomarkers::ASAT": 17, "Blood Biomarkers::ALAT": 12},
   ctx(["Age: 51", "Gender: Male", "Height: 184 cm", "Weight: 92 kg", "BMI: 27.2 kg/m²", "Geographic area: Switzerland — urban (Fehraltorf)",
        "General health status: Generally healthy — minor issues only", "Typical sleep: 7–8 hours", "Diet / dietary notes: Mediterranean-style",
        "Health goals: Weight management, Reduce cardiovascular risk, Longevity & disease prevention",
        "Current activity level: Lightly Active (1–2h/week)", "Stress level: Low", "Depression level: Very High",
        "Injuries / limitations: injury last week, can't move my leg"]), None),
 "F42_lena_demo": ({"Demographic::Age": 42, "Demographic::Sex": "Female", "Physiological::Vo2Max": 28, "Physiological::HR max": 178,
   "Physiological::HR at VT1": 128, "Physiological::HR at VT2": 155, "Physiological::Gripstrength Rechts": 26, "Physiological::Gripstrength Links": 24,
   "Physiological::Counter movement jump": 22, "Body Composition::Fat percentage": 34, "Body Composition::Muscle Mass Index (LMI)": 14.2,
   "Body Composition::ALMI": 5.8, "Body Composition::Visceral Fat Index (raw value from DEXA)": 9, "Blood Biomarkers::LDL": 4.2, "Blood Biomarkers::HbA1c": 5.8},
   ctx(["Age: 42", "Gender: Female", "Geographic area: Switzerland — urban (Zürich)", "General health status: Generally healthy — minor issues only",
        "Existing conditions / diagnoses: Family history of cardiovascular disease", "Smoking status: Non-smoker", "Alcohol use: Occasional (social)",
        "Typical sleep: 7–8 hours", "Health goals: Improve aerobic fitness, Lower cholesterol", "Current activity level: Lightly Active (under 2h/week)",
        "Preferred activities: Walking, Yoga", "Additional notes: Wants a plan she can keep with two small children."]), "demo-lena-hofmann"),
 "M58_marco_demo": ({"Demographic::Age": 58, "Demographic::Sex": "Male", "Physiological::Vo2Max": 32, "Physiological::HR max": 168,
   "Physiological::HR at VT1": 118, "Physiological::HR at VT2": 145, "Physiological::Gripstrength Rechts": 38, "Physiological::Gripstrength Links": 36,
   "Physiological::Biceps Strength Rechts": 28, "Physiological::Biceps Strength Links": 26, "Body Composition::Fat percentage": 27,
   "Body Composition::Muscle Mass Index (LMI)": 17.4, "Body Composition::ALMI": 7.1, "Blood Biomarkers::LDL": 3.9, "Blood Biomarkers::HbA1c": 5.6},
   ctx(["Age: 58", "Gender: Male", "Geographic area: Switzerland — urban (Zürich)", "General health status: Recovering from illness or injury",
        "Existing conditions / diagnoses: Mild left-knee osteoarthritis", "Smoking status: Non-smoker", "Alcohol use: Occasional (social)",
        "Typical sleep: 7–8 hours", "Health goals: Stay active for work travel, Protect the left knee",
        "Current activity level: Moderately Active (2–4h/week)", "Preferred activities: Running, Cycling",
        "Injuries / limitations: Left knee pain after interval sessions"]), "demo-marco-keller"),
 "M67_jonas_demo": ({"Demographic::Age": 67, "Demographic::Sex": "Male", "Physiological::Vo2Max": 22, "Physiological::HR max": 153,
   "Physiological::HR at VT1": 102, "Physiological::HR at VT2": 124, "Physiological::Gripstrength Rechts": 24, "Physiological::Gripstrength Links": 22,
   "Physiological::Y-Balance Composite Score": 78, "Body Composition::Fat percentage": 31, "Body Composition::Muscle Mass Index (LMI)": 15.1,
   "Body Composition::ALMI": 6.4, "Body Composition::Bone mineral density": -1.4, "Blood Biomarkers::LDL": 3.6, "Genetics::Bone Health Risk": "Moderate"},
   ctx(["Age: 67", "Gender: Male", "Geographic area: Switzerland — rural / alpine (Bernese Oberland)", "General health status: Managing chronic condition(s)",
        "Existing conditions / diagnoses: Osteopenia; history of a near-fall last winter", "Smoking status: Non-smoker", "Alcohol use: Occasional (social)",
        "Typical sleep: 7–8 hours", "Health goals: Stay independent, Reduce fall risk", "Current activity level: Lightly Active (under 2h/week)",
        "Preferred activities: Walking, Swimming", "Injuries / limitations: Unsteady on uneven ground",
        "Additional notes: Prefers supervised strength work before any jumping."]), "demo-jonas-weber"),
}
QUESTIONS = [
 "Make me a weekly workout plan",
 "What heart rate should I train at for Zone 2?",
 "How can I improve my VO2max?",
 "Is my body composition okay, and what should I work on?",
 "What should I eat to support my goals?",
 "How many strength sessions per week should I do, and how heavy?",
 "Can I do HIIT this week?",
]
done = set()
if os.path.exists(OUT):
    done = {json.loads(l)["id"] for l in open(OUT)}
with open(OUT, "a") as f:
    for pname, (member, personal, uid) in PROFILES.items():
        r = get_recommendations(member, personal_context=personal)
        for qi, q in enumerate(QUESTIONS):
            rid = f"{MODEL}:{pname}:q{qi+1}"
            if rid in done: continue
            CAPTURE.clear(); t = time.time()
            try:
                resp = ask_with = ask_engine.ask_with_knowledge(
                    question=q, member_context=enrich_member_context(r.context_for_llm, question=q, member_data=member),
                    member_snapshot=member, auto_ticket=False, retention_days=0, member_user_id=uid)
                rec = dict(id=rid, model=cb.ai_config().get("model"), profile=pname, question=q, seconds=round(time.time()-t, 1),
                           request=CAPTURE.get("request"), raw=CAPTURE.get("raw"), answer=resp.answer, confidence=resp.confidence,
                           citations=resp.citations, member=member, personal=personal)
            except Exception as e:
                rec = dict(id=rid, model=MODEL, profile=pname, question=q, error=str(e))
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n"); f.flush()
            print(rid, rec.get("seconds"), rec.get("confidence"), rec.get("error", ""), flush=True)
"""
Score Ask Joule answers against the exact prompt each model received.

Error types (operational, automated; each flag lists the evidence so it can be checked):
 A  invented value: a member-type number (bpm, ml/kg/min, kg/m², %, mmol/L, cm³, U/L, kg, SD, hours)
    stated in the answer that does not occur anywhere in the prompt.
 B  ungrounded dose (recommendation not in context): sets x reps, minutes, or sessions per week
    whose numbers do not occur in the prompt.
 C  misstated member value: a self-reported level (sleep, stress, depression, optimism) or a
    measured value named in the answer differs from the member's value in the prompt.
 D  wrong citation: [n] / [Web n] marker outside the numbered source lists, or a validated
    Q&A that belongs to another member.
"""
import json, re, sys, math
from collections import defaultdict

DASH = r"[–\-—]"
NUM = r"\d+(?:[.,]\d+)?"

def norm(x): return x.replace(",", ".").replace("—", "–").replace("-", "–")

def nums(text):
    return {norm(m) for m in re.findall(NUM, text)}

def present(num_str, ctx_nums):
    return norm(num_str) in ctx_nums or str(float(norm(num_str))).rstrip("0").rstrip(".") in {str(float(c)).rstrip("0").rstrip(".") for c in ctx_nums if re.fullmatch(r"\d+(\.\d+)?", c)}

UNIT = r"(bpm|beats per minute|ml/kg/min|ml/min/kg|kg/m²|kg/m2|mmol/L|cm³|cm3|U/L|kcal|SD|hours?|h\b|%|kg\b)"
VALUE_RE = re.compile(rf"(?<![\w.])({NUM})(?:\s*{DASH}\s*({NUM}))?\s*{UNIT}", re.I)
SETS_REPS = re.compile(rf"(\d+)\s*(?:sets?\s*(?:of|×|x)\s*|×\s*|x\s*)(\d+(?:\s*{DASH}\s*\d+)?)", re.I)
MINUTES = re.compile(rf"(\d+(?:\s*{DASH}\s*\d+)?)\s*(?:min\b|mins\b|minutes)", re.I)
PER_WEEK = re.compile(rf"(\d+(?:\s*{DASH}\s*\d+)?)\s*(?:×|x|times|sessions?|days?|workouts?)\s*(?:per|a|/|each)\s*week", re.I)

LEVELS = ["very high", "high", "moderate", "low"]
SELF = {"Stress level": "stress", "Depression level": "depress", "Optimism level": "optimis", "Typical sleep": "sleep"}
MEASURED = {  # answer keyword -> member_data key
    r"body fat": "Body Composition::Fat percentage", r"\bLMI\b|lean mass index|muscle mass index": "Body Composition::Muscle Mass Index (LMI)",
    r"VO2 ?max|VO₂ ?max": "Physiological::Vo2Max", r"\bLDL\b": "Blood Biomarkers::LDL", r"HbA1c": "Blood Biomarkers::HbA1c",
    r"visceral": "Body Composition::Visceral Fat Index (raw value from DEXA)", r"HR ?max|max(?:imum)? heart rate": "Physiological::HR max",
    r"\bVT1\b": "Physiological::HR at VT1", r"\bVT2\b": "Physiological::HR at VT2", r"grip": "Physiological::Gripstrength Rechts",
}

def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z*z/n; c = p + z*z/(2*n); r = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return ((c - r)/d, (c + r)/d)

def score(rec):
    msgs = rec["request"]["messages"]; ctx = "\n".join(m["content"] for m in msgs)
    ans = rec["answer"]
    body = ans.split("**Why medium confidence:**")[0]   # appended by code, not the model
    cn = nums(ctx)
    flags = defaultdict(list)
    # A: invented values
    for m in VALUE_RE.finditer(body):
        a, b, unit = m.group(1), m.group(2), m.group(3)
        missing = [x for x in (a, b) if x and not present(x, cn)]
        if missing:
            flags["A"].append(m.group(0))
    # B: ungrounded doses
    for rx in (SETS_REPS, MINUTES, PER_WEEK):
        for m in rx.finditer(body):
            parts = re.findall(r"\d+", m.group(0))
            if any(not present(p, cn) for p in parts):
                flags["B"].append(m.group(0))
            elif rx is SETS_REPS:
                rng = re.sub(r"\s+", "", norm(m.group(2)))
                if "–" in rng and rng not in norm(re.sub(r"\s+", "", ctx)):
                    flags["B"].append(m.group(0))
    # C: misstated member values
    personal = {}
    for line in ctx.splitlines():
        for label in SELF:
            if line.startswith(label + ":"):
                personal[label] = line.split(":", 1)[1].strip().split(" ·")[0].strip()
    for label, kw in SELF.items():
        val = personal.get(label)
        if not val: continue
        for m in re.finditer(kw, body, re.I):
            window = body[max(0, m.start()-45): m.end()+45].lower()
            if label == "Typical sleep":
                hrs = re.findall(r"(\d+)\s*[–-]\s*(\d+)\s*hours", window)
                truth = re.findall(r"\d+", val)
                for h in hrs:
                    if list(h) != truth[:2] and "7 hours" not in window and not (h[0] == "7"):
                        flags["C"].append(f"sleep '{'-'.join(h)} h' vs '{val}'")
                continue
            said = next((lv for lv in LEVELS if re.search(rf"\b{lv}\b", window)), None)
            if said and said != val.lower() and not (said == "high" and val.lower() == "very high"):
                # only count when the level word is about this field (closest keyword)
                near = body[m.start(): m.end()+40].lower() + body[max(0, m.start()-25): m.start()].lower()
                if re.search(rf"\b{said}\b", near):
                    flags["C"].append(f"{kw}: said '{said}', member '{val}'")
    member = rec.get("member") or {}
    for kwrx, key in MEASURED.items():
        if key not in member: continue
        truth = float(member[key])
        for m in re.finditer(kwrx, body, re.I):
            tail = body[m.end(): m.end()+30]
            nm = re.match(rf"[^\d\[\n]{{0,18}}?({NUM})", tail)
            if not nm: continue
            v = float(norm(nm.group(1)))
            if abs(v - truth) > max(0.011, 0.01*abs(truth)) and not present(nm.group(1), nums(rec.get("personal", ""))):
                seg = tail[:nm.end()]
                if re.search(r"(target|aim|goal|below|above|at least|or below|range|<|>|zone)", seg, re.I): continue
                flags["C"].append(f"{m.group(0)} {nm.group(1)} vs {truth}")
    # D: wrong citations
    n_src = len(re.findall(r"^\[(\d+)\] \(", ctx, re.M)); n_web = len(re.findall(r"^\[Web (\d+)\] \(", ctx, re.M))
    for m in re.finditer(r"\[([^\]]+)\]", body):
        toks = [t.strip().strip("[]") for t in re.split(r"\s*,\s*", m.group(1))]
        if not all(re.fullmatch(r"\d+|Web\s*\d+|Member(?: Context)?", t, re.I) for t in toks):
            continue  # e.g. "[Watson et al., 2015]" is a literature reference, not a source marker
        for tok in toks:
            if re.fullmatch(r"\d+", tok) and int(tok) > n_src: flags["D"].append(f"[{tok}] (only {n_src} sources)")
            wm = re.fullmatch(r"Web\s*(\d+)", tok, re.I)
            if wm and int(wm.group(1)) > n_web: flags["D"].append(f"[{tok}] (only {n_web} web sources)")
    for c in rec.get("citations") or []:
        if c.get("origin") == "Validated Q&A" and "knee" in (c.get("title") or "").lower() and rec["profile"] != "M58_marco_demo":
            flags["D"].append(f"other member's Q&A: {c.get('title')}")
    return dict(flags)

if __name__ == "__main__":
    out = {}
    for path in sys.argv[1:-1]:
        recs = [json.loads(l) for l in open(path)]
        recs = [r for r in recs if "answer" in r]
        model = recs[0]["model"] if recs else path
        rows = []
        for r in recs:
            f = score(r); rows.append(dict(id=r["id"], flags=f))
        n = len(rows); summary = {"n": n}
        for cat in ("A", "B", "C", "D"):
            k = sum(1 for x in rows if x["flags"].get(cat)); lo, hi = wilson(k, n)
            summary[cat] = dict(answers=k, rate=round(k/n, 3) if n else 0, ci95=[round(lo, 3), round(hi, 3)],
                                instances=sum(len(x["flags"].get(cat, [])) for x in rows))
        k = sum(1 for x in rows if x["flags"]); lo, hi = wilson(k, n)
        summary["any"] = dict(answers=k, rate=round(k/n, 3) if n else 0, ci95=[round(lo, 3), round(hi, 3)])
        out[model] = dict(summary=summary, rows=rows)
        print(model, json.dumps(summary))
    json.dump(out, open(sys.argv[-1], "w"), ensure_ascii=False, indent=1)
