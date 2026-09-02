"""
PAIMANA AI - LLM Chatbot Module
Groq-powered Project Intelligence Assistant using RAG-lite pattern.
Queries project data via Pandas, injects context into LLM prompt.
"""

import os
import re
import json
import requests
import asyncio
import pandas as pd
import numpy as np
from groq import Groq
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# ============================================================
# GROQ CLIENT
# ============================================================
MODEL_NAME = "qwen/qwen3.8-27b"

def get_groq_client():
    """Get Groq client. Returns None if API key is not set."""
    # Re-load .env every time to catch late-created files
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key == "your_groq_api_key_here":
        return None
    return Groq(api_key=api_key)


# ============================================================
# DATA LOADING
# ============================================================
RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'ml', 'results')

def load_projects():
    """Load the projects dataset."""
    filepath = os.path.join(RESULTS_DIR, 'projects_with_risk_scores.csv')
    if os.path.exists(filepath):
        return pd.read_csv(filepath, encoding='utf-8-sig')
    return pd.DataFrame()

def load_alerts():
    """Load the alerts dataset."""
    filepath = os.path.join(RESULTS_DIR, 'alerts.csv')
    if os.path.exists(filepath):
        return pd.read_csv(filepath, encoding='utf-8-sig')
    return pd.DataFrame()

def load_sector_benchmarks():
    """Load sector benchmarks."""
    filepath = os.path.join(RESULTS_DIR, 'sector_benchmarks.csv')
    if os.path.exists(filepath):
        return pd.read_csv(filepath, encoding='utf-8-sig')
    return pd.DataFrame()

# Load at module import
_projects_df = load_projects()
_alerts_df = load_alerts()
_benchmarks_df = load_sector_benchmarks()


