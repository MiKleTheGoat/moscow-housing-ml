import pickle
import logging
import pandas as pd
from Bot_mini_map_ai.config.settings import settings

logger = logging.getLogger(__name__)

_model_cache = None


def load_model():
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    try:
        with open(settings.MODEL_PATH, "rb") as f:
            data = pickle.load(f)
            _model_cache = data
        logger.info("Модель успешно загружена из %s", settings.MODEL_PATH)
        return _model_cache
    except FileNotFoundError:
        logger.warning("Файл модели не найден по пути %s. Сначала обучите модель.", settings.MODEL_PATH)
        return None
    except Exception:
        return None


def predict_price(features: dict) -> float:
    data = load_model()
    if data is None:

        logger.warning("Используем базовую эвристику для прогноза цены")
        return features.get("area", 0) * 300000.0

    model = data["model"]
    model_features = data["features"]
    df = pd.DataFrame([features])

    categorial_cols = ['floor', 'metro', 'time_to_metro']
    for col in categorial_cols:
        if col in df.columns:
            df[col] = df[col].astype('category')

    for col in model_features:
        if col not in df.columns:
            df[col] = 0

    X = df[model_features]

    try:
        predicted = model.predict(X)
        return float(predicted[0])
    except Exception as e:
        logger.error("Ошибка инференса: %s", e)
        return features.get("area", 0) * 300000.0

def invalidate_cache():
    global _model_cache
    _model_cache = None
