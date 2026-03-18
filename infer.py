import os, glob, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd 

from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error

COMP_DATASET_DIR = "/kaggle/input/forecasting-the-future-the-helios-corn-climate-challenge"
MASTER_FILE = "corn_climate_risk_futures_daily_master.csv"
SHARE_FILE  = "corn_regional_market_share.csv"

RANDOM_SEED = 42

LAGS = [1, 2, 3, 5, 7, 14, 30]
ROLL_WINDOWS = [7, 14, 30, 60]

HORIZON = 1

LGB_PARAMS = dict(
    n_estimators=4000,
    learning_rate=0.02,
    num_leaves=63,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=1.0,
    reg_lambda=1.0,
    min_child_samples=50,
    random_state=RANDOM_SEED,
)

def find_file(base_dir: str, filename: str):
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        return path
    matches = glob.glob(os.path.join(base_dir, "**", filename), recursive=True)
    return matches[0] if matches else None

def try_load_submission_template(base_dir: str):
    candidates = []
    for pat in ["*sample*submission*.csv", "*submission*format*.csv", "*submission*.csv"]:
        candidates += glob.glob(os.path.join(base_dir, "**", pat), recursive=True)
    candidates = sorted(list(set(candidates)))
    return candidates[0] if candidates else None

def infer_target_columns(train_df: pd.DataFrame, test_df: pd.DataFrame):
    diff = sorted(list(set(train_df.columns) - set(test_df.columns)))
    preferred = [c for c in diff if "ret_log" in c] + \
                [c for c in diff if "ret_pct" in c] + \
                [c for c in diff if ("futures_close" in c and "ZC_1" in c)]
    if preferred:
        return preferred
    return diff

def add_weighted_climate_signals(df: pd.DataFrame):
    if "region_weight" not in df.columns:
        df["region_weight"] = 0.0
    
    families = [
        "climate_risk_cnt_locations_heat_stress_risk",
        "climate_risk_cnt_locations_unseasonably_cold_rist",
        "climate_risk_cnt_locations_excess_precip_risk",
        "climate_risk_cnt_locations_drought_risk",
    ]

    for fam in families:
        low = f"{fam}_low"
        med = f"{fam}_medium"
        hig = f"{fam}_high"
        if all(col in df.columns for col in [low,med,hig]):
            intensity = (1.0 * df[low] + 2.0 * df[med] + 3.0 * df[hig])
            df[f"{fam}_intensity"] = intensity
            df[f"{fam}_w_intensity"] = intensity * df["region_weight"]

            total = df[low] + df[med] + df[hig]
            df[f"{fam}_high_frac"] = np.where(total > 0, df[hig] / total, 0.0)
            df[f"{fam}_w_high_frac"] = df[f"{fam}_high_frac"] * df["region_weight"]
    
    return df

def add_groupwise_lag_roll(df: pd.DataFrame, group_cols, time_col, feature_cols):
    df = df.sort_values(group_cols + [time_col].copy())
    g = df.groupby(group_cols, sort=False)
    for c in feature_cols:
        for lag in LAGS:
            df[f"{c}_lag{lag}"] = g[c].shift(lag)
        s = g[c].shift(1)
        for w in ROLL_WINDOWS:
            df[f"{c}_rmean{w}"] = s.rolling(w, min_periods=max(3, w//4)).mean()
            df[f"{c}_rstd{w}"] = s.rolling(w, min_periods=max(3, w//4)).std()
            df[f"{c}_rmax{w}"] = s.rolling(w, min_periods=max(3, w//4)).max()
            df[f"{c}_rmin{w}"] = s.rolling(w, min_periods=max(3, w//4)).min()
        
        df[f"{c}_diff1"] = g[c].diff(1)
    return df

def make_global_aggregates(df: pd.DataFrame, time_col = "data_on"):
    w_cols = [c for c in df.columns if c.endswith("_w_intensity") or c.endswith("_w_high_frac")]
    if not w_cols:
        return df
    
    glob = df.groupby(time_col, as_index=False)[w_cols].sum()
    glob.columns = [time_col] + [f"global_{c}" for c in w_cols]
    df = df.merge(glob, on=time_col, how="left")
    return df