# ============================================================
# INTELLIGENT DATA QUERY ENGINE
# ============================================================
def query_projects(question: str) -> dict:
    """
    Analyze the user's question and extract relevant project data.
    Returns a dict with context_type, data summary, and raw records.
    """
    df = _projects_df.copy()
    q = question.lower()
    context = {"type": "general", "summary": "", "records": [], "stats": {}}

    if df.empty:
        context["summary"] = "No project data available."
        return context

    # --- FILTER by keywords ---
    filtered = df.copy()
    filter_applied = False

    # Ministry filter
    for ministry in df['ministry'].dropna().unique():
        if ministry.lower() in q or any(word in q for word in ministry.lower().split() if len(word) > 3):
            filtered = filtered[filtered['ministry'] == ministry]
            filter_applied = True
            context["type"] = "ministry_specific"
            break

    # Sector filter
    for sector in df['sector'].dropna().unique():
        sector_words = [w for w in sector.lower().split() if len(w) > 3]
        if sector.lower() in q or any(word in q for word in sector_words):
            filtered = filtered[filtered['sector'] == sector]
            filter_applied = True
            context["type"] = "sector_specific"
            break

    # State filter
    for state in df['state'].dropna().unique():
        if isinstance(state, str) and len(state) > 2:
            state_words = [w for w in state.lower().split() if len(w) > 3]
            if state.lower() in q or any(word in q for word in state_words):
                filtered = filtered[filtered['state'] == state]
                filter_applied = True
                context["type"] = "state_specific"
                break

    # Risk category filter
    if 'critical' in q and ('risk' in q or 'project' in q):
        filtered = filtered[filtered['risk_category'] == 'Critical']
        filter_applied = True
        context["type"] = "risk_filter"
    elif 'high risk' in q or 'high-risk' in q:
        filtered = filtered[filtered['risk_category'].isin(['High', 'Critical'])]
        filter_applied = True
        context["type"] = "risk_filter"
    elif 'low risk' in q:
        filtered = filtered[filtered['risk_category'] == 'Low']
        filter_applied = True
        context["type"] = "risk_filter"

    # Cost overrun filter
    if 'cost overrun' in q or 'cost escalation' in q or 'over budget' in q:
        if not filter_applied:
            filtered = filtered[filtered['has_cost_overrun'] == 1]
        context["type"] = "cost_overrun"

    # Time overrun filter
    if 'time overrun' in q or 'delay' in q or 'behind schedule' in q or 'late' in q:
        if not filter_applied:
            filtered = filtered[filtered['has_time_overrun'] == 1]
        context["type"] = "time_overrun"

    # Stagnation filter
    if 'stagnant' in q or 'stagnation' in q or 'stuck' in q or 'no progress' in q:
        filtered = filtered[filtered['progress_stagnant'] == 1]
        filter_applied = True
        context["type"] = "stagnation"

    # --- Determine what kind of answer is needed ---

    # Top/bottom queries
    n_results = 10  # default
    num_match = re.search(r'top\s*(\d+)|(\d+)\s*project', q)
    if num_match:
        n_results = int(num_match.group(1) or num_match.group(2))
        n_results = min(n_results, 25)  # Cap at 25

    # Sort logic
    if 'expensive' in q or 'costliest' in q or 'largest cost' in q or 'biggest' in q:
        filtered = filtered.sort_values('revised_cost_cr', ascending=False)
    elif 'cheapest' in q or 'lowest cost' in q or 'smallest' in q:
        filtered = filtered.sort_values('revised_cost_cr', ascending=True)
    elif 'most delayed' in q or 'highest delay' in q or 'longest delay' in q:
        filtered = filtered.sort_values('time_overrun_months', ascending=False)
    elif 'highest risk' in q or 'riskiest' in q or 'most risky' in q:
        filtered = filtered.sort_values('risk_score', ascending=False)
    elif 'best' in q or 'best performing' in q or 'lowest risk' in q:
        filtered = filtered.sort_values('risk_score', ascending=True)
    elif 'most progress' in q or 'highest progress' in q:
        filtered = filtered.sort_values('physical_progress_pct', ascending=False)
    elif 'least progress' in q or 'lowest progress' in q:
        filtered = filtered.sort_values('physical_progress_pct', ascending=True)
    else:
        filtered = filtered.sort_values('risk_score', ascending=False)

    # --- Build statistics ---
    stats = {}
    if len(filtered) > 0:
        numeric_cols = ['original_cost_cr', 'revised_cost_cr', 'cumulative_expenditure_cr',
                        'physical_progress_pct', 'risk_score', 'cost_overrun_pct',
                        'time_overrun_months', 'expenditure_ratio']
        for col in numeric_cols:
            if col in filtered.columns:
                vals = pd.to_numeric(filtered[col], errors='coerce')
                stats[col] = {
                    "mean": round(float(vals.mean()), 2) if not vals.isna().all() else None,
                    "min": round(float(vals.min()), 2) if not vals.isna().all() else None,
                    "max": round(float(vals.max()), 2) if not vals.isna().all() else None,
                }

        if 'risk_category' in filtered.columns:
            stats['risk_distribution'] = filtered['risk_category'].value_counts().to_dict()
        if 'has_cost_overrun' in filtered.columns:
            stats['cost_overrun_rate'] = round(float(filtered['has_cost_overrun'].mean() * 100), 1)
        if 'has_time_overrun' in filtered.columns:
            stats['time_overrun_rate'] = round(float(filtered['has_time_overrun'].mean() * 100), 1)

    context["stats"] = stats
    context["total_matched"] = len(filtered)

    # --- Format top records for LLM context ---
    display_cols = ['project_name', 'ministry', 'sector', 'state',
                    'original_cost_cr', 'revised_cost_cr', 'cumulative_expenditure_cr',
                    'physical_progress_pct', 'risk_score', 'risk_category',
                    'cost_overrun_pct', 'time_overrun_months', 'has_cost_overrun', 'has_time_overrun']
    available_cols = [c for c in display_cols if c in filtered.columns]
    top_records = filtered[available_cols].head(n_results).replace({np.nan: None, np.inf: None, -np.inf: None})
    context["records"] = top_records.to_dict('records')

    # Build human-readable summary
    context["summary"] = f"Found {len(filtered)} matching projects out of {len(df)} total. Showing top {min(n_results, len(filtered))} results."

    return context


