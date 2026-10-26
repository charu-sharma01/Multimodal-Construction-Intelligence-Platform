"""
Multimodal Construction Intelligence Platform
Skill Wallet Capstone Project 1

Single-file Streamlit app. No database, no local persistence: deploys as-is on
Streamlit Community Cloud. Works in demonstration mode when no Gemini key is set.

Run:  streamlit run app.py
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import random
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import streamlit as st
from PIL import Image, UnidentifiedImageError

try:  # Optional dependency: the app still runs in demo mode without it.
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None

# --------------------------------------------------------------------------- #
# Page config & styling
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Construction Intelligence Platform",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
  --ink: #1d242b;
  --concrete: #eceae5;
  --slab: #d9d6cf;
  --steel: #3b4a57;
  --hivis: #e6f04a;
  --hazard: #f08a24;
  --ok: #2f8f5b;
  --warn: #d9962b;
  --bad: #c9402f;
  --crit: #7e1f3a;
}
html, body, [class*="css"] { font-family: 'IBM Plex Sans', system-ui, sans-serif; }
h1, h2, h3, .display { font-family: 'Barlow Condensed', 'IBM Plex Sans', sans-serif !important; letter-spacing: .01em; }

.hero {
  background: var(--ink); color: #f4f3ef; padding: 1.6rem 1.8rem; border-radius: 6px;
  border-left: 14px solid var(--hivis); margin-bottom: 1.2rem;
  background-image: repeating-linear-gradient(135deg, rgba(255,255,255,.035) 0 12px, transparent 12px 24px);
}
.hero h1 { color: #fff; font-size: 2.5rem; margin: 0; line-height: 1.05; }
.hero p { color: #c9ccce; margin: .5rem 0 0 0; max-width: 62ch; }

.mode-pill { display:inline-block; padding: .15rem .7rem; border-radius: 999px; font-size: .8rem; font-weight: 600; }
.mode-live { background: #d7f0e0; color: #1b5e3a; }
.mode-demo { background: #fbe8c8; color: #7a4a05; }

.metric {
  background: var(--concrete); border: 1px solid var(--slab); border-top: 4px solid var(--steel);
  border-radius: 4px; padding: .9rem 1rem; height: 100%;
}
.metric .label { font-size: .82rem; color: #55606a; margin-bottom: .15rem; }
.metric .value { font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 2rem; color: var(--ink); line-height: 1.1; }
.metric .sub { font-size: .8rem; color: #66717a; margin-top: .2rem; }
.metric.good { border-top-color: var(--ok); }
.metric.warn { border-top-color: var(--warn); }
.metric.bad  { border-top-color: var(--bad); }

.pill { display:inline-block; padding:.18rem .65rem; border-radius: 4px; font-size:.82rem; font-weight:600; color:#fff; }
.pill.low { background: var(--ok); }
.pill.medium { background: var(--warn); color:#2b1d00; }
.pill.high { background: var(--bad); }
.pill.critical { background: var(--crit); }
.pill.neutral { background: var(--steel); }

.ppe-row { display:flex; align-items:center; justify-content:space-between; padding:.55rem .8rem;
  border:1px solid var(--slab); border-radius:4px; margin-bottom:.4rem; background:#fafaf8; }
.ppe-row .note { color:#66717a; font-size:.82rem; }

.hazard { border:1px solid var(--slab); border-left-width: 6px; border-radius:4px; padding:.7rem .9rem; margin-bottom:.6rem; background:#fafaf8; }
.hazard.low { border-left-color: var(--ok); } .hazard.medium { border-left-color: var(--warn); }
.hazard.high { border-left-color: var(--bad); } .hazard.critical { border-left-color: var(--crit); }
.hazard .title { font-weight:600; }
.hazard .fix { color:#3d4852; font-size:.9rem; margin-top:.3rem; }

.alert { border-radius:4px; padding:.8rem 1rem; margin-bottom:.55rem; border:1px solid var(--slab); background:#fafaf8; border-left: 6px solid var(--hazard); }
.alert.stop { border-left-color: var(--bad); background:#fdf0ed; }
.alert.ok { border-left-color: var(--ok); background:#eff8f2; }
.alert .t { font-weight:600; }

.milestone { display:flex; gap:.6rem; align-items:center; padding:.3rem 0; font-size:.92rem; }
.dot { width:12px; height:12px; border-radius:50%; background: var(--slab); border:2px solid var(--steel); flex:none; }
.dot.done { background: var(--ok); border-color: var(--ok); }
.dot.now { background: var(--hivis); border-color: var(--ink); }

.disclaimer { font-size:.8rem; color:#66717a; margin-top:.6rem; }
div[data-testid="stTabs"] button { font-family:'Barlow Condensed',sans-serif; font-size:1.15rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Constants / data contracts
# --------------------------------------------------------------------------- #
SEVERITIES = ["Low", "Medium", "High", "Critical"]
PPE_ITEMS = {
    "helmet": "Safety helmet",
    "hi_vis_vest": "High-visibility vest",
    "safety_boots": "Steel-toe safety boots",
    "safety_harness": "Safety harness (work at height)",
}
CRACK_TYPES = ["Hairline", "Settlement", "Structural Shear", "Thermal Expansion", "Spalling"]

PPE_PROMPT = """You are a certified construction safety auditor trained in OSHA 29 CFR 1926 and
Indian Standards (IS 456:2000, IS 3764 excavation safety, IS 4130 demolition safety, BOCW Act 1996).
Analyse the attached construction site photograph. Audit every visible worker for PPE:
helmet, high-visibility vest, steel-toe safety boots, and safety harness (only required when working
at height above ~1.8 m). Also identify other site hazards (scaffolding, edge protection, housekeeping,
electrical, excavation, material stacking, etc.).

