import logging
import uuid
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import KFold, StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, OrdinalEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.svm import SVC, SVR
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from xgboost import XGBClassifier, XGBRegressor

from app.config import settings
from app.models.dataset import DatasetVersion
from app.models.plan import Plan
from app.models.run import ExperimentResult, Run

logger = logging.getLogger(__name__)

# Synchronous DB engine for RQ worker (RQ is sync; async engine cannot be used)
_sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
_sync_engine = create_engine(_sync_url, pool_pre_ping=True)
SyncSession = sessionmaker(bind=_sync_engine, expire_on_commit=False)

MODEL_REGISTRY: dict = {
    "LogisticRegression": LogisticRegression,
    "RandomForestClassifier": RandomForestClassifier,
    "RandomForestRegressor": RandomForestRegressor,
    "GradientBoostingClassifier": GradientBoostingClassifier,
    "GradientBoostingRegressor": GradientBoostingRegressor,
    "Ridge": Ridge,
    "Lasso": Lasso,
    "SVR": SVR,
    "SVC": SVC,
    "XGBClassifier": XGBClassifier,
    "XGBRegressor": XGBRegressor,
}


def _compute_metrics(
    y_true,
    y_pred,
    y_proba,
    task_type: str,
    requested_metrics: list[str],
) -> dict:
    results = {}
    for metric in requested_metrics:
        try:
            if metric == "accuracy":
                results[metric] = round(float(accuracy_score(y_true, y_pred)), 6)
            elif metric == "f1":
                results[metric] = round(float(f1_score(y_true, y_pred, average="weighted", zero_division=0)), 6)
            elif metric == "precision":
                results[metric] = round(float(precision_score(y_true, y_pred, average="weighted", zero_division=0)), 6)
            elif metric == "recall":
                results[metric] = round(float(recall_score(y_true, y_pred, average="weighted", zero_division=0)), 6)
            elif metric == "roc_auc":
                if y_proba is not None:
                    classes = np.unique(y_true)
                    if len(classes) == 2:
                        score = roc_auc_score(y_true, y_proba[:, 1])
                    else:
                        score = roc_auc_score(y_true, y_proba, multi_class="ovr", average="weighted")
                    results[metric] = round(float(score), 6)
            elif metric == "rmse":
                results[metric] = round(float(sqrt(mean_squared_error(y_true, y_pred))), 6)
            elif metric == "mae":
                results[metric] = round(float(mean_absolute_error(y_true, y_pred)), 6)
            elif metric == "r2":
                results[metric] = round(float(r2_score(y_true, y_pred)), 6)
        except Exception as e:
            logger.warning("Could not compute metric %s: %s", metric, e)
    return results


def _build_preprocessor(
    numeric_cols: list[str],
    categorical_cols: list[str],
    imputation: str,
    scaling: str,
    encode_categoricals: bool,
) -> ColumnTransformer:
    numeric_steps = [("imputer", SimpleImputer(strategy=imputation))]
    if scaling == "standard":
        numeric_steps.append(("scaler", StandardScaler()))
    elif scaling == "minmax":
        numeric_steps.append(("scaler", MinMaxScaler()))

    transformers = []
    if numeric_cols:
        transformers.append(("numeric", Pipeline(numeric_steps), numeric_cols))

    if categorical_cols and encode_categoricals:
        cat_steps = [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]
        transformers.append(("categorical", Pipeline(cat_steps), categorical_cols))
    elif categorical_cols:
        # Drop categoricals if not encoding
        transformers.append(("categorical_drop", "drop", categorical_cols))

    if not transformers:
        from sklearn.preprocessing import FunctionTransformer
        return ColumnTransformer(
            transformers=[("passthrough", FunctionTransformer(), [])],
            remainder="passthrough",
        )

    return ColumnTransformer(transformers=transformers, remainder="drop")


