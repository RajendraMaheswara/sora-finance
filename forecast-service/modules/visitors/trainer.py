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

logger = logging.getLogger("visitors_trainer")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
    logger.addHandler(ch)


class VisitorForecasterTrainer:
    """
    Melatih model Random Forest untuk prediksi jumlah pengunjung harian.
    Menggunakan TimeSeriesSplit untuk cross-validation yang tepat pada data time series.
    """

    def __init__(self):
        self.model_dir = Config.VISITORS_MODEL_DIR
        os.makedirs(self.model_dir, exist_ok=True)

    def _model_basename(self, store_id: str, granularity: str) -> str:
        if granularity == "daily":
            return f"rf_model_{store_id}.joblib"
        return f"rf_model_{granularity}_{store_id}.joblib"

    def _meta_basename(self, store_id: str, granularity: str) -> str:
        if granularity == "daily":
            return f"rf_meta_{store_id}.json"
        return f"rf_meta_{granularity}_{store_id}.json"

    def _scaler_basename(self, store_id: str, granularity: str) -> str:
        if granularity == "daily":
            return f"rf_scaler_{store_id}.joblib"
        return f"rf_scaler_{granularity}_{store_id}.joblib"

    def _feature_cols_basename(self, store_id: str, granularity: str) -> str:
        if granularity == "daily":
            return f"rf_features_{store_id}.json"
        return f"rf_features_{granularity}_{store_id}.json"

    def _model_path(self, store_id: str, granularity: str) -> str:
        return os.path.join(self.model_dir, self._model_basename(store_id, granularity))

    def _meta_path(self, store_id: str, granularity: str) -> str:
        return os.path.join(self.model_dir, self._meta_basename(store_id, granularity))

    def _scaler_path(self, store_id: str, granularity: str) -> str:
        return os.path.join(self.model_dir, self._scaler_basename(store_id, granularity))

    def _feature_cols_path(self, store_id: str, granularity: str) -> str:
        return os.path.join(self.model_dir, self._feature_cols_basename(store_id, granularity))

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
        y = df["visitors"].values.astype(float)

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
        model_path = self._model_path(store_id, granularity)
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model untuk store {store_id} tidak ditemukan. "
                "Jalankan /forecast/retrain terlebih dahulu."
            )

        model = joblib.load(model_path)
        scaler = joblib.load(self._scaler_path(store_id, granularity))

        with open(self._feature_cols_path(store_id, granularity)) as f:
            feature_cols = json.load(f)

        with open(self._meta_path(store_id, granularity)) as f:
            meta = json.load(f)

        logger.info(f"Model loaded: store={store_id}, trained_at={meta.get('trained_at')}")
        return model, scaler, feature_cols, meta

    def model_exists(self, store_id: str, granularity: str = "daily") -> bool:
        return os.path.exists(self._model_path(store_id, granularity))

    def list_trained_stores(self, granularity: str = "daily") -> list:
        stores = []
        for fname in os.listdir(self.model_dir):
            if granularity == "daily":
                if fname.startswith("rf_model_") and fname.endswith(".joblib"):
                    store_id = fname.replace("rf_model_", "").replace(".joblib", "")
                    if "_" not in store_id:
                        stores.append(store_id)
            else:
                prefix = f"rf_model_{granularity}_"
                if fname.startswith(prefix) and fname.endswith(".joblib"):
                    store_id = fname.replace(prefix, "").replace(".joblib", "")
                    stores.append(store_id)
        return stores

trainer = VisitorForecasterTrainer()
