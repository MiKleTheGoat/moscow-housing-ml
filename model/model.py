import pickle

import optuna
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import cross_val_score, KFold, train_test_split
from xgboost import XGBRegressor


class HousingPricePredictor:
    def __init__(self, model_path='xgb_model.pkl'):
        self.model_path = model_path
        self.model = xgb.XGBRegressor(
            n_estimators=1000,
            max_depth=6,
            learning_rate=0.07,
            tree_method="hist",
            subsample=0.7,
            random_state=42,
            enable_categorical=True,
        )
        self.features = None

    def cleaning_csv(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        garbage = ['url', 'date']
        df = df.drop(columns=[cols for cols in garbage if cols in df.columns], errors='ignore')

        categorial_cols = ['floor', 'metro', 'time_to_metro']
        for cols in categorial_cols:
            if cols in df.columns:
                df[cols] = df[cols].astype('category')

        return df

    def optimizing_training_model(self, csv_path: str, n_trials=60):
        self.df_raw = pd.read_csv(csv_path)
        df_cleaned = self.cleaning_csv(self.df_raw)

        X = df_cleaned.drop("price", axis=1)
        y = df_cleaned["price"]
        self.features = list(X.columns)

        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

        def objective(trial):
            parameters = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 2000),
                'max_depth': trial.suggest_int('max_depth', 1, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.10),
                'subsample': trial.suggest_float('subsample', 0.5, 0.9),
                'random_state': 42,
                'tree_method': 'hist',
                'enable_categorical': True,
            }
            model = xgb.XGBRegressor(**parameters)
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            scores = cross_val_score(model, X_train, y_train, cv=kf,
                                     scoring="neg_mean_absolute_error", n_jobs=-1)

            return scores.mean()

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials)

        self.model = XGBRegressor(**study.best_params,
                             enable_categorical=True,
                             tree_method='hist', )
        self.model.fit(X_train, y_train)

        predictions = self.model.predict(X_val)
        print(" --- РЕЗУЛЬТАТЫ НА ВАЛИДАЦИИ ---")
        print(f"MAE: {mean_absolute_error(y_val, predictions):,.0f} руб.")
        print(f"MSE: {mean_squared_error(y_val, predictions):,.0f}")
        print(f"R2 Score: {r2_score(y_val, predictions):.4f}")

        self.save_model()

    def save_model(self):
        with open(self.model_path, 'wb') as f:
            # Сохраняем модель и список фич для проверки при загрузке
            pickle.dump({'model': self.model, 'features': self.features}, f)
        print(f"Модель сохранена в {self.model_path}")

    def load_model(self):
        try:
            with open(self.model_path, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.features = data['features']
            print(f"Модель успешно загружена из {self.model_path}")
        except FileNotFoundError:
            print("Файл модели не найден. Сначала обучите модель.")

    def print_best_deals(self, csv_path='house_cian.csv', top_n=10):
        if self.model is None:
            self.load_model()

        df_processed = pd.read_csv(csv_path)
        df_cleaned = self.cleaning_csv(df_processed)

        for col in self.features:
            if col not in df_cleaned.columns:
                df_cleaned[col] = 0

        X_predict = df_cleaned[self.features]

        df_processed['predicted_price'] = self.model.predict(X_predict)
        df_processed['profit'] = df_cleaned['predicted_price'] - df_cleaned['price']

        beat_deals = df_processed.sort_values(by='profit', ascending=False).head(top_n)

        return beat_deals


HousingPricePredictor()
