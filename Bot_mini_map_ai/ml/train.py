import os
import pickle
import logging
import pandas as pd
import xgboost as xgb
import optuna
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from Bot_mini_map_ai.config.settings import settings

logger = logging.getLogger(__name__)


def cleaning_csv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    garbage = ['url', 'date']
    df = df.drop(columns=[cols for cols in garbage if cols in df.columns], errors='ignore')

    categorial_cols = ['floor', 'metro', 'time_to_metro']
    for cols in categorial_cols:
        if cols in df.columns:
            df[cols] = df[cols].astype('category')

    return df


def train_model(n_trials: int = 20) -> dict:
    csv_path = settings.CSV_PATH
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Файл данных не найден: {csv_path}")

    df_raw = pd.read_csv(csv_path)
    df_cleaned = cleaning_csv(df_raw)

    if "price" not in df_cleaned.columns:
        raise ValueError("В датасете нет целевой колонки 'price'")

    X = df_cleaned.drop("price", axis=1)
    y = df_cleaned["price"]
    features = list(X.columns)

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

    def objective(trial):
        parameters = {
            'n_estimators': trial.suggest_int('n_estimators', 100, 1500),
            'max_depth': trial.suggest_int('max_depth', 3, 9),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.15),
            'subsample': trial.suggest_float('subsample', 0.5, 0.9),
            'random_state': 42,
            'tree_method': 'hist',
            'enable_categorical': True,
        }
        model = xgb.XGBRegressor(**parameters)
        kf = KFold(n_splits=3, shuffle=True, random_state=42)
        scores = cross_val_score(model, X_train, y_train, cv=kf,
                                 scoring="neg_mean_absolute_error", n_jobs=-1)
        
        trial.set_user_attr("mae", -scores.mean())
        return scores.mean()

    logger.info("Запуск Optuna (%d итераций)", n_trials)
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=n_trials)

    logger.info("Лучшие параметры: %s", study.best_params)
    final_model = xgb.XGBRegressor(
        **study.best_params,
        enable_categorical=True,
        tree_method='hist'
    )
    final_model.fit(X_train, y_train)

    predictions = final_model.predict(X_val)
    mae = mean_absolute_error(y_val, predictions)
    mse = mean_squared_error(y_val, predictions)
    r2 = r2_score(y_val, predictions)

    logger.info("── РЕЗУЛЬТАТЫ ── MAE: %s | R²: %.4f", f"{mae:,.0f}", r2)

    os.makedirs(os.path.dirname(settings.MODEL_PATH), exist_ok=True)
    with open(settings.MODEL_PATH, 'wb') as f:
        pickle.dump({'model': final_model, 'features': features}, f)
    logger.info("Модель сохранена → %s", settings.MODEL_PATH)

    run_id = _log_to_mlflow(
        final_model=final_model,
        best_params=study.best_params,
        n_trials=n_trials,
        dataset_size=len(df_raw),
        features=features,
        mae=mae, mse=mse, r2=r2,
    )

    from Bot_mini_map_ai.ml.predict import invalidate_cache
    invalidate_cache()

    return {
        "mae": float(mae),
        "mse": float(mse),
        "r2_score": float(r2),
        "best_params": study.best_params,
        "mlflow_run_id": run_id,
    }


def _log_to_mlflow(
    final_model: xgb.XGBRegressor,
    best_params: dict,
    n_trials: int,
    dataset_size: int,
    features: list,
    mae: float,
    mse: float,
    r2: float,
) -> str:
    try:
        import mlflow
        import mlflow.xgboost

        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)

        with mlflow.start_run(run_name=f"xgboost_optuna_{n_trials}trials"):
            mlflow.log_params({
                **best_params,
                "n_optuna_trials": n_trials,
                "dataset_size": dataset_size,
                "test_size": 0.2,
                "features": str(features),
            })
            mlflow.log_metric("mae", mae)
            mlflow.log_metric("mse", mse)
            mlflow.log_metric("r2_score", r2)
            
            # Dynamically construct input_example with all features to prevent schema mismatches
            example = {f: 0 for f in features}
            if "area" in example: example["area"] = 50.0
            if "floor" in example: example["floor"] = 5
            if "time_to_metro" in example: example["time_to_metro"] = 10
            
            mlflow.xgboost.log_model(
                xgb_model=final_model,
                artifact_path="xgboost_model",
                input_example=example,
            )

            run_id = mlflow.active_run().info.run_id
            logger.info(
                "MLflow ✓ | run_id: %s | experiment: %s",
                run_id,
                settings.MLFLOW_EXPERIMENT_NAME,
            )
            return run_id

    except Exception as e:
        return ""