def get_portfolio_summary() -> str:
    """Get a brief portfolio summary for the system prompt."""
    df = _projects_df
    if df.empty:
        return "No data available."

    total = len(df)
    total_cost = pd.to_numeric(df['revised_cost_cr'], errors='coerce').sum()
    total_exp = pd.to_numeric(df['cumulative_expenditure_cr'], errors='coerce').sum()
    avg_progress = pd.to_numeric(df['physical_progress_pct'], errors='coerce').mean()
    avg_risk = pd.to_numeric(df['risk_score'], errors='coerce').mean()
    risk_dist = df['risk_category'].value_counts().to_dict() if 'risk_category' in df.columns else {}
    ministries = int(df['ministry'].nunique())
    sectors = int(df['sector'].nunique())
    cost_overrun_rate = float(df['has_cost_overrun'].mean() * 100) if 'has_cost_overrun' in df.columns else 0
    time_overrun_rate = float(df['has_time_overrun'].mean() * 100) if 'has_time_overrun' in df.columns else 0

    return (
        f"Portfolio: {total} projects across {ministries} Ministries and {sectors} sectors.\n"
        f"Total revised cost: ₹{total_cost/100:.2f} lakh crore. Total expenditure: ₹{total_exp/100:.2f} lakh crore.\n"
        f"Average physical progress: {avg_progress:.1f}%. Average risk score: {avg_risk:.1f}/100.\n"
        f"Risk distribution: {risk_dist}.\n"
        f"Cost overrun rate: {cost_overrun_rate:.1f}%. Time overrun rate: {time_overrun_rate:.1f}%.\n"
        f"Available sectors: {', '.join(sorted(df['sector'].dropna().unique().tolist()))}.\n"
        f"Available ministries: {', '.join(sorted(df['ministry'].dropna().unique().tolist()))}."
    )


# ============================================================
# LLM PROMPT ENGINEERING
# ============================================================
SYSTEM_PROMPT = """You are PAIMANA AI Assistant — an intelligent project monitoring assistant for India's infrastructure projects tracked by MoSPI (Ministry of Statistics and Programme Implementation).

You have access to real-time data from the PAIMANA portal covering Central Sector Infrastructure Projects costing ₹150 crore and above.

YOUR CAPABILITIES:
- Answer questions about specific projects, ministries, sectors, states
- Analyze cost overruns, time overruns, and project risks
- Compare performance across sectors and ministries
- Explain risk scores and alert patterns
- Provide insights on project implementation status
- Identify stagnating or troubled projects
- Run live predictive AI simulations using the predict_risk tool when a user provides project parameters (e.g. "What if I have a 1200 Cr project..."). If they don't provide all parameters, use reasonable defaults or ask them.

PORTFOLIO OVERVIEW:
{portfolio_summary}

IMPORTANT RULES:
1. Always use the DATA CONTEXT provided below to answer questions. Do not make up project names or numbers.
2. When citing numbers, use ₹ (Rupees) and 'crore' as the unit.
3. Risk scores are 0-100 (Low: 0-30, Medium: 30-60, High: 60-80, Critical: 80-100).
4. Be concise but thorough. Use bullet points and tables where appropriate.
5. If the data context doesn't contain enough information to answer, say so clearly.
6. When discussing cost overrun, note that cost_overrun_pct = ((revised - original) / original) × 100.
7. Format numbers nicely (e.g., ₹5,234 crore instead of 5234.0).
8. You are a government decision-support tool. Be professional, factual, and action-oriented.
9. If asked about something unrelated to infrastructure projects, politely redirect to your domain."""


