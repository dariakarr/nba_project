# NBA Analytics Dashboard

## 1. Парсинг данных

Для сбора «сырых» данных использовался сайт [basketball-reference.com](https://www.basketball-reference.com/):

* **Страницы игроков** (`/players/{}/{player_id}.html`) для суммарной и per-game статистики.
* **Страницы команд** (`/teams/{team_id}/{season}.html`) для рейтинговой таблицы (Standings).
* **Boxscore страницы матчей** (`/boxscores/{Game_ID}.html`) для базовой и расширённой статистики игроков.
* **Four-Factors API-таблицы** через endpoint матчей, выдающий Pace, eFG%, TOV%, ORB%, FT/FGA, ORtg.

лежат скрипты в папке `parsers/`, результат сохраняется в CSV в папке `data/`.

## 2. Описание приложения

Веб‑приложение на [Streamlit](https://streamlit.io/) состоит из нескольких вкладок:

| Вкладка                         | Описание                                                                                                        | Модель/методика                                                                                                          |
| ------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **1. Player/Team Stats**        | По запросу выводит сезонную статистику для выбранного игрока или команды.                                       | —                                                                                                                        |
| **2. Top‑N Rankings**           | Топ‑N игроков или команд по заданному параметру за период. Вкл. описания метрик и распределения.                | —                                                                                                                        |
| **3. Time Series Plots**        | Построение динамики (time-series) по выбранным метрикам для игроков или команд, с нормализацией и сравнением.   | [Altair](https://altair-viz.github.io/) для визуализации.                                                                |
| **4. Match Outcome Prediction** | Прогноз результатов матчей. Классификатор (RandomForest) прогнозирует победу домашней команды.                  | [RandomForestClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html) |
| **5. Unsupervised Clustering**  | Кластеризация игроков или команд по статистическим профилям (K-Means), PCA‑визуализация.                        | [scikit‑learn KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html)                     |
| **6. Forecasting with Prophet** | Прогноз метрик (PTS, TRB, AST, ORtg и т.д.) с помощью библиотеки [Prophet](https://facebook.github.io/prophet). | [Prophet](https://facebook.github.io/prophet)                                                                            |
| **7. LSTM vs. Random Forest**   | Сравнение рекуррентной сети (LSTM) и RandomForestRegressor для прогноза сезонных показателей игроков.           | [Keras LSTM](https://keras.io/api/layers/recurrent_layers/lstm/), [RandomForestRegressor](https://scikit-learn.org/)     |

## 4. Как запустить приложение

1. Клонируйте репозиторий и перейдите в папку проекта:

   ```bash
   git clone <repo_url>
   cd NBA_PROJECT
   ```
2. Создайте виртуальное окружение и установите зависимости:

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # для Linux/Mac
   venv\Scripts\activate    # для Windows
   pip install -r requirements.txt
   ```
3. Запустите Streamlit:

   ```bash
   streamlit run main.py
   ```
4. Перейдите в браузере по адресу `http://localhost:8501`.