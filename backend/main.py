"""
PAIMANA AI - FastAPI Backend
Serves ML model results, predictions, alerts, and analytics via REST API.
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import numpy as np
import json
import joblib

app = FastAPI(
    title="PAIMANA AI API",
    description="AI-powered Predictive Analytics & Early Warning System for Infrastructure Monitoring",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# LOAD DATA & MODELS
# ============================================================
RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'ml', 'results')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'ml', 'models')

def load_csv(filename):
    filepath = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(filepath):
        return pd.read_csv(filepath, encoding='utf-8-sig')
    return pd.DataFrame()

def load_json(filename):
    filepath = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}

# Load data at startup
projects_df = load_csv('projects_with_risk_scores.csv')
alerts_df = load_csv('alerts.csv')
benchmarks_df = load_csv('sector_benchmarks.csv')
cost_drivers_df = load_csv('cost_drivers.csv')
summary_data = load_json('summary.json')
comparison_data = load_json('model_comparison.json')

# Clean NaN for JSON serialization
def clean_for_json(obj):
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    return obj

def df_to_records(df, max_rows=None):
    if max_rows:
        df = df.head(max_rows)
    records = df.replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict('records')
    return clean_for_json(records)


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/api/health")
def api_health():
    return {"message": "PAIMANA AI API", "status": "running", "version": "1.0.0"}


# --- DASHBOARD SUMMARY ---
@app.get("/api/summary")
def get_summary():
    """Get overall dashboard summary stats."""
    total = len(projects_df)
    
    risk_dist = {}
    if 'risk_category' in projects_df.columns:
        risk_dist = projects_df['risk_category'].value_counts().to_dict()
    
    return clean_for_json({
        "total_projects": total,
        "total_original_cost_cr": round(float(pd.to_numeric(projects_df['original_cost_cr'], errors='coerce').sum()), 2),
        "total_revised_cost_cr": round(float(pd.to_numeric(projects_df['revised_cost_cr'], errors='coerce').sum()), 2),
        "total_expenditure_cr": round(float(pd.to_numeric(projects_df['cumulative_expenditure_cr'], errors='coerce').sum()), 2),
        "avg_physical_progress": round(float(pd.to_numeric(projects_df['physical_progress_pct'], errors='coerce').mean()), 1),
        "cost_overrun_rate": round(float(projects_df['has_cost_overrun'].mean() * 100), 1),
        "time_overrun_rate": round(float(projects_df['has_time_overrun'].mean() * 100), 1),
        "avg_risk_score": round(float(pd.to_numeric(projects_df['risk_score'], errors='coerce').mean()), 1),
        "risk_distribution": risk_dist,
        "total_alerts": len(alerts_df),
        "critical_alerts": int(len(alerts_df[alerts_df['severity'] == 'CRITICAL'])) if len(alerts_df) > 0 else 0,
        "total_ministries": int(projects_df['ministry'].nunique()),
        "total_sectors": int(projects_df['sector'].nunique()),
        "model_accuracy": summary_data.get('comparison', {}),
    })


# --- PROJECTS ---
@app.get("/api/projects")
def get_projects(
    sector: str = None,
    ministry: str = None,
    state: str = None,
    risk_category: str = None,
    sort_by: str = "risk_score",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
):
    """Get projects with filters, sorting, and pagination."""
    df = projects_df.copy()
    
    if sector:
        df = df[df['sector'].str.contains(sector, case=False, na=False)]
    if ministry:
        df = df[df['ministry'].str.contains(ministry, case=False, na=False)]
    if state:
        df = df[df['state'].str.contains(state, case=False, na=False)]
    if risk_category:
        df = df[df['risk_category'] == risk_category]
    
    # Sort
    if sort_by in df.columns:
        df[sort_by] = pd.to_numeric(df[sort_by], errors='coerce')
        ascending = sort_order == "asc"
        df = df.sort_values(sort_by, ascending=ascending, na_position='last')
    
    total = len(df)
    start = (page - 1) * page_size
    end = start + page_size
    
    # Select columns for response
    cols = [
        'project_name', 'agency', 'project_code', 'ministry', 'sector', 'state',
        'original_cost_cr', 'revised_cost_cr', 'cumulative_expenditure_cr',
        'physical_progress_pct', 'cost_overrun_ratio', 'cost_overrun_pct',
        'time_overrun_months', 'has_cost_overrun', 'has_time_overrun',
        'risk_score', 'risk_category', 'cost_overrun_probability', 'time_overrun_probability',
        'expenditure_ratio', 'financial_progress_pct', 'physical_financial_gap',
        'expenditure_lag_score', 'stagnation_score',
    ]
    available_cols = [c for c in cols if c in df.columns]
    
    return clean_for_json({
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "data": df_to_records(df[available_cols].iloc[start:end]),
    })


@app.get("/api/projects/{project_idx}")
def get_project_detail(project_idx: int):
    """Get detailed info for a single project."""
    if project_idx < 0 or project_idx >= len(projects_df):
        return JSONResponse(status_code=404, content={"error": "Project not found"})
    
    row = projects_df.iloc[project_idx]
    project = row.replace({np.nan: None, np.inf: None}).to_dict()
    
    # Get alerts for this project
    project_alerts = []
    if len(alerts_df) > 0 and 'project_name' in alerts_df.columns:
        pa = alerts_df[alerts_df['project_name'] == row.get('project_name', '')]
        project_alerts = df_to_records(pa)
    
    return clean_for_json({
        "project": project,
        "alerts": project_alerts,
    })


# --- ALERTS ---
@app.get("/api/alerts")
def get_alerts(
    severity: str = None,
    alert_type: str = None,
    sector: str = None,
    page: int = 1,
    page_size: int = 50,
):
    """Get early warning alerts."""
    df = alerts_df.copy()
    
    if severity:
        df = df[df['severity'] == severity.upper()]
    if alert_type:
        df = df[df['type'] == alert_type.upper()]
    if sector:
        df = df[df['sector'].str.contains(sector, case=False, na=False)]
    
    df = df.sort_values('risk_score', ascending=False, na_position='last')
    
    total = len(df)
    start = (page - 1) * page_size
    
    return clean_for_json({
        "total": total,
        "page": page,
        "data": df_to_records(df.iloc[start:start + page_size]),
        "summary": {
            "by_severity": df['severity'].value_counts().to_dict() if len(df) > 0 else {},
            "by_type": df['type'].value_counts().to_dict() if len(df) > 0 else {},
        }
    })


# --- ANALYTICS ---
@app.get("/api/analytics/sectors")
def get_sector_analytics():
    """Get sector-wise benchmarks and analytics."""
    if len(benchmarks_df) == 0:
        return {"data": []}
    return clean_for_json({
        "data": df_to_records(benchmarks_df.reset_index() if 'sector' in benchmarks_df.index.names else benchmarks_df)
    })


@app.get("/api/analytics/risk-distribution")
def get_risk_distribution():
    """Risk distribution by sector."""
    if 'sector' not in projects_df.columns or 'risk_category' not in projects_df.columns:
        return {"data": []}
    
    cross = pd.crosstab(projects_df['sector'], projects_df['risk_category'])
    result = []
    for sector in cross.index:
        row = {'sector': sector}
        for cat in ['Low', 'Medium', 'High', 'Critical']:
            row[cat] = int(cross.loc[sector].get(cat, 0))
        row['total'] = int(cross.loc[sector].sum())
        result.append(row)
    
    return clean_for_json({"data": sorted(result, key=lambda x: x.get('Critical', 0) + x.get('High', 0), reverse=True)})


@app.get("/api/analytics/cost-drivers")
def get_cost_drivers():
    """Get cost escalation driver analysis."""
    if len(cost_drivers_df) == 0:
        return {"data": []}
    return clean_for_json({"data": df_to_records(cost_drivers_df)})


@app.get("/api/analytics/model-comparison")
def get_model_comparison():
    """Get statistical vs ML model comparison."""
    return clean_for_json(comparison_data)


@app.get("/api/analytics/ministry-overview")
def get_ministry_overview():
    """Ministry-wise project overview."""
    df = projects_df.copy()
    result = []
    
    for ministry in df['ministry'].dropna().unique():
        mdf = df[df['ministry'] == ministry]
        result.append({
            'ministry': ministry,
            'project_count': len(mdf),
            'avg_risk_score': round(float(pd.to_numeric(mdf['risk_score'], errors='coerce').mean()), 1),
            'total_cost_cr': round(float(pd.to_numeric(mdf['original_cost_cr'], errors='coerce').sum()), 2),
            'cost_overrun_pct': round(float(mdf['has_cost_overrun'].mean() * 100), 1),
            'time_overrun_pct': round(float(mdf['has_time_overrun'].mean() * 100), 1),
            'avg_progress': round(float(pd.to_numeric(mdf['physical_progress_pct'], errors='coerce').mean()), 1),
            'critical_projects': int(len(mdf[mdf['risk_category'] == 'Critical'])),
        })
    
    return clean_for_json({"data": sorted(result, key=lambda x: x['avg_risk_score'], reverse=True)})


@app.get("/api/analytics/overrun-trends")
def get_overrun_trends():
    """Cost and time overrun analysis by cost bucket."""
    df = projects_df.copy()
    
    if 'cost_bucket' not in df.columns:
        return {"data": []}
    
    result = []
    for bucket in df['cost_bucket'].dropna().unique():
        bdf = df[df['cost_bucket'] == bucket]
        result.append({
            'cost_bucket': str(bucket),
            'project_count': len(bdf),
            'avg_cost_overrun_pct': round(float(pd.to_numeric(bdf['cost_overrun_pct'], errors='coerce').mean()), 2),
            'avg_time_overrun_months': round(float(pd.to_numeric(bdf['time_overrun_months'], errors='coerce').mean()), 1),
            'avg_risk_score': round(float(pd.to_numeric(bdf['risk_score'], errors='coerce').mean()), 1),
        })
    
    return clean_for_json({"data": result})


# ============================================================
# LOAD ML MODELS FOR LIVE PREDICTION
# ============================================================
try:
    cost_model = joblib.load(os.path.join(MODEL_DIR, 'cost_overrun_model.joblib'))
    time_classifier = joblib.load(os.path.join(MODEL_DIR, 'time_overrun_classifier.joblib'))
    time_regressor = joblib.load(os.path.join(MODEL_DIR, 'time_overrun_regressor.joblib'))
    feature_names = joblib.load(os.path.join(MODEL_DIR, 'feature_names.joblib'))
    label_encoders = joblib.load(os.path.join(MODEL_DIR, 'label_encoders.joblib'))
    MODELS_LOADED = True
    print(f"  ML models loaded: {len(feature_names)} features")
except Exception as e:
    MODELS_LOADED = False
    print(f"  Warning: Could not load ML models: {e}")


# --- FILTERS ---
@app.get("/api/filters")
def get_filters():
    """Get available filter options."""
    return clean_for_json({
        "sectors": sorted(projects_df['sector'].dropna().unique().tolist()),
        "ministries": sorted(projects_df['ministry'].dropna().unique().tolist()),
        "states": sorted(projects_df['state'].dropna().unique().tolist()),
        "risk_categories": ["Low", "Medium", "High", "Critical"],
    })


# --- PREDICT OPTIONS ---
@app.get("/api/predict/options")
def get_predict_options():
    """Get dropdown options for the predictor form."""
    if not MODELS_LOADED:
        return {"error": "Models not loaded"}
    return clean_for_json({
        "ministries": sorted(label_encoders['ministry'].classes_.tolist()),
        "sectors": sorted(label_encoders['sector'].classes_.tolist()),
        "states": sorted(label_encoders['state'].classes_.tolist()),
    })


# --- LIVE PREDICTION ---
from pydantic import BaseModel
from typing import Optional

class PredictRequest(BaseModel):
    ministry: str
    sector: str
    state: str
    original_cost_cr: float
    revised_cost_cr: float
    cumulative_expenditure_cr: float
    physical_progress_pct: float
    planned_duration_months: float = 60
    project_age_months: float = 36

@app.post("/api/predict")
def predict_risk(req: PredictRequest):
    """Run live inference on user-supplied project parameters."""
    if not MODELS_LOADED:
        return JSONResponse(status_code=503, content={"error": "ML models not loaded"})
    
    try:
        # Encode categorical variables safely
        def safe_encode(encoder, value):
            classes = list(encoder.classes_)
            if value in classes:
                return encoder.transform([value])[0]
            return 0  # default fallback

        ministry_enc = safe_encode(label_encoders['ministry'], req.ministry)
        sector_enc = safe_encode(label_encoders['sector'], req.sector)
        state_enc = safe_encode(label_encoders['state'], req.state)

        # Compute derived features
        expenditure_ratio = req.cumulative_expenditure_cr / req.revised_cost_cr if req.revised_cost_cr > 0 else 0
        financial_progress = (req.cumulative_expenditure_cr / req.revised_cost_cr * 100) if req.revised_cost_cr > 0 else 0
        physical_financial_gap = abs(req.physical_progress_pct - financial_progress)
        time_elapsed_ratio = req.project_age_months / req.planned_duration_months if req.planned_duration_months > 0 else 0
        expenditure_velocity = req.cumulative_expenditure_cr / req.project_age_months if req.project_age_months > 0 else 0
        expenditure_monthly_avg = expenditure_velocity
        progress_velocity = req.physical_progress_pct / req.project_age_months if req.project_age_months > 0 else 0
        progress_monthly_avg = progress_velocity
        cost_overrun_pct = ((req.revised_cost_cr - req.original_cost_cr) / req.original_cost_cr * 100) if req.original_cost_cr > 0 else 0

        # Build feature vector in exact model order
        feature_dict = {
            'original_cost_cr': req.original_cost_cr,
            'revised_cost_cr': req.revised_cost_cr,
            'cumulative_expenditure_cr': req.cumulative_expenditure_cr,
            'physical_progress_pct': req.physical_progress_pct,
            'expenditure_ratio': expenditure_ratio,
            'financial_progress_pct': financial_progress,
            'physical_financial_gap': physical_financial_gap,
            'planned_duration_months': req.planned_duration_months,
            'project_age_months': req.project_age_months,
            'time_elapsed_ratio': time_elapsed_ratio,
            'expenditure_velocity': expenditure_velocity,
            'expenditure_monthly_avg': expenditure_monthly_avg,
            'expenditure_acceleration': 0,  # single snapshot, no acceleration
            'progress_velocity': progress_velocity,
            'progress_monthly_avg': progress_monthly_avg,
            'progress_stagnant': 1 if progress_velocity < 0.3 else 0,
            'cost_revision_trend': 0,
            'cost_revised_up': 1 if req.revised_cost_cr > req.original_cost_cr else 0,
            'cost_overrun_trend': 0,
            'months_tracked': 1,
            'expenditure_ratio_trend': 0,
            'ministry_encoded': ministry_enc,
            'sector_encoded': sector_enc,
            'state_encoded': state_enc,
        }

        X = np.array([[feature_dict.get(f, 0) for f in feature_names]])

        # Predictions (XGBoost does not require feature scaling, model was trained on unscaled X)
        cost_overrun_prob = float(cost_model.predict_proba(X)[0][1])
        cost_overrun_pred = int(cost_model.predict(X)[0])

        time_overrun_prob = float(time_classifier.predict_proba(X)[0][1])
        time_overrun_pred = int(time_classifier.predict(X)[0])
        time_delay_months = float(max(0, time_regressor.predict(X)[0]))

        # --- HEURISTIC OVERRIDES FOR EXTREME ANOMALIES ---
        if req.cumulative_expenditure_cr > req.revised_cost_cr and req.revised_cost_cr > 0:
            cost_overrun_prob = max(cost_overrun_prob, 0.99)
        
        if req.project_age_months > req.planned_duration_months and req.physical_progress_pct < 100:
            time_overrun_prob = max(time_overrun_prob, 0.99)
            if time_delay_months < 1:
                if progress_velocity > 0:
                    time_delay_months = float(max(1.0, (100 - req.physical_progress_pct) / progress_velocity))
                else:
                    time_delay_months = 12.0

        if physical_financial_gap > 50:
            cost_overrun_prob = max(cost_overrun_prob, 0.80)
            time_overrun_prob = max(time_overrun_prob, 0.80)

        # Composite risk score (0-100)
        risk_score = round(
            cost_overrun_prob * 40 +
            time_overrun_prob * 30 +
            min(physical_financial_gap / 50, 1) * 15 +
            min(cost_overrun_pct / 100, 1) * 15,
            1
        )
        
        if physical_financial_gap > 50:
            risk_score = max(risk_score, 85.0)  # Force High/Critical if massive gap
            
        risk_score = min(100.0, max(0.0, risk_score))

        if risk_score >= 80: risk_category = 'Critical'
        elif risk_score >= 60: risk_category = 'High'
        elif risk_score >= 30: risk_category = 'Medium'
        else: risk_category = 'Low'

        # Generate warnings
        warnings = []
        if cost_overrun_prob > 0.7:
            warnings.append({"type": "COST_ESCALATION", "severity": "CRITICAL", "message": f"High probability of cost overrun ({cost_overrun_prob*100:.1f}%)"})
        elif cost_overrun_prob > 0.4:
            warnings.append({"type": "COST_ESCALATION", "severity": "WARNING", "message": f"Moderate cost overrun risk ({cost_overrun_prob*100:.1f}%)"})

        if time_overrun_prob > 0.7:
            warnings.append({"type": "TIME_OVERRUN", "severity": "CRITICAL", "message": f"High probability of schedule delay ({time_overrun_prob*100:.1f}%). Predicted delay: {time_delay_months:.1f} months"})
        elif time_overrun_prob > 0.4:
            warnings.append({"type": "TIME_OVERRUN", "severity": "WARNING", "message": f"Moderate schedule delay risk ({time_overrun_prob*100:.1f}%)"})

        if physical_financial_gap > 30:
            warnings.append({"type": "PF_GAP", "severity": "CRITICAL", "message": f"Large physical-financial gap of {physical_financial_gap:.1f}%"})
        elif physical_financial_gap > 15:
            warnings.append({"type": "PF_GAP", "severity": "WARNING", "message": f"Physical-financial gap of {physical_financial_gap:.1f}%"})

        if expenditure_ratio > 0.9 and req.physical_progress_pct < 70:
            warnings.append({"type": "EXPENDITURE_LAG", "severity": "WARNING", "message": f"High expenditure ({expenditure_ratio*100:.0f}%) but low progress ({req.physical_progress_pct:.0f}%)"})

        if cost_overrun_pct > 50:
            warnings.append({"type": "COST_REVISION", "severity": "CRITICAL", "message": f"Cost has been revised up by {cost_overrun_pct:.1f}% from original"})

        # Recommendations
        recommendations = []
        if cost_overrun_prob > 0.6:
            recommendations.append("Conduct immediate cost audit and review budget allocation")
        if time_overrun_prob > 0.6:
            recommendations.append("Review implementation timeline and identify bottleneck milestones")
        if physical_financial_gap > 20:
            recommendations.append("Investigate physical-financial gap; verify ground-level progress")
        if progress_velocity < 0.5 and req.project_age_months > 24:
            recommendations.append("Progress velocity is critically low; escalate to monitoring committee")
        if expenditure_ratio < 0.3 and time_elapsed_ratio > 0.5:
            recommendations.append("Expenditure significantly behind schedule; review fund release mechanism")
        if not recommendations:
            recommendations.append("Project parameters within acceptable limits. Continue routine monitoring.")

        # Feature importance for this prediction
        top_drivers = [
            {"feature": "Financial Progress %", "value": round(financial_progress, 1)},
            {"feature": "Expenditure Ratio", "value": round(expenditure_ratio * 100, 1)},
            {"feature": "Physical-Financial Gap", "value": round(physical_financial_gap, 1)},
            {"feature": "Cost Overrun %", "value": round(cost_overrun_pct, 1)},
            {"feature": "Time Elapsed Ratio", "value": round(time_elapsed_ratio * 100, 1)},
        ]

        return clean_for_json({
            "cost_overrun_probability": round(cost_overrun_prob * 100, 1),
            "cost_overrun_prediction": bool(cost_overrun_pred),
            "time_overrun_probability": round(time_overrun_prob * 100, 1),
            "time_overrun_prediction": bool(time_overrun_pred),
            "predicted_delay_months": round(time_delay_months, 1),
            "risk_score": risk_score,
            "risk_category": risk_category,
            "warnings": warnings,
            "recommendations": recommendations,
            "top_drivers": top_drivers,
            "computed_features": {
                "expenditure_ratio": round(expenditure_ratio, 3),
                "financial_progress_pct": round(financial_progress, 1),
                "physical_financial_gap": round(physical_financial_gap, 1),
                "time_elapsed_ratio": round(time_elapsed_ratio, 3),
                "cost_overrun_pct": round(cost_overrun_pct, 1),
                "progress_velocity": round(progress_velocity, 2),
            }
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ============================================================
# LLM CHAT ENDPOINTS
# ============================================================
from chat import chat as llm_chat, CHAT_SUGGESTIONS

class ChatRequest(BaseModel):
    message: str
    history: list = []

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """LLM-powered project intelligence assistant."""
    if not req.message.strip():
        return JSONResponse(status_code=400, content={"error": "Message cannot be empty"})

    result = await llm_chat(req.message, req.history)

    if result["error"]:
        return JSONResponse(status_code=503, content={"error": result["error"]})

    return {"response": result["response"]}


@app.get("/api/chat/suggestions")
def get_chat_suggestions():
    """Get starter question suggestions for the chat UI."""
    return {"suggestions": CHAT_SUGGESTIONS}


# ============================================================
# STATIC FILE SERVING & SPA FALLBACK (for unified/Docker deployment)
# ============================================================
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')
if os.path.isdir(FRONTEND_DIST):
    from fastapi.responses import FileResponse

    assets_dir = os.path.join(FRONTEND_DIST, 'assets')
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve frontend static files or fallback to index.html for SPA client routes."""
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    print(f"  Serving frontend SPA from {FRONTEND_DIST}")
else:
    @app.get("/")
    def root():
        return {"message": "PAIMANA AI API", "status": "running", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting PAIMANA AI API on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