def build_messages(user_message: str, history: list = None) -> list:
    """
    Build the full message list for the Groq API call.
    Includes system prompt, data context, conversation history, and user message.
    """
    # Query the data
    data_context = query_projects(user_message)

    # Format records as a readable table
    records_text = ""
    if data_context["records"]:
        records_text = "\n### Matching Projects:\n"
        for i, rec in enumerate(data_context["records"], 1):
            name = rec.get('project_name', 'N/A')
            ministry = rec.get('ministry', 'N/A')
            sector = rec.get('sector', 'N/A')
            state = rec.get('state', 'N/A')
            orig = rec.get('original_cost_cr')
            rev = rec.get('revised_cost_cr')
            exp = rec.get('cumulative_expenditure_cr')
            prog = rec.get('physical_progress_pct')
            risk = rec.get('risk_score')
            risk_cat = rec.get('risk_category', 'N/A')
            cost_op = rec.get('cost_overrun_pct')
            time_om = rec.get('time_overrun_months')

            records_text += (
                f"\n{i}. **{name}**\n"
                f"   - Ministry: {ministry} | Sector: {sector} | State: {state}\n"
                f"   - Original Cost: ₹{orig:,.2f} Cr | Revised Cost: ₹{rev:,.2f} Cr\n" if orig and rev else ""
            )
            if exp is not None:
                records_text += f"   - Expenditure: ₹{exp:,.2f} Cr\n"
            if prog is not None:
                records_text += f"   - Physical Progress: {prog:.1f}%\n"
            if risk is not None:
                records_text += f"   - Risk Score: {risk:.1f}/100 ({risk_cat})\n"
            if cost_op is not None and cost_op != 0:
                records_text += f"   - Cost Overrun: {cost_op:.1f}%\n"
            if time_om is not None and time_om != 0:
                records_text += f"   - Time Overrun: {time_om:.1f} months\n"

    # Format statistics
    stats_text = ""
    if data_context.get("stats"):
        stats = data_context["stats"]
        stats_text = "\n### Summary Statistics:\n"
        if 'risk_distribution' in stats:
            stats_text += f"- Risk Distribution: {stats['risk_distribution']}\n"
        if 'cost_overrun_rate' in stats:
            stats_text += f"- Cost Overrun Rate: {stats['cost_overrun_rate']}%\n"
        if 'time_overrun_rate' in stats:
            stats_text += f"- Time Overrun Rate: {stats['time_overrun_rate']}%\n"
        if 'risk_score' in stats:
            rs = stats['risk_score']
            stats_text += f"- Risk Score — Mean: {rs['mean']}, Min: {rs['min']}, Max: {rs['max']}\n"
        if 'physical_progress_pct' in stats:
            pp = stats['physical_progress_pct']
            stats_text += f"- Physical Progress — Mean: {pp['mean']}%, Min: {pp['min']}%, Max: {pp['max']}%\n"

    data_block = (
        f"\n---\n## DATA CONTEXT\n"
        f"{data_context['summary']}\n"
        f"{stats_text}"
        f"{records_text}"
        f"\n---\n"
    )

    # Build messages array
    system = SYSTEM_PROMPT.format(portfolio_summary=get_portfolio_summary())
    messages = [{"role": "system", "content": system}]

    # Add conversation history (last 10 messages)
    if history:
        for msg in history[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

    # Add current user message with data context
    messages.append({
        "role": "user",
        "content": f"{user_message}\n{data_block}"
    })

    return messages


# ============================================================
# CHAT FUNCTION WITH TOOL CALLING
# ============================================================
PREDICT_TOOL = {
    "type": "function",
    "function": {
        "name": "predict_risk",
        "description": "Predict the risk of cost/time overrun for a hypothetical or real project using the AI models.",
        "parameters": {
            "type": "object",
            "properties": {
                "ministry": {"type": "string", "description": "Name of the ministry (e.g., 'Ministry of Road Transport and Highways')"},
                "sector": {"type": "string", "description": "Name of the sector (e.g., 'Roads and Highways', 'Railways', 'Power')"},
                "state": {"type": "string", "description": "Name of the state (e.g., 'Maharashtra', 'Multi State')"},
                "original_cost_cr": {"type": "number", "description": "Original cost in Crores"},
                "revised_cost_cr": {"type": "number", "description": "Revised cost in Crores"},
                "cumulative_expenditure_cr": {"type": "number", "description": "Total expenditure so far in Crores"},
                "physical_progress_pct": {"type": "number", "description": "Physical progress percentage (0-100)"},
                "planned_duration_months": {"type": "number", "description": "Original planned duration in months"},
                "project_age_months": {"type": "number", "description": "Current age of the project in months"}
            },
            "required": ["original_cost_cr", "revised_cost_cr", "cumulative_expenditure_cr", "physical_progress_pct", "planned_duration_months", "project_age_months"]
        }
    }
}

async def chat(user_message: str, history: list = None) -> dict:
    """
    Process a chat message and return the LLM response, handling tool calls.
    """
    client = get_groq_client()
    if client is None:
        return {
            "response": None,
            "error": "GROQ_API_KEY is not configured."
        }

    try:
        messages = build_messages(user_message, history)

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=[PREDICT_TOOL],
            tool_choice="auto",
            temperature=0.3,
            max_tokens=2048,
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            # LLM wants to use a tool
            messages.append(response_message)
            
            for tool_call in tool_calls:
                if tool_call.function.name == "predict_risk":
                    args = json.loads(tool_call.function.arguments)
                    
                    # Provide defaults for strings if missing
                    payload = {
                        "ministry": args.get("ministry", "Ministry of Road Transport and Highways"),
                        "sector": args.get("sector", "Roads and Highways"),
                        "state": args.get("state", "Multi State"),
                        "original_cost_cr": args.get("original_cost_cr", 1000),
                        "revised_cost_cr": args.get("revised_cost_cr", 1000),
                        "cumulative_expenditure_cr": args.get("cumulative_expenditure_cr", 0),
                        "physical_progress_pct": args.get("physical_progress_pct", 0),
                        "planned_duration_months": args.get("planned_duration_months", 60),
                        "project_age_months": args.get("project_age_months", 36),
                    }
                    
                    try:
                        # Use asyncio.to_thread to prevent blocking the FastAPI event loop (which causes a deadlock)
                        # Use env var for internal API URL to support hosted deployments
                        internal_url = os.getenv("INTERNAL_API_URL", "http://127.0.0.1:8000")
                        api_res = await asyncio.to_thread(
                            requests.post, 
                            f"{internal_url}/api/predict", 
                            json=payload, 
                            timeout=15
                        )
                        api_res.raise_for_status()
                        result_data = api_res.json()
                        tool_result = json.dumps(result_data)
                    except Exception as e:
                        tool_result = json.dumps({"error": f"Prediction failed: {str(e)}"})

                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "predict_risk",
                        "content": tool_result,
                    })
            
            # Second call to LLM with tool results
            second_response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
            return {"response": second_response.choices[0].message.content, "error": None}

        else:
            # Normal response
            return {"response": response_message.content, "error": None}

    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            return {
                "response": None,
                "error": "Rate limit reached. Please wait a moment."
            }
        return {"response": None, "error": f"LLM error: {error_msg}"}


