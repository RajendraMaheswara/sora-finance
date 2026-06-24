import os
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Tuple, Any
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
import logging

from config import Config

logger = logging.getLogger("sales_trainer")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
    logger.addHandler(ch)

class SalesForecasterTrainer:
    """
    Melatih model Random Forest untuk prediksi sales/omzet harian.
    Menggunakan TimeSeriesSplit untuk cross-validation yang tepat pada data time series.
    """

    def __init__(self):
        self.model_dir = Config.SALES_MODELS_DIR
        os.makedirs(self.model_dir, exist_ok=True)

    def _artifact_basename(self, store_id: str, granularity: str, kind: str, ext: str) -> str:
        clean_granularity = (granularity or "daily").strip().lower()
        clean_store_id = str(store_id).strip()
        return f"sales_{clean_granularity}_{kind}_store_{clean_store_id}.{ext}"

    def _artifact_path(self, store_id: str, granularity: str, kind: str, ext: str) -> str:
        return os.path.join(self.model_dir, self._artifact_basename(store_id, granularity, kind, ext))

    def _legacy_artifact_basename(self, store_id: str, granularity: str, kind: str, ext: str) -> str:
        """
        Kompatibilitas untuk file lama:
        rf_model_<store_id>.joblib
        rf_model_weekly_<store_id>.joblib
        """
        legacy_kind = "features" if kind == "features" else kind
        if kind == "metadata":
            legacy_kind = "meta"
        if granularity == "daily":
            return f"rf_{legacy_kind}_{store_id}.{ext}"
        return f"rf_{legacy_kind}_{granularity}_{store_id}.{ext}"

    def _legacy_artifact_path(self, store_id: str, granularity: str, kind: str, ext: str) -> str:
        return os.path.join(self.model_dir, self._legacy_artifact_basename(store_id, granularity, kind, ext))

    def _resolve_artifact_path(self, store_id: str, granularity: str, kind: str, ext: str) -> str:
        current_path = self._artifact_path(store_id, granularity, kind, ext)
        if os.path.exists(current_path):
            return current_path

        legacy_path = self._legacy_artifact_path(store_id, granularity, kind, ext)
        if os.path.exists(legacy_path):
            return legacy_path

        return current_path

    def _model_path(self, store_id: str, granularity: str) -> str:
        return self._artifact_path(store_id, granularity, "model", "joblib")

    def _meta_path(self, store_id: str, granularity: str) -> str:
        return self._artifact_path(store_id, granularity, "metadata", "json")

    def _scaler_path(self, store_id: str, granularity: str) -> str:
        return self._artifact_path(store_id, granularity, "scaler", "joblib")

    def _feature_cols_path(self, store_id: str, granularity: str) -> str:
        return self._artifact_path(store_id, granularity, "features", "json")

    def train(
        self,
        df: pd.DataFrame,
        feature_cols: list,
        store_id: str,
        granularity: str = "daily",
    ) -> Dict[str, Any]:
        """
        Latih model Random Forest dengan cross-validation berbasis time series.
        """
        logger.info(f"Mulai training untuk store {store_id} | {len(df)} data points")

        X = df[feature_cols].values
        y = df["omzet"].values.astype(float)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        tscv = TimeSeriesSplit(n_splits=5)
        mae_scores, rmse_scores = [], []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X_scaled)):
            X_train, X_val = X_scaled[train_idx], X_scaled[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            fold_model = RandomForestRegressor(
                n_estimators=200,
                max_depth=12,
                min_samples_split=5,
                min_samples_leaf=2,
                max_features="sqrt",
                bootstrap=True,
                random_state=42,
                n_jobs=-1,
            )
            fold_model.fit(X_train, y_train)
            y_pred = fold_model.predict(X_val)
            y_pred = np.maximum(y_pred, 0)

            mae = mean_absolute_error(y_val, y_pred)
            rmse = np.sqrt(mean_squared_error(y_val, y_pred))
            mae_scores.append(mae)
            rmse_scores.append(rmse)
            logger.info(f"  Fold {fold + 1}: MAE={mae:.2f}, RMSE={rmse:.2f}")

        cv_mae = float(np.mean(mae_scores))
        cv_rmse = float(np.mean(rmse_scores))
        logger.info(f"Cross-validation selesai → MAE={cv_mae:.2f}, RMSE={cv_rmse:.2f}")

        final_model = RandomForestRegressor(
            n_estimators=300,
            max_depth=12,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features="sqrt",
            bootstrap=True,
            random_state=42,
            n_jobs=-1,
        )
        final_model.fit(X_scaled, y)

        importance = dict(
            zip(feature_cols, final_model.feature_importances_.round(4).tolist())
        )
        top_features = dict(
            sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        joblib.dump(final_model, self._model_path(store_id, granularity))
        joblib.dump(scaler, self._scaler_path(store_id, granularity))

        with open(self._feature_cols_path(store_id, granularity), "w") as f:
            json.dump(feature_cols, f)

        meta = {
            "store_id": store_id,
            "granularity": granularity,
            "trained_at": datetime.utcnow().isoformat(),
            "training_data_points": len(df),
            "feature_count": len(feature_cols),
            "cv_mae": cv_mae,
            "cv_rmse": cv_rmse,
            "feature_importance": importance,
            "top_features": top_features,
        }
        with open(self._meta_path(store_id, granularity), "w") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Model tersimpan: {self._model_path(store_id, granularity)}")
        return meta

    def load_model(
        self, store_id: str, granularity: str = "daily"
    ) -> Tuple[RandomForestRegressor, StandardScaler, list, dict]:
        model_path = self._resolve_artifact_path(store_id, granularity, "model", "joblib")
        scaler_path = self._resolve_artifact_path(store_id, granularity, "scaler", "joblib")
        feature_path = self._resolve_artifact_path(store_id, granularity, "features", "json")
        meta_path = self._resolve_artifact_path(store_id, granularity, "metadata", "json")

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model untuk store {store_id} tidak ditemukan. "
                "Jalankan /forecast/sales/retrain terlebih dahulu."
            )

        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)

        with open(feature_path) as f:
            feature_cols = json.load(f)

        with open(meta_path) as f:
            meta = json.load(f)

        logger.info(f"Model loaded: store={store_id}, trained_at={meta.get('trained_at')}")
        return model, scaler, feature_cols, meta

    def model_exists(self, store_id: str, granularity: str = "daily") -> bool:
        model_path = self._resolve_artifact_path(store_id, granularity, "model", "joblib")
        return os.path.exists(model_path)

    def list_trained_stores(self, granularity: str = "daily") -> list:
        stores = set()
        new_prefix = f"sales_{granularity}_model_store_"
        old_prefix = "rf_model_" if granularity == "daily" else f"rf_model_{granularity}_"

        for fname in os.listdir(self.model_dir):
            if not fname.endswith(".joblib"):
                continue

            if fname.startswith(new_prefix):
                store_id = fname.replace(new_prefix, "").replace(".joblib", "")
                stores.add(store_id)
                continue

            if fname.startswith(old_prefix):
                store_id = fname.replace(old_prefix, "").replace(".joblib", "")
                if granularity != "daily" or "_" not in store_id:
                    stores.add(store_id)

        return sorted(stores)

trainer = SalesForecasterTrainer()

def train_all():
    pass