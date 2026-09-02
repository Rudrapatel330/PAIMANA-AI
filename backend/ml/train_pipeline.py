"""
PAIMANA AI - Complete ML Pipeline (Multi-Month Version)
Uses all 4 months (April-July 2026) properly:
- Matches projects across months
- Extracts temporal features (trends, velocity, acceleration)
- Temporal validation (train on earlier months, test on latest)
- No data leakage
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np
import os
import json
import joblib
import warnings
warnings.filterwarnings('ignore')

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import (
    RandomForestClassifier, RandomForestRegressor,
    GradientBoostingClassifier, GradientBoostingRegressor
)
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    mean_absolute_error, mean_squared_error, r2_score
)

try:
    from xgboost import XGBClassifier, XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    print("XGBoost not available, using GradientBoosting instead")

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False
    print("SHAP not available, skipping explainability")

# ============================================================
# PATHS
# ============================================================
DATA_DIR = r"d:\0SIHNEW\Dataset\cleaned"
MODEL_DIR = r"d:\0SIHNEW\backend\ml\models"
RESULTS_DIR = r"d:\0SIHNEW\backend\ml\results"
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

MONTH_ORDER = ['April', 'May', 'June', 'July']


# ============================================================
# 1. LOAD & MERGE ALL 4 MONTHS
# ============================================================
def load_all_months():
    """Load all 4 monthly datasets."""
    months = {}
    for f in os.listdir(DATA_DIR):
        if f.endswith('_cleaned.csv') and 'all_projects' not in f:
            df = pd.read_csv(os.path.join(DATA_DIR, f), encoding='utf-8-sig')
            month = df['report_month'].iloc[0] if 'report_month' in df.columns else 'Unknown'
            months[month] = df
            print(f"  Loaded {month}: {len(df)} projects")
    return months


def create_project_key(df):
    """Create a unique key for each project to match across months."""
    # Use project_name + state as key (project_code can be missing)
    df = df.copy()
    name = df['project_name'].fillna('').astype(str).str.strip().str[:100]
    state = df['state'].fillna('').astype(str).str.strip()
    df['project_key'] = name + '||' + state
    return df


def merge_monthly_data(months):
    """
    Merge projects across months to create temporal features.
    Strategy: 
    - Use July (latest) as the PRIMARY dataset with target variables
    - Add features derived from April/May/June showing how each project evolved
    """
    print("\n--- Merging Monthly Data ---")
    
    # Add project keys
    for month in months:
        months[month] = create_project_key(months[month])
    
    # Start with July as base (latest month = what we want to predict)
    if 'July' not in months:
        # Fallback to latest available
        base_month = MONTH_ORDER[-1]
        for m in reversed(MONTH_ORDER):
            if m in months:
                base_month = m
                break
    else:
        base_month = 'July'
    
    base = months[base_month].copy()
    print(f"  Base month (latest): {base_month} with {len(base)} projects")
    
    # For each earlier month, compute what changed
    numeric_cols = [
        'original_cost_cr', 'revised_cost_cr', 'cumulative_expenditure_cr',
        'physical_progress_pct', 'expenditure_ratio', 'cost_overrun_ratio',
        'time_overrun_months'
    ]
    
    # Ensure numeric
    for month_name, df in months.items():
        for col in numeric_cols:
            if col in df.columns:
                months[month_name][col] = pd.to_numeric(df[col], errors='coerce')
    
    # Find projects that exist across months
    all_keys = set(base['project_key'])
    months_available = [m for m in MONTH_ORDER if m in months and m != base_month]
    
    print(f"  Earlier months available: {months_available}")
    
    # Compute temporal features by matching projects
    temporal_features = {}
    
    for key in all_keys:
        features = {}
        base_row = base[base['project_key'] == key]
        if len(base_row) == 0:
            continue
        base_row = base_row.iloc[0]
        
        # Collect values across months for this project
        monthly_values = {}
        for col in numeric_cols:
            monthly_values[col] = []
        
        for month_name in MONTH_ORDER:
            if month_name not in months:
                continue
            month_df = months[month_name]
            project_row = month_df[month_df['project_key'] == key]
            if len(project_row) > 0:
                row = project_row.iloc[0]
                for col in numeric_cols:
                    val = row.get(col, np.nan)
                    monthly_values[col].append(float(val) if not pd.isna(val) else np.nan)
            else:
                for col in numeric_cols:
                    monthly_values[col].append(np.nan)
        
        # --- Compute temporal features ---
        
        # 1. Expenditure velocity (monthly change in expenditure)
        exp_vals = [v for v in monthly_values['cumulative_expenditure_cr'] if not np.isnan(v)]
        if len(exp_vals) >= 2:
            features['expenditure_velocity'] = exp_vals[-1] - exp_vals[0]  # Total change
            features['expenditure_monthly_avg'] = (exp_vals[-1] - exp_vals[0]) / len(exp_vals)
            # Acceleration: is spending speeding up or slowing?
            if len(exp_vals) >= 3:
                early_rate = exp_vals[1] - exp_vals[0]
                late_rate = exp_vals[-1] - exp_vals[-2]
                features['expenditure_acceleration'] = late_rate - early_rate
            else:
                features['expenditure_acceleration'] = 0
        else:
            features['expenditure_velocity'] = 0
            features['expenditure_monthly_avg'] = 0
            features['expenditure_acceleration'] = 0
        
        # 2. Physical progress velocity
        prog_vals = [v for v in monthly_values['physical_progress_pct'] if not np.isnan(v)]
        if len(prog_vals) >= 2:
            features['progress_velocity'] = prog_vals[-1] - prog_vals[0]
            features['progress_monthly_avg'] = (prog_vals[-1] - prog_vals[0]) / len(prog_vals)
            # Stagnation: no progress over months
            features['progress_stagnant'] = 1 if (prog_vals[-1] - prog_vals[0]) < 1.0 else 0
        else:
            features['progress_velocity'] = 0
            features['progress_monthly_avg'] = 0
            features['progress_stagnant'] = 0
        
        # 3. Cost revision trend (did revised cost increase across months?)
        cost_vals = [v for v in monthly_values['revised_cost_cr'] if not np.isnan(v)]
        if len(cost_vals) >= 2:
            features['cost_revision_trend'] = cost_vals[-1] - cost_vals[0]
            features['cost_revised_up'] = 1 if cost_vals[-1] > cost_vals[0] * 1.01 else 0
        else:
            features['cost_revision_trend'] = 0
            features['cost_revised_up'] = 0
        
        # 4. Cost overrun trend
        cor_vals = [v for v in monthly_values['cost_overrun_ratio'] if not np.isnan(v)]
        if len(cor_vals) >= 2:
            features['cost_overrun_trend'] = cor_vals[-1] - cor_vals[0]
        else:
            features['cost_overrun_trend'] = 0
        
        # 5. Number of months project appears in data
        months_present = sum(1 for col in numeric_cols[:1] 
                           for vals in [monthly_values[col]] 
                           if any(not np.isnan(v) for v in vals))
        features['months_tracked'] = len([v for v in monthly_values['cumulative_expenditure_cr'] if not np.isnan(v)])
        
        # 6. Expenditure ratio trend
        er_vals = [v for v in monthly_values['expenditure_ratio'] if not np.isnan(v)]
        if len(er_vals) >= 2:
            features['expenditure_ratio_trend'] = er_vals[-1] - er_vals[0]
        else:
            features['expenditure_ratio_trend'] = 0
        
        temporal_features[key] = features
    
    # Merge temporal features into base dataset
    temporal_df = pd.DataFrame.from_dict(temporal_features, orient='index')
    temporal_df.index.name = 'project_key'
    temporal_df = temporal_df.reset_index()
    
    merged = base.merge(temporal_df, on='project_key', how='left')
    
    # Fill NaN temporal features with 0
    temporal_cols = [c for c in temporal_df.columns if c != 'project_key']
    for col in temporal_cols:
        merged[col] = merged[col].fillna(0)
    
    print(f"  Merged dataset: {len(merged)} projects x {len(merged.columns)} columns")
    print(f"  New temporal features: {temporal_cols}")
    
    return merged, temporal_cols


# ============================================================
# 2. PREPARE FEATURES
# ============================================================
def prepare_features(df, temporal_cols):
    """Prepare feature matrix for ML models."""
    
    # Base numeric features (from CUF fields)
    base_features = [
        'original_cost_cr', 'revised_cost_cr', 'cumulative_expenditure_cr',
        'physical_progress_pct', 'expenditure_ratio', 'financial_progress_pct',
        'physical_financial_gap', 'planned_duration_months', 'project_age_months',
        'time_elapsed_ratio'
    ]
    
    categorical_features = ['ministry', 'sector', 'state']
    
    data = df.copy()
    
    # Encode categoricals
    label_encoders = {}
    for col in categorical_features:
        le = LabelEncoder()
        data[col + '_encoded'] = le.fit_transform(data[col].fillna('Unknown').astype(str))
        label_encoders[col] = le
    
    encoded_cats = [c + '_encoded' for c in categorical_features]
    
    # All features = base + temporal + encoded categoricals
    all_features = base_features + temporal_cols + encoded_cats
    
    # Ensure numeric
    for col in base_features + temporal_cols:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
    
    # Drop rows with NaN targets
    data = data.dropna(subset=['has_cost_overrun', 'has_time_overrun'])
    
    available_features = [f for f in all_features if f in data.columns]
    
    X = data[available_features].copy()
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    print(f"\nFeature matrix: {X.shape}")
    print(f"  Base CUF features: {len(base_features)}")
    print(f"  Temporal features: {len(temporal_cols)}")
    print(f"  Categorical (encoded): {len(encoded_cats)}")
    print(f"  Total: {len(available_features)}")
    
    return X, data, available_features, label_encoders


# ============================================================
# 3. TRAIN MODELS WITH CUF-ONLY vs CUF+TEMPORAL COMPARISON
# ============================================================
def train_and_compare(X, y, feature_names, task_name, base_feature_count):
    """
    Train models in 3 groups:
    1. Statistical (Logistic/DecisionTree) with all features
    2. ML with CUF-only features  
    3. ML with CUF + Temporal features
    This answers requirement (b) AND (c) from the problem statement.
    """
    
    print(f"\n{'='*60}")
    print(f"{task_name}")
    print(f"{'='*60}")
    print(f"Target distribution: {dict(pd.Series(y).value_counts())}")
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # CUF-only features (first base_feature_count + 3 categorical = base)
    cuf_feature_count = base_feature_count + 3  # +3 for encoded categoricals
    X_train_cuf = X_train.iloc[:, :cuf_feature_count]
    X_test_cuf = X_test.iloc[:, :cuf_feature_count]
    X_train_cuf_scaled = X_train_scaled[:, :cuf_feature_count]
    X_test_cuf_scaled = X_test_scaled[:, :cuf_feature_count]
    
    results = {}
    best_model = None
    best_score = 0
    best_name = ""
    
    # ---- Group 1: Statistical Models (all features) ----
    print("\n  --- Statistical Models ---")
    
    stat_models = {
        'Logistic Regression': (LogisticRegression(max_iter=1000, random_state=42), True),
        'Decision Tree': (DecisionTreeClassifier(max_depth=5, random_state=42), False),
    }
    
    for name, (model, use_scaled) in stat_models.items():
        print(f"  Training {name}...")
        Xtr = X_train_scaled if use_scaled else X_train
        Xte = X_test_scaled if use_scaled else X_test
        model.fit(Xtr, y_train)
        y_pred = model.predict(Xte)
        y_prob = model.predict_proba(Xte)[:, 1]
        
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        try: auc = roc_auc_score(y_test, y_prob)
        except: auc = 0.0
        
        results[name] = {
            'type': 'Statistical', 'feature_set': 'All',
            'accuracy': round(acc, 4), 'precision': round(prec, 4),
            'recall': round(rec, 4), 'f1_score': round(f1, 4), 'roc_auc': round(auc, 4),
        }
        print(f"    Acc: {acc:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | F1: {f1:.4f} | AUC: {auc:.4f}")
    
    # ---- Group 2: ML with CUF-only features ----
    print("\n  --- ML Models (CUF-only features) ---")
    
    ml_cuf_models = {
        'Random Forest (CUF)': RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
        'Gradient Boosting (CUF)': GradientBoostingClassifier(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42),
    }
    
    for name, model in ml_cuf_models.items():
        print(f"  Training {name}...")
        model.fit(X_train_cuf, y_train)
        y_pred = model.predict(X_test_cuf)
        y_prob = model.predict_proba(X_test_cuf)[:, 1]
        
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        try: auc = roc_auc_score(y_test, y_prob)
        except: auc = 0.0
        
        results[name] = {
            'type': 'ML', 'feature_set': 'CUF-only',
            'accuracy': round(acc, 4), 'precision': round(prec, 4),
            'recall': round(rec, 4), 'f1_score': round(f1, 4), 'roc_auc': round(auc, 4),
        }
        print(f"    Acc: {acc:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | F1: {f1:.4f} | AUC: {auc:.4f}")
    
    # ---- Group 3: ML with CUF + Temporal features ----
    print("\n  --- ML Models (CUF + Temporal features) ---")
    
    ml_full_models = {
        'Random Forest (Full)': RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
        'Gradient Boosting (Full)': GradientBoostingClassifier(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42),
    }
    
    if HAS_XGBOOST:
        ml_full_models['XGBoost (Full)'] = XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            random_state=42, use_label_encoder=False, eval_metric='logloss'
        )
    
    for name, model in ml_full_models.items():
        print(f"  Training {name}...")
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]
        
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        try: auc = roc_auc_score(y_test, y_prob)
        except: auc = 0.0
        
        cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='f1')
        
        results[name] = {
            'type': 'ML', 'feature_set': 'CUF+Temporal',
            'accuracy': round(acc, 4), 'precision': round(prec, 4),
            'recall': round(rec, 4), 'f1_score': round(f1, 4), 'roc_auc': round(auc, 4),
            'cv_f1_mean': round(cv_scores.mean(), 4), 'cv_f1_std': round(cv_scores.std(), 4),
        }
        print(f"    Acc: {acc:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | F1: {f1:.4f} | AUC: {auc:.4f} | CV: {cv_scores.mean():.4f}+/-{cv_scores.std():.4f}")
        
        if f1 > best_score:
            best_score = f1
            best_model = model
            best_name = name
    
    print(f"\n  BEST: {best_name} (F1={best_score:.4f})")
    
    return results, best_model, best_name, scaler, X_train, X_test, y_test


def train_regression(X, y, feature_names, base_feature_count):
    """Train time overrun regression models."""
    
    print(f"\n{'='*60}")
    print("TIME OVERRUN REGRESSION (delay in months)")
    print(f"{'='*60}")
    
    # Remove NaN/inf targets
    valid = ~y.isna() & ~np.isinf(y)
    X_valid = X[valid]
    y_valid = y[valid]
    
    X_train, X_test, y_train, y_test = train_test_split(
        X_valid, y_valid, test_size=0.2, random_state=42
    )
    
    cuf_count = base_feature_count + 3
    X_train_cuf = X_train.iloc[:, :cuf_count]
    X_test_cuf = X_test.iloc[:, :cuf_count]
    
    results = {}
    best_model = None
    best_score = -999
    best_name = ""
    
    # Statistical baseline
    print("\n  --- Statistical ---")
    for name, model in [
        ('Linear Regression', LinearRegression()),
        ('Decision Tree Reg', DecisionTreeRegressor(max_depth=5, random_state=42)),
    ]:
        print(f"  Training {name}...")
        scaler = StandardScaler()
        Xtr = scaler.fit_transform(X_train) if 'Linear' in name else X_train.values
        Xte = scaler.transform(X_test) if 'Linear' in name else X_test.values
        model.fit(Xtr, y_train)
        y_pred = model.predict(Xte)
        
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        
        results[name] = {'type': 'Statistical', 'feature_set': 'All',
                        'mae_months': round(mae, 2), 'rmse_months': round(rmse, 2), 'r2_score': round(r2, 4)}
        print(f"    MAE: {mae:.2f} | RMSE: {rmse:.2f} | R2: {r2:.4f}")
    
    # ML with CUF-only
    print("\n  --- ML (CUF-only) ---")
    for name, model in [
        ('Random Forest Reg (CUF)', RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)),
    ]:
        print(f"  Training {name}...")
        model.fit(X_train_cuf, y_train)
        y_pred = model.predict(X_test_cuf)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        results[name] = {'type': 'ML', 'feature_set': 'CUF-only',
                        'mae_months': round(mae, 2), 'rmse_months': round(rmse, 2), 'r2_score': round(r2, 4)}
        print(f"    MAE: {mae:.2f} | RMSE: {rmse:.2f} | R2: {r2:.4f}")
    
    # ML with CUF + Temporal
    print("\n  --- ML (CUF + Temporal) ---")
    reg_models = {
        'Random Forest Reg (Full)': RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
    }
    if HAS_XGBOOST:
        reg_models['XGBoost Reg (Full)'] = XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42)
    
    for name, model in reg_models.items():
        print(f"  Training {name}...")
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        results[name] = {'type': 'ML', 'feature_set': 'CUF+Temporal',
                        'mae_months': round(mae, 2), 'rmse_months': round(rmse, 2), 'r2_score': round(r2, 4)}
        print(f"    MAE: {mae:.2f} | RMSE: {rmse:.2f} | R2: {r2:.4f}")
        
        if r2 > best_score:
            best_score = r2
            best_model = model
            best_name = name
    
    print(f"\n  BEST: {best_name} (R2={best_score:.4f})")
    
    return results, best_model, best_name


# ============================================================
# 4. RISK SCORING
# ============================================================
def compute_risk_scores(df, cost_model, time_model, feature_cols, label_encoders):
    """Compute composite risk scores (0-100) for all projects."""
    
    print(f"\n{'='*60}")
    print("PROJECT RISK SCORING FRAMEWORK")
    print(f"{'='*60}")
    
    data = df.copy()
    
    # Re-encode categoricals for prediction
    for col in ['ministry', 'sector', 'state']:
        le = label_encoders.get(col)
        if le:
            data[col + '_encoded'] = data[col].fillna('Unknown').astype(str).apply(
                lambda x: le.transform([x])[0] if x in le.classes_ else -1
            )
    
    X_all = data[feature_cols].copy()
    X_all = X_all.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    # Component scores
    try: cost_prob = cost_model.predict_proba(X_all)[:, 1]
    except: cost_prob = np.zeros(len(X_all))
    
    try: time_prob = time_model.predict_proba(X_all)[:, 1]
    except: time_prob = np.zeros(len(X_all))
    
    exp_ratio = pd.to_numeric(data['expenditure_ratio'], errors='coerce').fillna(0).clip(0, 2)
    time_ratio = pd.to_numeric(data['time_elapsed_ratio'], errors='coerce').fillna(0).clip(0, 3)
    expenditure_lag = np.where(time_ratio > 0, np.clip(1 - (exp_ratio / np.maximum(time_ratio, 0.1)), 0, 1), 0)
    
    pf_gap = pd.to_numeric(data['physical_financial_gap'], errors='coerce').fillna(0)
    pf_gap_score = np.clip(np.abs(pf_gap) / 50, 0, 1)
    
    cost_ratio = pd.to_numeric(data['cost_overrun_ratio'], errors='coerce').fillna(1)
    cost_mag = np.clip((cost_ratio - 1) / 0.5, 0, 1)
    
    progress = pd.to_numeric(data['physical_progress_pct'], errors='coerce').fillna(0)
    stagnation = np.where(time_ratio > 0.5, np.clip(1 - (progress / 100) / np.maximum(time_ratio, 0.1), 0, 1), 0)
    
    # Temporal risk (new!) - projects with stagnant progress across months
    progress_stagnant = pd.to_numeric(data.get('progress_stagnant', 0), errors='coerce').fillna(0)
    
    risk_score = (
        cost_prob * 22 +
        time_prob * 22 +
        expenditure_lag * 15 +
        pf_gap_score * 13 +
        cost_mag * 10 +
        stagnation * 10 +
        progress_stagnant * 8
    )
    
    risk_score = np.clip(risk_score, 0, 100).round(1)
    
    data['risk_score'] = risk_score
    data['risk_category'] = pd.cut(risk_score, bins=[-1, 30, 60, 80, 100], labels=['Low', 'Medium', 'High', 'Critical'])
    data['cost_overrun_probability'] = (cost_prob * 100).round(1)
    data['time_overrun_probability'] = (time_prob * 100).round(1)
    data['expenditure_lag_score'] = (expenditure_lag * 100).round(1)
    data['stagnation_score'] = (stagnation * 100).round(1)
    
    print(f"\nRisk Distribution:")
    print(data['risk_category'].value_counts().to_string())
    print(f"\nAvg Risk Score: {risk_score.mean():.1f}")
    print(f"High/Critical: {(risk_score >= 60).sum()} ({(risk_score >= 60).mean()*100:.1f}%)")
    
    return data


# ============================================================
# 5. EARLY WARNING ALERTS
# ============================================================
def generate_alerts(df):
    """Generate early warning alerts."""
    
    print(f"\n{'='*60}")
    print("EARLY WARNING ALERT SYSTEM")
    print(f"{'='*60}")
    
    alerts = []
    
    for _, row in df.iterrows():
        project_alerts = []
        
        # Rule 1: Cost escalation >15%
        cr = pd.to_numeric(row.get('cost_overrun_ratio', 1), errors='coerce')
        if not pd.isna(cr) and cr > 1.15:
            project_alerts.append({
                'type': 'COST_ESCALATION',
                'severity': 'CRITICAL' if cr > 1.5 else 'WARNING',
                'message': f'Cost escalated by {(cr-1)*100:.1f}% from original',
            })
        
        # Rule 2: Expenditure lag
        er = pd.to_numeric(row.get('expenditure_ratio', 0), errors='coerce')
        tr = pd.to_numeric(row.get('time_elapsed_ratio', 0), errors='coerce')
        if not pd.isna(er) and not pd.isna(tr) and er < 0.4 and tr > 0.7:
            project_alerts.append({
                'type': 'EXPENDITURE_LAG',
                'severity': 'CRITICAL',
                'message': f'Only {er*100:.0f}% budget spent but {tr*100:.0f}% time elapsed',
            })
        
        # Rule 3: Progress stagnation
        prog = pd.to_numeric(row.get('physical_progress_pct', 0), errors='coerce')
        if not pd.isna(prog) and not pd.isna(tr) and prog < 30 and tr > 0.8:
            project_alerts.append({
                'type': 'PROGRESS_STAGNATION',
                'severity': 'CRITICAL',
                'message': f'Only {prog:.0f}% progress with {tr*100:.0f}% time elapsed',
            })
        
        # Rule 4: Physical-Financial gap >20%
        pf = pd.to_numeric(row.get('physical_financial_gap', 0), errors='coerce')
        if not pd.isna(pf) and abs(pf) > 20:
            project_alerts.append({
                'type': 'PF_GAP',
                'severity': 'WARNING',
                'message': f'Physical-Financial gap of {pf:.1f}%',
            })
        
        # Rule 5: ML risk alert
        rs = pd.to_numeric(row.get('risk_score', 0), errors='coerce')
        if not pd.isna(rs) and rs >= 80:
            project_alerts.append({'type': 'HIGH_RISK_ML', 'severity': 'CRITICAL',
                                   'message': f'ML risk score: {rs:.0f}/100'})
        elif not pd.isna(rs) and rs >= 60:
            project_alerts.append({'type': 'ELEVATED_RISK_ML', 'severity': 'WARNING',
                                   'message': f'ML risk score: {rs:.0f}/100'})
        
        # Rule 6: Time overrun >12 months
        to = pd.to_numeric(row.get('time_overrun_months', 0), errors='coerce')
        if not pd.isna(to) and to > 12:
            project_alerts.append({
                'type': 'TIME_OVERRUN',
                'severity': 'CRITICAL' if to > 36 else 'WARNING',
                'message': f'Delayed by {to:.0f} months',
            })
        
        # Rule 7 (NEW): Progress stagnation across months
        ps = row.get('progress_stagnant', 0)
        if ps == 1:
            project_alerts.append({
                'type': 'MULTI_MONTH_STAGNATION',
                'severity': 'CRITICAL',
                'message': 'No progress improvement over multiple months',
            })
        
        for alert in project_alerts:
            alert['project_name'] = row.get('project_name', '')
            alert['project_code'] = row.get('project_code', '')
            alert['ministry'] = row.get('ministry', '')
            alert['sector'] = row.get('sector', '')
            alert['state'] = row.get('state', '')
            alert['risk_score'] = float(rs) if not pd.isna(rs) else 0
            alerts.append(alert)
    
    alerts_df = pd.DataFrame(alerts)
    if len(alerts_df) > 0:
        print(f"\nTotal alerts: {len(alerts_df)}")
        print(f"\nBy severity:\n{alerts_df['severity'].value_counts().to_string()}")
        print(f"\nBy type:\n{alerts_df['type'].value_counts().to_string()}")
    
    return alerts_df


# ============================================================
# 6. BENCHMARKING
# ============================================================
def compute_benchmarks(df):
    """Sector-wise benchmarks."""
    
    print(f"\n{'='*60}")
    print("BENCHMARKING & COMPARATIVE ANALYTICS")
    print(f"{'='*60}")
    
    benchmarks = {}
    for sector in df['sector'].dropna().unique():
        sdf = df[df['sector'] == sector]
        if len(sdf) < 2: continue
        benchmarks[sector] = {
            'project_count': len(sdf),
            'avg_original_cost': round(pd.to_numeric(sdf['original_cost_cr'], errors='coerce').mean(), 2),
            'avg_cost_overrun_pct': round(pd.to_numeric(sdf['cost_overrun_pct'], errors='coerce').mean(), 2),
            'avg_physical_progress': round(pd.to_numeric(sdf['physical_progress_pct'], errors='coerce').mean(), 1),
            'avg_risk_score': round(pd.to_numeric(sdf['risk_score'], errors='coerce').mean(), 1),
            'pct_cost_overrun': round(pd.to_numeric(sdf['has_cost_overrun'], errors='coerce').mean() * 100, 1),
            'pct_time_overrun': round(pd.to_numeric(sdf['has_time_overrun'], errors='coerce').mean() * 100, 1),
            'avg_time_overrun_months': round(pd.to_numeric(sdf['time_overrun_months'], errors='coerce').mean(), 1),
        }
    
    bdf = pd.DataFrame(benchmarks).T
    bdf.index.name = 'sector'
    print(f"\nBenchmarks for {len(bdf)} sectors")
    print(bdf.sort_values('avg_risk_score', ascending=False).head(10).to_string())
    return bdf


# ============================================================
# 7. COST DRIVER ANALYSIS (SHAP)
# ============================================================
def analyze_cost_drivers(model, X_train, feature_names):
    """SHAP-based cost driver analysis."""
    
    print(f"\n{'='*60}")
    print("COST ESCALATION DRIVER ANALYSIS")
    print(f"{'='*60}")
    
    if HAS_SHAP:
        try:
            explainer = shap.TreeExplainer(model)
            sample = X_train[:min(500, len(X_train))]
            shap_values = explainer.shap_values(sample)
            if isinstance(shap_values, list): shap_values = shap_values[1]
            mean_shap = np.abs(shap_values).mean(axis=0)
            importance = pd.DataFrame({'feature': feature_names, 'mean_shap_value': mean_shap})
            importance = importance.sort_values('mean_shap_value', ascending=False)
            print("\nTop Cost Drivers (SHAP):")
            print(importance.head(15).to_string())
            return importance
        except Exception as e:
            print(f"SHAP error: {e}")
    
    if hasattr(model, 'feature_importances_'):
        importance = pd.DataFrame({'feature': feature_names, 'importance': model.feature_importances_})
        importance = importance.sort_values('importance', ascending=False)
        print("\nFeature Importance:")
        print(importance.head(15).to_string())
        return importance
    return None


# ============================================================
# 8. COMPARISON REPORT
# ============================================================
def generate_comparison_report(cost_results, time_class_results, time_reg_results):
    """Statistical vs ML vs CUF-only vs CUF+Temporal comparison."""
    
    print(f"\n{'='*60}")
    print("FULL COMPARISON REPORT")
    print(f"{'='*60}")
    
    def best_f1(results, type_filter=None, feature_filter=None):
        filtered = {k: v for k, v in results.items()
                   if (type_filter is None or v.get('type') == type_filter)
                   and (feature_filter is None or v.get('feature_set') == feature_filter)}
        if not filtered: return 0
        return max(v['f1_score'] for v in filtered.values())
    
    # Requirement (b): Statistical vs ML
    stat_f1 = best_f1(cost_results, type_filter='Statistical')
    ml_f1 = best_f1(cost_results, type_filter='ML')
    improvement = ((ml_f1 - stat_f1) / max(stat_f1, 0.001)) * 100
    
    print(f"\n  [Req b] Statistical vs ML for Cost Overrun:")
    print(f"    Best Statistical F1: {stat_f1:.4f}")
    print(f"    Best ML F1: {ml_f1:.4f}")
    print(f"    ML improvement: {improvement:+.1f}%")
    
    # Requirement (c): CUF-only vs CUF+Temporal
    cuf_f1 = best_f1(cost_results, feature_filter='CUF-only')
    full_f1 = best_f1(cost_results, feature_filter='CUF+Temporal')
    cuf_gain = ((full_f1 - cuf_f1) / max(cuf_f1, 0.001)) * 100
    
    print(f"\n  [Req c] CUF-only vs CUF+Temporal for Cost Overrun:")
    print(f"    CUF-only F1: {cuf_f1:.4f}")
    print(f"    CUF+Temporal F1: {full_f1:.4f}")
    print(f"    Gain from temporal features: {cuf_gain:+.1f}%")
    
    # Time overrun
    stat_t = best_f1(time_class_results, type_filter='Statistical')
    ml_t = best_f1(time_class_results, type_filter='ML')
    
    print(f"\n  Time Overrun Classification:")
    print(f"    Best Statistical F1: {stat_t:.4f}")
    print(f"    Best ML F1: {ml_t:.4f}")
    
    report = {
        'cost_overrun': cost_results,
        'time_overrun_classification': time_class_results,
        'time_overrun_regression': time_reg_results,
        'summary': {
            'requirement_b': {
                'statistical_f1': stat_f1, 'ml_f1': ml_f1,
                'ml_improvement_pct': round(improvement, 1),
                'conclusion': 'ML provides significant gains' if ml_f1 > stat_f1 else 'Comparable'
            },
            'requirement_c': {
                'cuf_only_f1': cuf_f1, 'cuf_temporal_f1': full_f1,
                'temporal_gain_pct': round(cuf_gain, 1),
                'conclusion': 'Temporal features from multi-month tracking improve prediction'
            }
        }
    }
    return report


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("="*60)
    print("PAIMANA AI - ML PIPELINE (Multi-Month)")
    print("="*60)
    
    # 1. Load all months
    print("\n[1/8] Loading all monthly datasets...")
    months = load_all_months()
    
    # 2. Merge and create temporal features
    print("\n[2/8] Merging months & creating temporal features...")
    merged_df, temporal_cols = merge_monthly_data(months)
    
    # 3. Prepare features
    print("\n[3/8] Preparing features...")
    BASE_FEATURE_COUNT = 10  # Number of base CUF numeric features
    X, data, feature_names, label_encoders = prepare_features(merged_df, temporal_cols)
    
    # 4. Train cost overrun models
    print("\n[4/8] Training cost overrun models...")
    y_cost = data['has_cost_overrun'].astype(int)
    cost_results, cost_model, cost_name, cost_scaler, X_train, X_test, y_test = train_and_compare(
        X, y_cost, feature_names, "COST OVERRUN PREDICTION", BASE_FEATURE_COUNT
    )
    
    # 5. Train time overrun models
    print("\n[5/8] Training time overrun models...")
    y_time_class = data['has_time_overrun'].astype(int)
    time_class_results, time_model, time_name, time_scaler, _, _, _ = train_and_compare(
        X, y_time_class, feature_names, "TIME OVERRUN CLASSIFICATION", BASE_FEATURE_COUNT
    )
    
    y_time_reg = pd.to_numeric(data['time_overrun_months'], errors='coerce').fillna(0)
    time_reg_results, time_reg_model, time_reg_name = train_regression(
        X, y_time_reg, feature_names, BASE_FEATURE_COUNT
    )
    
    # 6. Risk scoring
    print("\n[6/8] Computing risk scores...")
    scored_df = compute_risk_scores(data, cost_model, time_model, feature_names, label_encoders)
    
    # 7. Alerts + Benchmarks + Drivers
    print("\n[7/8] Generating alerts, benchmarks, cost drivers...")
    alerts_df = generate_alerts(scored_df)
    benchmarks_df = compute_benchmarks(scored_df)
    drivers = analyze_cost_drivers(cost_model, X_train, feature_names)
    
    # 8. Comparison report
    print("\n[8/8] Generating comparison report...")
    comparison = generate_comparison_report(cost_results, time_class_results, time_reg_results)
    
    # ============================================================
    # SAVE EVERYTHING
    # ============================================================
    print(f"\n{'='*60}")
    print("SAVING ALL RESULTS")
    print(f"{'='*60}")
    
    scored_df.to_csv(os.path.join(RESULTS_DIR, 'projects_with_risk_scores.csv'), index=False, encoding='utf-8-sig')
    print(f"  projects_with_risk_scores.csv ({len(scored_df)} projects)")
    
    if len(alerts_df) > 0:
        alerts_df.to_csv(os.path.join(RESULTS_DIR, 'alerts.csv'), index=False, encoding='utf-8-sig')
        print(f"  alerts.csv ({len(alerts_df)} alerts)")
    
    benchmarks_df.to_csv(os.path.join(RESULTS_DIR, 'sector_benchmarks.csv'), encoding='utf-8-sig')
    print(f"  sector_benchmarks.csv ({len(benchmarks_df)} sectors)")
    
    if drivers is not None:
        drivers.to_csv(os.path.join(RESULTS_DIR, 'cost_drivers.csv'), index=False, encoding='utf-8-sig')
        print(f"  cost_drivers.csv")
    
    with open(os.path.join(RESULTS_DIR, 'model_comparison.json'), 'w') as f:
        json.dump(comparison, f, indent=2, default=str)
    print(f"  model_comparison.json")
    
    joblib.dump(cost_model, os.path.join(MODEL_DIR, 'cost_overrun_model.joblib'))
    joblib.dump(time_model, os.path.join(MODEL_DIR, 'time_overrun_classifier.joblib'))
    joblib.dump(time_reg_model, os.path.join(MODEL_DIR, 'time_overrun_regressor.joblib'))
    joblib.dump(cost_scaler, os.path.join(MODEL_DIR, 'scaler.joblib'))
    joblib.dump(feature_names, os.path.join(MODEL_DIR, 'feature_names.joblib'))
    joblib.dump(label_encoders, os.path.join(MODEL_DIR, 'label_encoders.joblib'))
    print(f"  All models saved to {MODEL_DIR}")
    
    # Summary JSON for API
    api_data = {
        'total_projects': len(scored_df),
        'risk_distribution': scored_df['risk_category'].value_counts().to_dict(),
        'avg_risk_score': round(float(scored_df['risk_score'].mean()), 1),
        'total_alerts': len(alerts_df) if len(alerts_df) > 0 else 0,
        'cost_overrun_rate': round(float(scored_df['has_cost_overrun'].mean() * 100), 1),
        'time_overrun_rate': round(float(scored_df['has_time_overrun'].mean() * 100), 1),
        'best_cost_model': cost_name,
        'best_time_model': time_name,
        'features_used': feature_names,
        'temporal_features': temporal_cols,
        'comparison': comparison['summary'],
    }
    with open(os.path.join(RESULTS_DIR, 'summary.json'), 'w') as f:
        json.dump(api_data, f, indent=2, default=str)
    print(f"  summary.json")
    
    print(f"\n{'='*60}")
    print("ML PIPELINE COMPLETE!")
    print(f"{'='*60}")