# ============================================================
# SUGGESTION PROMPTS
# ============================================================
CHAT_SUGGESTIONS = [
    {
        "category": "🤖 AI Prediction (Live ML)",
        "questions": [
            "Predict risk: original cost ₹1200 Cr, revised ₹1500 Cr, spent ₹2100 Cr, 35% progress, planned 48 months, age 60 months",
            "What risk does the AI predict for a Railways project spending ₹900 Cr of ₹1000 Cr budget with only 20% progress?",
            "Simulate: Power sector project, ₹500 Cr budget, ₹480 Cr spent, 90% done, 36 months planned, 34 months elapsed",
        ]
    },
    {
        "category": "Risk Analysis",
        "questions": [
            "Which projects have critical risk scores?",
            "Show me the top 10 riskiest projects across all sectors",
            "What is the risk distribution across ministries?",
        ]
    },
    {
        "category": "Cost Analysis",
        "questions": [
            "Which projects have the highest cost overruns?",
            "Compare cost overrun rates across sectors",
            "Show me the most expensive Railway projects",
        ]
    },
    {
        "category": "Sector & Ministry",
        "questions": [
            "Compare Railways vs Highways sector performance",
            "Which ministry has the most troubled projects?",
            "Show me all projects in Maharashtra",
        ]
    },
]