def train_model(run_id: str) -> None:
    db: Session = SyncSession()
    run = db.get(Run, uuid.UUID(run_id))
    if run is None:
        logger.error("Run %s not found", run_id)
        db.close()
        return

    run.status = "running"
    run.started_at = datetime.now(tz=timezone.utc)
    db.commit()

    try:
        _do_train(db, run)
    except Exception as exc:
        logger.exception("Training failed for run %s", run_id)
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.completed_at = datetime.now(tz=timezone.utc)
        db.commit()
    finally:
        db.close()


def _do_train(db: Session, run: Run) -> None:
    plan: Plan = db.get(Plan, run.plan_id)
    dataset_version: DatasetVersion = db.get(DatasetVersion, plan.dataset_version_id)

    pj = plan.plan_json
    task_type: str = pj["task_type"]
    target_col: str = pj["target_column"]
    feature_cols: list[str] = pj["feature_columns"]
    model_choices: list[dict] = pj["model_choices"]
    validation_method: str = pj["validation_method"]
    requested_metrics: list[str] = pj["metrics"]
    preprocessing: dict = pj["preprocessing"]

    # Load data
    df = pd.read_csv(dataset_version.file_path)
    df = df.dropna(subset=[target_col])

    # Separate available features
    available_features = [c for c in feature_cols if c in df.columns]
    X = df[available_features]
    y = df[target_col]

    # Identify column types
    numeric_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = X.select_dtypes(exclude=[np.number]).columns.tolist()

    preprocessor = _build_preprocessor(
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        imputation=preprocessing.get("imputation", "median"),
        scaling=preprocessing.get("scaling", "standard"),
        encode_categoricals=preprocessing.get("encode_categoricals", True),
    )

    # Parse validation method
    method_lower = validation_method.lower()
    use_kfold = method_lower.startswith("stratified_kfold") or method_lower.startswith("kfold")
    holdout_test_size = 0.2

    if not use_kfold:
        # e.g. "holdout_0.2"
        parts = method_lower.split("_")
        if len(parts) >= 2:
            try:
                holdout_test_size = float(parts[-1])
            except ValueError:
                holdout_test_size = 0.2

    kfold_splits = 5
    if use_kfold:
        parts = method_lower.split("_")
        try:
            kfold_splits = int(parts[-1])
        except (ValueError, IndexError):
            kfold_splits = 5

    # Encode target for classification if needed
    label_encoder = None
    if task_type == "classification" and y.dtype == object:
        from sklearn.preprocessing import LabelEncoder
        label_encoder = LabelEncoder()
        y = pd.Series(label_encoder.fit_transform(y), index=y.index)

    artifact_dir = Path(settings.artifacts_dir) / run.id.hex
    artifact_dir.mkdir(parents=True, exist_ok=True)

    all_model_metrics: dict = {}
    best_model_name: str | None = None
    best_score: float = -float("inf")
    primary_metric = requested_metrics[0] if requested_metrics else "accuracy"

    for choice in model_choices:
        model_name = choice["name"]
        hyperparams = choice.get("hyperparameters", {})

        if model_name not in MODEL_REGISTRY:
            logger.warning("Unknown model %s — skipping", model_name)
            continue

        model_cls = MODEL_REGISTRY[model_name]
        try:
            model_instance = model_cls(**hyperparams)
        except TypeError as e:
            logger.warning("Bad hyperparameters for %s: %s — using defaults", model_name, e)
            model_instance = model_cls()

        pipeline = Pipeline([("preprocessor", preprocessor), ("model", model_instance)])

        model_metrics: dict = {}

        if use_kfold:
            if task_type == "classification":
                cv = StratifiedKFold(n_splits=kfold_splits, shuffle=True, random_state=42)
            else:
                cv = KFold(n_splits=kfold_splits, shuffle=True, random_state=42)

            for fold_idx, (train_idx, val_idx) in enumerate(cv.split(X, y)):
                X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

                pipeline.fit(X_train, y_train)
                y_pred = pipeline.predict(X_val)
                y_proba = None
                if task_type == "classification" and hasattr(pipeline, "predict_proba"):
                    try:
                        y_proba = pipeline.predict_proba(X_val)
                    except Exception:
                        pass

                fold_metrics = _compute_metrics(y_val, y_pred, y_proba, task_type, requested_metrics)
                _store_result(db, run, model_name, f"fold_{fold_idx + 1}", fold_metrics, None)

            # Final fit on all data for feature importances + artifact
            pipeline.fit(X, y)
            model_metrics = _compute_metrics(y, pipeline.predict(X), None, task_type, requested_metrics)

        else:
            # Holdout split
            stratify = y if task_type == "classification" else None
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=holdout_test_size, random_state=42, stratify=stratify
            )
            pipeline.fit(X_train, y_train)

            # Train metrics
            y_train_pred = pipeline.predict(X_train)
            y_train_proba = None
            if task_type == "classification" and hasattr(pipeline, "predict_proba"):
                try:
                    y_train_proba = pipeline.predict_proba(X_train)
                except Exception:
                    pass
            train_metrics = _compute_metrics(y_train, y_train_pred, y_train_proba, task_type, requested_metrics)
            _store_result(db, run, model_name, "train", train_metrics, None)

            # Test metrics
            y_test_pred = pipeline.predict(X_test)
            y_test_proba = None
            if task_type == "classification" and hasattr(pipeline, "predict_proba"):
                try:
                    y_test_proba = pipeline.predict_proba(X_test)
                except Exception:
                    pass
            test_metrics = _compute_metrics(y_test, y_test_pred, y_test_proba, task_type, requested_metrics)

            # Feature importances
            feature_importances = _extract_importances(pipeline, available_features)
            _store_result(db, run, model_name, "test", test_metrics, feature_importances)
            model_metrics = test_metrics

        # Save artifact
        artifact_path = artifact_dir / f"{model_name}.joblib"
        joblib.dump(pipeline, str(artifact_path))

        all_model_metrics[model_name] = model_metrics

        # Track best model by primary metric
        score = model_metrics.get(primary_metric, -float("inf"))
        if score > best_score:
            best_score = score
            best_model_name = model_name

    run.metrics = {
        "best_model": best_model_name,
        "best_score": best_score if best_score != -float("inf") else None,
        "metric": primary_metric,
        "models": all_model_metrics,
    }
    run.model_artifacts_path = str(artifact_dir) + "/"
    run.status = "completed"
    run.completed_at = datetime.now(tz=timezone.utc)
    db.commit()


