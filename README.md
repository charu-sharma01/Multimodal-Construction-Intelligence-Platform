# Multimodal Construction Intelligence Platform

Skill Wallet Capstone Project 1 (Generative AI | Real Estate Decision Support)

A Streamlit app that analyses construction site photos with a multimodal LLM (Google Gemini) to audit PPE safety, diagnose concrete cracks, estimate project cost and asset value in INR, and give weather-aware daily safety protocols. It has no database and needs no local setup beyond Python, so it deploys in one step on Streamlit Community Cloud.

## Features

| Tab | What it does |
|---|---|
| **Site Safety & PPE** | Upload a site photo. Checks helmets, high-vis vests, steel-toe boots and harnesses against OSHA and IS standards. Returns a safety score (0-100), overall status, PPE checklist and hazards with severity (Low, Medium, High, Critical) and remedies. JSON report download. |
| **Crack Diagnostics** | Upload a concrete or wall photo. Classifies the defect (Hairline, Settlement, Structural Shear, Thermal Expansion, Spalling), estimates crack width in mm, and lists root causes, repairs and urgency. JSON report download. |
| **Planning & Valuation** | Inputs: structure type, built-up sq ft, location tier (1/2/3), completion %. Outputs: total budget, capital spent, current asset value and value on completion in Lakhs/Crores, steel and cement requirements, milestone tracker, and a Pollinations (Flux) 3D concept rendering. |
| **Daily Assistant** | Weather selector (Normal, High Wind, Heavy Rain, Extreme Heat) with dynamic safety alerts and a shift checklist. Multi-turn chatbot for construction engineering questions. |

The sidebar holds the Gemini API key field, model name, architecture overview and feature list. **If no key is supplied, the app runs in demonstration mode** with simulated results, so it never breaks during a demo.

## Quick start

Requires Python 3.9 or newer.

```bash
git clone <your-repo-url>
cd <your-repo>
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501.

## Configuring Gemini

1. Create a free key at https://aistudio.google.com/apikey.
2. Use one of these:
   - Paste it into the sidebar field (kept in the session only), or
   - Set an environment variable: `export GEMINI_API_KEY="your-key"`, or
   - Create `.streamlit/secrets.toml`:
     ```toml
     GEMINI_API_KEY = "your-key"
     ```
3. The sidebar badge changes from **Demonstration mode** to **Live AI mode**.

The default model is `gemini-2.0-flash`. Change it in the sidebar to any vision-capable Gemini model your key can access (for example `gemini-1.5-pro` if still available). Never commit your key to Git. Add `.streamlit/secrets.toml` to `.gitignore`.

## Deploy to Streamlit Community Cloud

1. Push `app.py`, `requirements.txt` and this README to a GitHub repository.
2. Go to https://share.streamlit.io and choose **New app**.
3. Select the repository, branch, and `app.py` as the main file.
4. Under **Advanced settings → Secrets**, add `GEMINI_API_KEY = "your-key"` (optional; visitors can also paste their own key).
5. Click **Deploy**.

## Project structure

```
.
├── app.py             # entire application
├── requirements.txt   # streamlit, pillow, google-generativeai
└── README.md
```

Inside `app.py`:

- **Gemini layer:** image loading and resizing with Pillow, vision calls, JSON extraction.
- **Data contract validators:** `normalize_ppe()` and `normalize_crack()` enforce the JSON schema so odd model output cannot crash the UI.
- **Demo mode:** deterministic simulated results seeded from the image bytes.
- **Valuation model:** `STRUCTURES`, `MARKET_RATE` and `project_model()`.
- **Weather advisory:** the `WEATHER` dictionary.
- **UI:** one function per tab, plus `sidebar()` and `main()`.

## JSON data contracts

**Safety audit**

```json
{
  "safety_score": 72,
  "overall_status": "Needs Attention",
  "workers_detected": 4,
  "summary": "...",
  "ppe_detection": {
    "helmet": {"status": "Compliant", "note": "..."},
    "hi_vis_vest": {"status": "Violation", "note": "..."},
    "safety_boots": {"status": "Not Visible", "note": "..."},
    "safety_harness": {"status": "Not Applicable", "note": "..."}
  },
  "hazards": [
    {"hazard": "Unprotected floor edge", "severity": "High",
     "standard": "OSHA 1926.502", "remedy": "Install double-rail edge protection."}
  ]
}
```

**Crack diagnostic**

```json
{
  "defect_type": "Settlement",
  "severity_score": 68,
  "severity_level": "High",
  "estimated_width_mm": 2.5,
  "width_confidence": "Low",
  "orientation": "diagonal",
  "root_causes": ["Differential foundation settlement"],
  "recommended_repairs": [{"method": "Epoxy injection", "detail": "..."}],
  "urgency": "Repair within 2 weeks",
  "monitoring_advice": "...",
  "engineer_note": "..."
}
```

## Customising the valuation model

The numbers in Tab 3 are **illustrative planning assumptions**, not market data. Edit them in `app.py`:

- `STRUCTURES`: construction cost per sq ft for Tier 1/2/3, steel kg/sq ft, cement bags/sq ft, quality multiplier.
- `MARKET_RATE`: completed-property rate per sq ft by tier.
- `LAND_SHARE`: share of completed value that is land (default 35%).
- Budget includes an 8% contingency (`project_model()`).

Current asset value = completed value × (land share + (1 − land share) × completion %).

## Troubleshooting

| Problem | Fix |
|---|---|
| Stuck in demonstration mode | Check the key is non-empty and `google-generativeai` installed (`pip install -r requirements.txt`). |
| "Gemini request failed" | Invalid key, exhausted quota, retired model name or a safety block. Try another model name or photo. |
| "Reply was not valid JSON" | Run the analysis again; clearer, well-lit photos help. |
| 3D rendering does not load | The free Pollinations service may be busy. Retry after a moment. |
| `use_container_width` warning | Upgrade Streamlit to the latest version. |

## Limitations and disclaimer

- AI output is advisory. It does not replace a certified safety officer, a licensed structural engineer, a quantity surveyor or a registered valuer.
- Crack width from a photo is approximate. Include a ruler or coin in the frame for better estimates.
- Images are sent to the Gemini API in live mode. Do not upload sensitive or confidential site imagery without your organisation's approval.

## Tech stack

Python 3.9+, Streamlit, Google Gemini (multimodal), Pillow, Pollinations/Flux image API, JSON data contracts.