Return ONLY valid JSON, no markdown, matching exactly this schema:
{
  "safety_score": <integer 0-100>,
  "overall_status": "Compliant" | "Needs Attention" | "Non-Compliant",
  "workers_detected": <integer>,
  "summary": "<2 sentence summary>",
  "ppe_detection": {
    "helmet":         {"status": "Compliant"|"Violation"|"Not Visible"|"Not Applicable", "note": "<short>"},
    "hi_vis_vest":    {"status": "...", "note": "<short>"},
    "safety_boots":   {"status": "...", "note": "<short>"},
    "safety_harness": {"status": "...", "note": "<short>"}
  },
  "hazards": [
    {"hazard": "<name>", "severity": "Low"|"Medium"|"High"|"Critical",
     "standard": "<OSHA/IS clause or topic>", "remedy": "<corrective action>"}
  ]
}
If the image is not a construction site, set safety_score to 0, overall_status to "Non-Compliant",
and explain in summary. Never invent details that are not visible."""

CRACK_PROMPT = """You are a structural engineer experienced with IS 456:2000, IS 13935 (seismic
retrofit) and IS 15988. Analyse the attached photograph of a concrete or masonry surface.
Classify the dominant defect as one of: Hairline, Settlement, Structural Shear, Thermal Expansion, Spalling.
Estimate crack width in mm from visual cues (state your uncertainty).

Return ONLY valid JSON, no markdown, matching exactly this schema:
{
  "defect_type": "Hairline"|"Settlement"|"Structural Shear"|"Thermal Expansion"|"Spalling",
  "severity_score": <integer 0-100, higher is worse>,
  "severity_level": "Low"|"Medium"|"High"|"Critical",
  "estimated_width_mm": <number>,
  "width_confidence": "Low"|"Medium"|"High",
  "orientation": "<horizontal|vertical|diagonal|map-pattern|stepped>",
  "root_causes": ["<cause>", ...],
  "recommended_repairs": [{"method": "<e.g. Epoxy injection>", "detail": "<how>"}],
  "urgency": "Monitor" | "Repair within 3 months" | "Repair within 2 weeks" | "Immediate - restrict access",
  "monitoring_advice": "<tell-tale / crack gauge advice>",
  "engineer_note": "<one caution about limits of photo-based assessment>"
}
If the image does not show a surface defect, use defect_type "Hairline", severity_score 0, and say so
in engineer_note."""

CHAT_SYSTEM = """You are SiteMate, a practical construction engineering assistant for Indian building
sites. Be concise (under 180 words unless asked for more), use metric units and INR, cite IS codes
(IS 456, IS 800, IS 1786, IS 4082, IS 3764, NBC 2016) and OSHA where relevant. For safety-critical
questions state the conservative action first. You do not replace a licensed structural engineer."""

# --------------------------------------------------------------------------- #
# Helpers: session, formatting, UI atoms
# --------------------------------------------------------------------------- #

def get_secret_key() -> str:
    """Read key from env / Streamlit secrets without crashing when none exist."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            key = ""
    return key


def inr(amount: float) -> str:
    """Format rupees as Lakhs / Crores."""
    if amount >= 1e7:
        return f"₹{amount / 1e7:,.2f} Cr"
    if amount >= 1e5:
        return f"₹{amount / 1e5:,.2f} Lakh"
    return f"₹{amount:,.0f}"


def metric(label: str, value: str, sub: str = "", tone: str = "") -> str:
    return (
        f'<div class="metric {tone}"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="sub">{sub}</div></div>'
    )


def pill(text: str, kind: str | None = None) -> str:
    kind = (kind or text).lower()
    if kind not in {"low", "medium", "high", "critical"}:
        kind = "neutral"
    return f'<span class="pill {kind}">{text}</span>'


def tone_for_score(score: int, invert: bool = False) -> str:
    if invert:
        score = 100 - score
    return "good" if score >= 80 else "warn" if score >= 55 else "bad"


def esc(text: Any) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def download_json(label: str, payload: dict, name: str) -> None:
    st.download_button(
        label,
        data=json.dumps(payload, indent=2, ensure_ascii=False),
        file_name=f"{name}_{datetime.now():%Y%m%d_%H%M%S}.json",
        mime="application/json",
    )


# --------------------------------------------------------------------------- #
# Gemini layer
# --------------------------------------------------------------------------- #
@dataclass
class AIConfig:
    api_key: str
    model: str

    @property
    def live(self) -> bool:
        return bool(self.api_key) and genai is not None


def load_image(uploaded) -> Image.Image | None:
    try:
        img = Image.open(uploaded)
        img.load()
        img = img.convert("RGB")
        img.thumbnail((1600, 1600))  # keeps upload payload small and fast
        return img
    except (UnidentifiedImageError, OSError) as exc:
        st.error(f"That file could not be read as an image ({exc}). Upload a JPG or PNG.")
        return None