def _store_result(
    db: Session,
    run: Run,
    model_name: str,
    split: str,
    metrics: dict,
    feature_importances: dict | None,
) -> None:
    result = ExperimentResult(
        run_id=run.id,
        user_id=run.user_id,
        model_name=model_name,
        split=split,
        metrics=metrics,
        feature_importances=feature_importances,
    )
    db.add(result)
    db.commit()


def _extract_importances(pipeline: Pipeline, feature_cols: list[str]) -> dict | None:
    try:
        model_step = pipeline.named_steps.get("model")
        if model_step is None:
            return None

        if hasattr(model_step, "feature_importances_"):
            importances = model_step.feature_importances_
        elif hasattr(model_step, "coef_"):
            coef = model_step.coef_
            if coef.ndim > 1:
                importances = np.abs(coef).mean(axis=0)
            else:
                importances = np.abs(coef)
        else:
            return None

        # Try to get transformed feature names from the preprocessor
        preprocessor = pipeline.named_steps.get("preprocessor")
        if preprocessor is not None and hasattr(preprocessor, "get_feature_names_out"):
            try:
                names = list(preprocessor.get_feature_names_out())
            except Exception:
                names = feature_cols
        else:
            names = feature_cols

        if len(names) != len(importances):
            names = [f"feature_{i}" for i in range(len(importances))]

        return {name: round(float(imp), 6) for name, imp in zip(names, importances)}
    except Exception as e:
        logger.warning("Could not extract feature importances: %s", e)
        return None
