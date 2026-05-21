# -*- coding: utf-8 -*-
"""
Exports model artifacts from joblib (xgboost 3.x pickle) to version-neutral formats
so the SageMaker XGBoost 1.7 container can load them without pickle version mismatch.

  XGBoost models     → models/*.ubj   (native XGBoost binary JSON)
  Label encoders     → models/label_encoder_*.json  (classes list)
  Preprocessor       → data/processed/preprocessor.json  (scaler params)

Run from project root:  py infrastructure/export_native.py
"""
import json
import joblib
import numpy as np

# ---------------------------------------------------------------------------
# XGBoost models → native binary format
# ---------------------------------------------------------------------------
model_a = joblib.load("models/modelo_a_mozo.joblib")
model_a.get_booster().save_model("models/modelo_a_mozo.ubj")
print("Exported: models/modelo_a_mozo.ubj")

for curso in ["entrada", "principal", "postre", "bebida"]:
    m = joblib.load(f"models/modelo_b_{curso}.joblib")
    m.get_booster().save_model(f"models/modelo_b_{curso}.ubj")
    print(f"Exported: models/modelo_b_{curso}.ubj")

# ---------------------------------------------------------------------------
# Label encoders → JSON  (just the classes_ array)
# ---------------------------------------------------------------------------
for curso in ["entrada", "principal", "postre", "bebida"]:
    le = joblib.load(f"models/label_encoder_{curso}.joblib")
    with open(f"models/label_encoder_{curso}.json", "w", encoding="utf-8") as f:
        json.dump(le.classes_.tolist(), f)
    print(f"Exported: models/label_encoder_{curso}.json")

# ---------------------------------------------------------------------------
# Preprocessor → JSON  (scaler min/max/scale params + segment means)
# ---------------------------------------------------------------------------
pp = joblib.load("data/processed/preprocessor.joblib")

export = {
    "segment_means": {str(k): float(v) for k, v in pp["segment_means"].items()},
    "global_mean_ticket": float(pp["global_mean_ticket"]),
    "feature_names": pp["feature_names"],
    "scalers": {},
}
for col, scaler in pp["scalers"].items():
    export["scalers"][col] = {
        "data_min_":   scaler.data_min_.tolist(),
        "data_max_":   scaler.data_max_.tolist(),
        "scale_":      scaler.scale_.tolist(),
        "data_range_": scaler.data_range_.tolist(),
        "min_":        scaler.min_.tolist(),
    }

with open("data/processed/preprocessor.json", "w", encoding="utf-8") as f:
    json.dump(export, f, ensure_ascii=False)
print("Exported: data/processed/preprocessor.json")
print("Done.")