def extract_json(text: str) -> dict:
    """Parse model output into a dict, tolerating code fences and stray prose."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def call_gemini_vision(cfg: AIConfig, prompt: str, img: Image.Image) -> dict:
    genai.configure(api_key=cfg.api_key)
    model = genai.GenerativeModel(cfg.model)
    try:
        response = model.generate_content(
            [prompt, img],
            generation_config={"response_mime_type": "application/json", "temperature": 0.2},
        )
    except TypeError:
        response = model.generate_content([prompt, img])
    return extract_json(response.text)


def clamp(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def norm_severity(value: Any, default: str = "Medium") -> str:
    s = str(value).strip().capitalize()
    return s if s in SEVERITIES else default


def normalize_ppe(raw: dict) -> dict:
    """Enforce the JSON data contract so the UI never crashes on odd model output."""
    ppe_in = raw.get("ppe_detection", {}) if isinstance(raw.get("ppe_detection"), dict) else {}
    ppe_out = {}
    for key in PPE_ITEMS:
        item = ppe_in.get(key, {}) if isinstance(ppe_in.get(key), dict) else {}
        status = str(item.get("status", "Not Visible"))
        if status not in {"Compliant", "Violation", "Not Visible", "Not Applicable"}:
            status = "Not Visible"
        ppe_out[key] = {"status": status, "note": str(item.get("note", ""))}
    hazards = []
    for h in raw.get("hazards", []) if isinstance(raw.get("hazards"), list) else []:
        if isinstance(h, dict):
            hazards.append({
                "hazard": str(h.get("hazard", "Unspecified hazard")),
                "severity": norm_severity(h.get("severity")),
                "standard": str(h.get("standard", "")),
                "remedy": str(h.get("remedy", "")),
            })
    score = clamp(raw.get("safety_score"), 0, 100, 50)
    status = raw.get("overall_status")
    if status not in {"Compliant", "Needs Attention", "Non-Compliant"}:
        status = "Compliant" if score >= 80 else "Needs Attention" if score >= 55 else "Non-Compliant"
    return {
        "safety_score": score,
        "overall_status": status,
        "workers_detected": clamp(raw.get("workers_detected"), 0, 999, 0),
        "summary": str(raw.get("summary", "")),
        "ppe_detection": ppe_out,
        "hazards": hazards,
    }


def normalize_crack(raw: dict) -> dict:
    dtype = str(raw.get("defect_type", "Hairline")).strip().title()
    if dtype not in CRACK_TYPES:
        dtype = "Hairline"
    score = clamp(raw.get("severity_score"), 0, 100, 30)
    level = norm_severity(raw.get("severity_level"),
                          "Low" if score < 30 else "Medium" if score < 60 else "High" if score < 85 else "Critical")
    try:
        width = round(float(raw.get("estimated_width_mm", 0.3)), 2)
    except (TypeError, ValueError):
        width = 0.3
    repairs = []
    for r in raw.get("recommended_repairs", []) if isinstance(raw.get("recommended_repairs"), list) else []:
        if isinstance(r, dict):
            repairs.append({"method": str(r.get("method", "Repair")), "detail": str(r.get("detail", ""))})
        elif isinstance(r, str):
            repairs.append({"method": r, "detail": ""})
    causes = [str(c) for c in raw.get("root_causes", [])] if isinstance(raw.get("root_causes"), list) else []
    return {
        "defect_type": dtype,
        "severity_score": score,
        "severity_level": level,
        "estimated_width_mm": width,
        "width_confidence": str(raw.get("width_confidence", "Low")),
        "orientation": str(raw.get("orientation", "unspecified")),
        "root_causes": causes,
        "recommended_repairs": repairs,
        "urgency": str(raw.get("urgency", "Monitor")),
        "monitoring_advice": str(raw.get("monitoring_advice", "")),
        "engineer_note": str(raw.get("engineer_note", "")),
    }


# --------------------------------------------------------------------------- #
# Demonstration mode (deterministic, seeded from the image bytes)
# --------------------------------------------------------------------------- #

def _seed(img: Image.Image) -> random.Random:
    digest = hashlib.sha256(img.tobytes()[:200000]).hexdigest()
    return random.Random(int(digest[:12], 16))


def demo_ppe(img: Image.Image) -> dict:
    rng = _seed(img)
    statuses = {k: rng.choice(["Compliant", "Compliant", "Violation", "Not Visible"]) for k in PPE_ITEMS}
    notes = {"Compliant": "Worn correctly (demo)", "Violation": "Missing or worn incorrectly (demo)",
             "Not Visible": "Cannot be confirmed from this angle (demo)"}
    hazard_pool = [
        ("Unprotected floor edge", "High", "OSHA 1926.502 / IS 7969", "Install double-rail edge protection with toe board."),
        ("Loose material stacking", "Medium", "IS 7969 housekeeping", "Stack on level ground, max 1.5 m, with stoppers."),
        ("Exposed temporary wiring", "Critical", "IS 732 / OSHA 1926.405", "Isolate supply, use armoured cable with ELCB."),
        ("Scaffold without full planking", "High", "IS 4014 / OSHA 1926.451", "Fully plank platforms; tag scaffold after inspection."),
        ("Debris in walkways", "Low", "IS 7969", "Assign daily housekeeping crew; clear access routes."),
        ("Unsupported trench wall", "Critical", "IS 3764 / OSHA 1926.651", "Provide shoring or battered slopes before entry."),
    ]
    hazards = [dict(zip(["hazard", "severity", "standard", "remedy"], h)) for h in rng.sample(hazard_pool, rng.randint(2, 4))]
    penalty = {"Violation": 14, "Not Visible": 4, "Compliant": 0}
    score = 100 - sum(penalty[s] for s in statuses.values()) - sum({"Low": 2, "Medium": 6, "High": 11, "Critical": 18}[h["severity"]] for h in hazards)
    return normalize_ppe({
        "safety_score": max(8, score),
        "workers_detected": rng.randint(2, 9),
        "summary": "Demonstration result generated without an AI model. Add a Gemini API key for a real image audit.",
        "ppe_detection": {k: {"status": v, "note": notes[v]} for k, v in statuses.items()},
        "hazards": hazards,
    })


def demo_crack(img: Image.Image) -> dict:
    rng = _seed(img)
    dtype = rng.choice(CRACK_TYPES)
    table = {
        "Hairline": (0.2, 15, ["Plastic shrinkage", "Rapid surface drying during curing"],
                     [("Surface sealing", "Apply flexible polymer-modified cementitious coating.")], "Monitor"),
        "Settlement": (2.5, 68, ["Differential foundation settlement", "Poor soil bearing or waterlogging"],
                       [("Underpinning review", "Geotechnical check, then underpin or grout the footing."),
                        ("Epoxy injection", "Stitch cracks after movement has stabilised.")], "Repair within 2 weeks"),
        "Structural Shear": (3.5, 88, ["Inadequate shear reinforcement or stirrup spacing", "Overloading"],
                             [("Restrict access", "Prop the member and call a structural engineer."),
                              ("Structural re-grouting", "Jacket or wrap member per IS 15988 after design check.")], "Immediate - restrict access"),
        "Thermal Expansion": (0.6, 35, ["No expansion joints", "Temperature cycling"],
                              [("Joint formation", "Cut control joint and seal with polyurethane sealant.")], "Repair within 3 months"),
        "Spalling": (1.0, 55, ["Rebar corrosion from carbonation or chlorides", "Low concrete cover"],
                     [("Patch repair", "Remove loose concrete, treat rebar with zinc-rich primer, apply repair mortar."),
                      ("Epoxy injection", "Seal associated cracks to stop water ingress.")], "Repair within 2 weeks"),
    }
    width, score, causes, repairs, urgency = table[dtype]
    score = clamp(score + rng.randint(-6, 6), 0, 100, score)
    level = "Low" if score < 30 else "Medium" if score < 60 else "High" if score < 85 else "Critical"
    return normalize_crack({
        "defect_type": dtype, "severity_score": score, "severity_level": level,
        "estimated_width_mm": round(width * rng.uniform(0.8, 1.2), 2), "width_confidence": "Low",
        "orientation": rng.choice(["vertical", "diagonal", "horizontal", "stepped"]),
        "root_causes": causes,
        "recommended_repairs": [{"method": m, "detail": d} for m, d in repairs],
        "urgency": urgency,
        "monitoring_advice": "Fix a crack gauge or plaster tell-tale across the crack and log width weekly.",
        "engineer_note": "Demonstration result. A real assessment needs on-site inspection by a licensed engineer.",
    })


# --------------------------------------------------------------------------- #
# Planning & valuation model (documented assumptions, editable below)
# --------------------------------------------------------------------------- #
STRUCTURES = {
    # construction ₹/sqft by tier (T1, T2, T3), steel kg/sqft, cement bags/sqft
    "Load-bearing masonry (G+1)": {"cost": (1800, 1500, 1250), "steel": 2.0, "cement": 0.38, "quality": 0.90},
    "RCC framed residential":      {"cost": (2300, 1950, 1650), "steel": 4.0, "cement": 0.45, "quality": 1.00},
    "Premium / luxury residential": {"cost": (3600, 3000, 2500), "steel": 5.0, "cement": 0.50, "quality": 1.25},
    "Commercial RCC":              {"cost": (2800, 2300, 1900), "steel": 5.5, "cement": 0.48, "quality": 1.15},
    "Steel / PEB industrial":      {"cost": (2500, 2100, 1800), "steel": 8.0, "cement": 0.25, "quality": 0.85},
}
# Market rate (₹/sqft, completed, land included) by tier. Illustrative planning figures.
MARKET_RATE = {"Tier 1": 11000, "Tier 2": 6200, "Tier 3": 3600}
TIER_INDEX = {"Tier 1": 0, "Tier 2": 1, "Tier 3": 2}
LAND_SHARE = 0.35  # share of completed value attributable to land, present from day one
MILESTONES = [
    ("Site prep & foundation", 15), ("Plinth", 25), ("Superstructure (columns, slabs)", 60),
    ("Masonry & roofing", 75), ("MEP & finishing", 95), ("Handover", 100),
]


def project_model(structure: str, sqft: int, tier: str, pct: int) -> dict:
    spec = STRUCTURES[structure]
    rate = spec["cost"][TIER_INDEX[tier]]
    budget = rate * sqft * 1.08  # +8% contingency and approvals
    capex = budget * pct / 100
    completed_value = MARKET_RATE[tier] * spec["quality"] * sqft
    current_value = completed_value * (LAND_SHARE + (1 - LAND_SHARE) * pct / 100)
    steel_t = spec["steel"] * sqft / 1000
    cement_bags = spec["cement"] * sqft
    return {
        "rate_per_sqft": rate, "budget": budget, "capex": capex,
        "completed_value": completed_value, "current_value": current_value,
        "steel_total_t": steel_t, "steel_used_t": steel_t * pct / 100,
        "cement_total_bags": cement_bags, "cement_used_bags": cement_bags * pct / 100,
        "expected_gain": completed_value - budget,
    }


def render_3d_prompt(structure: str, tier: str, sqft: int, pct: int, style: str) -> str:
    stage = ("bare foundation excavation" if pct < 15 else "concrete frame under construction" if pct < 60
             else "brick walls and roof slab, plastering in progress" if pct < 95 else "fully finished building")
    return (f"architectural 3D render of a {structure.lower()} building, {sqft} sq ft, {style} style, "
            f"located in an Indian {tier.lower()} city, stage: {stage}, golden hour light, "
            f"photorealistic, wide angle, detailed materials")


def pollinations_url(prompt: str, seed: int) -> str:
    q = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{q}?width=1024&height=640&model=flux&seed={seed}&nologo=true"


# --------------------------------------------------------------------------- #
# Weather advisory
# --------------------------------------------------------------------------- #
WEATHER = {
    "Normal": {
        "icon": "🌤️", "level": "ok",
        "alerts": [
            ("Standard operations", "ok", "All trades may proceed. Run the toolbox talk and confirm PPE at the gate."),
            ("Hydration and shade", "ok", "Provide potable water points and a shaded rest area."),
        ],
        "checklist": ["Inspect scaffolds and edge protection", "Verify lifting-gear certificates", "Log daily headcount and permits"],
    },
    "High Wind": {
        "icon": "💨", "level": "stop",
        "alerts": [
            ("Suspend crane operations", "stop", "Stop lifting when wind at the boom tip exceeds the crane's limit (commonly about 36 km/h, 10 m/s). Lower and secure the hook and boom."),
            ("Secure loose materials", "warn", "Tie down sheeting, formwork panels and scaffold boards; stack light materials low."),
            ("Halt work at height", "stop", "No work on scaffolds, roof edges or tower cranes. Clear nets and hoardings of debris."),
            ("Dust control", "warn", "Wet down excavations and wear eye protection."),
        ],
        "checklist": ["Check scaffold ties and bracing", "Anchor temporary sheds", "Tag out unattended lifting equipment"],
    },
    "Heavy Rain": {
        "icon": "🌧️", "level": "stop",
        "alerts": [
            ("Electrical hazard mitigation", "stop", "De-energise temporary panels in wet areas, check ELCB/RCCB trip tests, keep cable joints raised and sealed."),
            ("Stop concreting if rain is imminent", "stop", "Cover fresh concrete with tarpaulin. Do not place or finish concrete in rain; protect from washout and re-vibrate or reject if rain-damaged."),
            ("Excavation and trench safety", "stop", "Evacuate trenches, inspect shoring after rain, run dewatering pumps."),
            ("Slip and fall control", "warn", "Place anti-slip mats on ramps, light walkways, and stop work on wet scaffolds."),
        ],
        "checklist": ["Clear site drainage", "Cover cement and keep it off the ground", "Inspect trench walls before re-entry"],
    },
    "Extreme Heat": {
        "icon": "🔥", "level": "warn",
        "alerts": [
            ("Concrete curing protocol", "warn", "Pour early morning or evening, use chilled water/ice in the mix, keep concrete temperature under 35 °C (IS 7861 Part 1), and start wet curing immediately (7 days minimum, 10 for blended cements)."),
            ("Heat-stress management", "stop", "Enforce rest-shade cycles, ORS and water every 20 minutes, and watch for heat exhaustion. Restrict heavy work from 12:00 to 15:00."),
            ("Formwork and steel", "warn", "Wet formwork and shade rebar before placing; surfaces can exceed 50 °C."),
            ("Fire risk", "warn", "Keep extinguishers near hot work and stored flammables."),
        ],
        "checklist": ["Set up cooling stations", "Reschedule heavy pours", "Brief crew on heat-illness signs"],
    },
}


def demo_chat_reply(question: str, weather: str) -> str:
    q = question.lower()
    kb = [
        (("cur",), "Cure OPC concrete for at least 7 days (10 to 14 for PPC or slag cement) per IS 456 clause 13.5. Keep surfaces continuously wet, or use curing compound and cover with wet hessian."),
        (("slump", "workab"), "Typical slump (IS 456 Table 7): 25-75 mm for lightly reinforced slabs/beams, 50-100 mm for heavily reinforced sections, 75-100 mm for columns. Add admixture, not water, to raise workability."),
        (("cement", "mix", "m20", "m25"), "Nominal mixes: M20 is about 1:1.5:3. Prefer design mix for M25 and above. Roughly 8 bags of cement per cubic metre for M20."),
        (("steel", "rebar", "tmt", "cover"), "Use Fe500D TMT (IS 1786). Minimum cover (IS 456 Table 16, mild exposure): 20 mm slabs/walls, 25 mm beams, 40 mm columns, 50 mm footings. Lap length is about 40-50 d depending on grade."),
        (("crack",), "Measure width first. Under 0.3 mm in moderate exposure is generally acceptable (IS 456 cl. 35.3.2). Wider, diagonal, or growing cracks need an engineer. Install a crack gauge and log weekly."),
        (("harness", "height", "scaffold", "fall"), "Use a full-body harness with double lanyard anchored above the D-ring wherever work is above 1.8 m without edge protection. Inspect scaffolds before every shift."),
        (("crane", "lift", "wind"), "Stop crane lifts if wind exceeds the manufacturer's limit (commonly about 10 m/s at the boom tip). Check the load chart, outrigger bearing and the signaller's communication."),
        (("rain", "monsoon"), "In rain: cover fresh concrete, de-energise wet electrical points, check trench shoring and dewater. Resume only after inspection."),
        (("cost", "budget", "estimate", "rate"), "Use the Planning tab for a quick budget. Always keep a 5-10% contingency, and track cost per sqft against the plan monthly."),
        (("excavat", "trench"), "Shore or batter trench walls deeper than 1.5 m (IS 3764). Keep spoil at least 0.6 m from the edge, provide ladders every 7.5 m, and inspect after rain."),
    ]
    for keys, ans in kb:
        if any(k in q for k in keys):
            return ans + f"\n\n*(Demo mode. Current weather setting: {weather}.)*"
    return ("I can help with curing, mix design, rebar, scaffolding, crane safety, excavations, cracks, and costs. "
            "Try asking about one of these. *(Demo mode: add a Gemini API key for open-ended answers.)*")


def gemini_chat_reply(cfg: AIConfig, history: list[dict], weather: str, context: str) -> str:
    genai.configure(api_key=cfg.api_key)
    system = f"{CHAT_SYSTEM}\nCurrent site weather: {weather}.\n{context}"
    try:
        model = genai.GenerativeModel(cfg.model, system_instruction=system)
        prefix = []
    except TypeError:
        model = genai.GenerativeModel(cfg.model)
        prefix = [{"role": "user", "parts": [system]}, {"role": "model", "parts": ["Understood."]}]
    msgs = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in history[:-1]]
    chat = model.start_chat(history=prefix + msgs)
    return chat.send_message(history[-1]["content"]).text


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #

def sidebar() -> AIConfig:
    with st.sidebar:
        st.markdown("### Gemini connection")
        key_input = st.text_input("API key", type="password", placeholder="Paste key, or leave empty for demo",
                                  help="Used only in this session. Never stored or logged.")
        model = st.text_input("Model", value="gemini-2.0-flash",
                              help="Any vision-capable Gemini model, for example gemini-2.0-flash or gemini-1.5-pro.")
        cfg = AIConfig(api_key=(key_input or get_secret_key()).strip(), model=model.strip())
        if cfg.live:
            st.markdown('<span class="mode-pill mode-live">Live AI mode</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="mode-pill mode-demo">Demonstration mode</span>', unsafe_allow_html=True)
            if cfg.api_key and genai is None:
                st.warning("google-generativeai is not installed, so demo mode is on.")
            else:
                st.caption("Results are simulated until you add a key.")
        st.divider()
        st.markdown("### What's inside")
        st.markdown(
            "- **Site Safety**: PPE and hazard audit from a photo\n"
            "- **Crack Diagnostics**: defect class, width, repair plan\n"
            "- **Planning & Valuation**: budget, materials, asset value\n"
            "- **Daily Assistant**: weather protocols and chat"
        )
        st.divider()
        st.markdown("### Architecture")
        st.code(
            "Photo → Pillow resize\n"
            "      → Gemini vision prompt\n"
            "      → JSON → validator\n"
            "      → cards, pills, export",
            language="text",
        )
        st.caption("Standards referenced: OSHA 29 CFR 1926, IS 456:2000, NBC 2016. AI output is advisory and does not replace a certified inspector.")
    return cfg


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #

def run_vision(cfg: AIConfig, prompt: str, img: Image.Image, demo_fn, norm_fn) -> dict | None:
    if not cfg.live:
        return demo_fn(img)
    try:
        return norm_fn(call_gemini_vision(cfg, prompt, img))
    except json.JSONDecodeError:
        st.error("The model reply was not valid JSON. Run the analysis again, or try a clearer photo.")
    except Exception as exc:  # network, quota, bad key, safety block
        st.error(f"Gemini request failed: {exc}")
        if st.button("Show a demonstration result instead", key=f"fallback_{prompt[:20]}"):
            return demo_fn(img)
    return None


def tab_safety(cfg: AIConfig) -> None:
    st.subheader("Site safety and PPE audit")
    st.caption("Upload a site photo. Each worker is checked for helmet, vest, boots and harness.")
    up = st.file_uploader("Site photo", type=["jpg", "jpeg", "png"], key="ppe_up")
    if up:
        img = load_image(up)
        if img is not None:
            col_img, col_btn = st.columns([3, 1])
            col_img.image(img, caption="Photo to audit", use_container_width=True)
            if col_btn.button("Run safety audit", type="primary", key="ppe_run"):
                with st.spinner("Auditing site photo..."):
                    result = run_vision(cfg, PPE_PROMPT, img, demo_ppe, normalize_ppe)
                if result:
                    st.session_state["ppe_result"] = result
    else:
        st.info("Upload a JPG or PNG to begin.")

    res = st.session_state.get("ppe_result")
    if not res:
        return
    st.divider()
    score, status = res["safety_score"], res["overall_status"]
    kind = {"Compliant": "low", "Needs Attention": "medium", "Non-Compliant": "high"}[status]
    violations = sum(1 for v in res["ppe_detection"].values() if v["status"] == "Violation")
    worst = max((SEVERITIES.index(h["severity"]) for h in res["hazards"]), default=-1)
    c = st.columns(4)
    c[0].markdown(metric("Safety score", f"{score}/100", "Higher is safer", tone_for_score(score)), unsafe_allow_html=True)
    c[1].markdown(metric("Overall status", pill(status, kind), "Based on PPE and hazards"), unsafe_allow_html=True)
    c[2].markdown(metric("Workers detected", str(res["workers_detected"]), f"{violations} PPE violation type(s)",
                         "bad" if violations else "good"), unsafe_allow_html=True)
    c[3].markdown(metric("Hazards found", str(len(res["hazards"])),
                         f"Worst: {SEVERITIES[worst] if worst >= 0 else 'None'}",
                         "bad" if worst >= 2 else "warn" if worst >= 0 else "good"), unsafe_allow_html=True)
    if res["summary"]:
        st.write("")
        st.write(res["summary"])

    left, right = st.columns(2)
    with left:
        st.markdown("#### PPE checklist")
        for key, label in PPE_ITEMS.items():
            item = res["ppe_detection"][key]
            kind = {"Compliant": "low", "Violation": "high", "Not Visible": "medium", "Not Applicable": "neutral"}[item["status"]]
            st.markdown(
                f'<div class="ppe-row"><div><b>{label}</b><div class="note">{esc(item["note"])}</div></div>'
                f'{pill(item["status"], kind)}</div>', unsafe_allow_html=True)
    with right:
        st.markdown("#### Hazards and remedies")
        if not res["hazards"]:
            st.success("No hazards identified in this photo.")
        for h in sorted(res["hazards"], key=lambda x: -SEVERITIES.index(x["severity"])):
            st.markdown(
                f'<div class="hazard {h["severity"].lower()}"><div class="title">{esc(h["hazard"])} {pill(h["severity"])}</div>'
                f'<div class="note">{esc(h["standard"])}</div><div class="fix"><b>Fix:</b> {esc(h["remedy"])}</div></div>',
                unsafe_allow_html=True)
    download_json("Download JSON report", res, "safety_audit")


def tab_cracks(cfg: AIConfig) -> None:
    st.subheader("Crack diagnostics and structural integrity")
    st.caption("Upload a close-up of a concrete or masonry surface. Include a coin or ruler for scale if you can.")
    up = st.file_uploader("Surface photo", type=["jpg", "jpeg", "png"], key="crack_up")
    if up:
        img = load_image(up)
        if img is not None:
            col_img, col_btn = st.columns([3, 1])
            col_img.image(img, caption="Surface to diagnose", use_container_width=True)
            if col_btn.button("Diagnose defect", type="primary", key="crack_run"):
                with st.spinner("Analysing surface..."):
                    result = run_vision(cfg, CRACK_PROMPT, img, demo_crack, normalize_crack)
                if result:
                    st.session_state["crack_result"] = result
    else:
        st.info("Upload a JPG or PNG to begin.")

    r = st.session_state.get("crack_result")
    if not r:
        return
    st.divider()
    sev = r["severity_level"]
    c = st.columns(4)
    c[0].markdown(metric("Defect type", r["defect_type"], f"Orientation: {esc(r['orientation'])}"), unsafe_allow_html=True)
    c[1].markdown(metric("Severity score", f"{r['severity_score']}/100", pill(sev),
                         tone_for_score(r["severity_score"], invert=True)), unsafe_allow_html=True)
    c[2].markdown(metric("Estimated width", f"{r['estimated_width_mm']} mm",
                         f"Confidence: {esc(r['width_confidence'])}. IS 456 limit is about 0.3 mm"),
                  unsafe_allow_html=True)
    c[3].markdown(metric("Urgency", esc(r["urgency"]), "Recommended response",
                         "bad" if sev in ("High", "Critical") else "warn" if sev == "Medium" else "good"),
                  unsafe_allow_html=True)
    if r["severity_level"] == "Critical" or r["urgency"].startswith("Immediate"):
        st.error("Restrict access to the affected area and consult a structural engineer before any further loading.")
    st.progress(r["severity_score"] / 100, text="Severity")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Probable root causes")
        for cause in r["root_causes"] or ["Not determined from the photo."]:
            st.markdown(f"- {cause}")
        if r["monitoring_advice"]:
            st.markdown("#### Monitoring")
            st.write(r["monitoring_advice"])
    with right:
        st.markdown("#### Recommended repairs")
        for rep in r["recommended_repairs"] or [{"method": "Engineer inspection", "detail": "On-site assessment needed."}]:
            st.markdown(f"**{rep['method']}**  \n{rep['detail']}")
    if r["engineer_note"]:
        st.caption(r["engineer_note"])
    download_json("Download JSON report", r, "crack_diagnostic")


def tab_planning() -> None:
    st.subheader("Planning and real estate valuation")
    c1, c2, c3 = st.columns(3)
    structure = c1.selectbox("Structure type", list(STRUCTURES))
    tier = c2.selectbox("Location tier", list(TIER_INDEX), help="Tier 1: metros. Tier 2: large cities. Tier 3: smaller towns.")
    sqft = c3.number_input("Built-up area (sq ft)", min_value=200, max_value=500000, value=1800, step=100)
    pct = st.slider("Completion (%)", 0, 100, 40)

    m = project_model(structure, int(sqft), tier, pct)
    st.session_state["project_context"] = (
        f"Project: {structure}, {sqft} sq ft, {tier}, {pct}% complete, budget {inr(m['budget'])}.")

    k = st.columns(4)
    k[0].markdown(metric("Total project budget", inr(m["budget"]), f"₹{m['rate_per_sqft']:,}/sq ft + 8% contingency"), unsafe_allow_html=True)
    k[1].markdown(metric("Capital spent so far", inr(m["capex"]), f"{pct}% of budget"), unsafe_allow_html=True)
    k[2].markdown(metric("Current asset value", inr(m["current_value"]), "Land plus built portion", "good"), unsafe_allow_html=True)
    k[3].markdown(metric("Value on completion", inr(m["completed_value"]),
                         f"Indicative gain {inr(m['expected_gain'])}" if m["expected_gain"] > 0 else "Below build cost at this tier",
                         "good" if m["expected_gain"] > 0 else "bad"), unsafe_allow_html=True)

    st.write("")
    s = st.columns(2)
    s[0].markdown(metric("Steel (TMT)", f"{m['steel_total_t']:.1f} t",
                         f"{m['steel_used_t']:.1f} t used, {m['steel_total_t'] - m['steel_used_t']:.1f} t to order"), unsafe_allow_html=True)
    s[1].markdown(metric("Cement", f"{m['cement_total_bags']:,.0f} bags",
                         f"{m['cement_used_bags']:,.0f} used, {m['cement_total_bags'] - m['cement_used_bags']:,.0f} to order (50 kg)"),
                  unsafe_allow_html=True)

    st.markdown("#### Milestone progress")
    st.progress(pct / 100, text=f"{pct}% complete")
    rows, prev = [], 0
    for name, end in MILESTONES:
        state = "done" if pct >= end else "now" if pct > prev else ""
        rows.append(f'<div class="milestone"><span class="dot {state}"></span><span>{name} (to {end}%)</span></div>')
        prev = end
    st.markdown("".join(rows), unsafe_allow_html=True)
    st.markdown(
        '<div class="disclaimer">Estimates use illustrative planning rates (editable in the STRUCTURES and MARKET_RATE tables in the code). '
        'Get a quantity surveyor estimate and a registered valuer\'s report before any financial decision.</div>',
        unsafe_allow_html=True)

    st.markdown("#### Conceptual 3D rendering")
    style = st.selectbox("Architectural style", ["Contemporary", "Modern minimalist", "Indo-colonial", "Industrial"])
    prompt = st.text_area("Image prompt", value=render_3d_prompt(structure, tier, int(sqft), pct, style), height=90)
    if st.button("Generate rendering", key="render"):
        seed = random.randint(1, 10**6)
        url = pollinations_url(prompt, seed)
        try:
            st.image(url, caption=f"Pollinations AI concept (seed {seed}). Not a design drawing.", use_container_width=True)
        except Exception as exc:
            st.warning(f"The image service did not respond ({exc}). Open the link directly: {url}")
        st.caption("If the image does not appear, the free service may be busy. Try again in a moment.")


def tab_assistant(cfg: AIConfig) -> None:
    st.subheader("Daily site assistant and weather advisory")
    weather = st.radio("Today's weather", list(WEATHER), horizontal=True, key="weather")
    w = WEATHER[weather]
    st.markdown(f"#### {w['icon']} Advisory for {weather.lower()} conditions")
    for title, level, body in w["alerts"]:
        cls = {"stop": "stop", "ok": "ok"}.get(level, "")
        st.markdown(f'<div class="alert {cls}"><div class="t">{title}</div>{esc(body)}</div>', unsafe_allow_html=True)
    with st.expander("Start-of-shift checklist"):
        for item in w["checklist"]:
            st.checkbox(item, key=f"chk_{weather}_{item}")

    st.divider()
    st.markdown("#### Ask the site engineer")
    if "chat" not in st.session_state:
        st.session_state["chat"] = [{"role": "assistant",
                                     "content": "Hi, I'm SiteMate. Ask about curing, rebar, scaffolds, cranes, trenches or costs."}]
    top = st.columns([6, 1])
    if top[1].button("Clear chat"):
        del st.session_state["chat"]
        st.rerun()
    for msg in st.session_state["chat"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if question := st.chat_input("Ask a construction question"):
        st.session_state["chat"].append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    if cfg.live:
                        reply = gemini_chat_reply(cfg, st.session_state["chat"], weather,
                                                  st.session_state.get("project_context", ""))
                    else:
                        reply = demo_chat_reply(question, weather)
                except Exception as exc:
                    reply = f"I could not reach Gemini ({exc}). Here is the offline answer:\n\n{demo_chat_reply(question, weather)}"
            st.markdown(reply)
        st.session_state["chat"].append({"role": "assistant", "content": reply})


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    cfg = sidebar()
    st.markdown(
        '<div class="hero"><h1>Multimodal Construction Intelligence Platform</h1>'
        '<p>Audit site safety, diagnose cracks, budget the build and value the asset, all from one workspace.</p></div>',
        unsafe_allow_html=True)
    t1, t2, t3, t4 = st.tabs(["Site Safety & PPE", "Crack Diagnostics", "Planning & Valuation", "Daily Assistant"])
    with t1:
        tab_safety(cfg)
    with t2:
        tab_cracks(cfg)
    with t3:
        tab_planning()
    with t4:
        tab_assistant(cfg)


if __name__ == "__main__":
    main()
