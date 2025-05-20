def app():
    import streamlit as st
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_squared_error
    from sklearn.preprocessing import MinMaxScaler
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense
    from tensorflow.keras.callbacks import EarlyStopping
    import matplotlib.pyplot as plt

    st.header("9. Прогнозирование временных рядов: LSTM против Random Forest")
    st.markdown(
        "Сравнение рекуррентных нейросетей (LSTM) и регрессора Random Forest "
        "для прогнозирования сезонной статистики игроков."
    )
    st.sidebar.header("Гиперпараметры")
    st.sidebar.markdown("Для сравнения моделей")

    rf_trees = st.sidebar.number_input(
        "Random Forest: количество деревьев",
        min_value=10,
        max_value=500,
        value=100,
        step=10,
    )

    lstm_units = st.sidebar.slider(
        "LSTM: количество нейронов", min_value=10, max_value=200, value=50
    )
    lstm_epochs = st.sidebar.slider(
        "Количество эпох", min_value=10, max_value=500, value=200, step=10
    )
    batch_size = st.sidebar.slider("Размер батча", min_value=1, max_value=32, value=1)
    patience = st.sidebar.slider(
        "Ранняя остановка (patience)", min_value=1, max_value=20, value=5
    )
    optimizer = st.sidebar.selectbox("Оптимизатор", ["adam", "rmsprop", "sgd"])

    df_totals = pd.read_csv("data/parsed_player_totals_stats.csv")
    players = sorted(df_totals["Player_Name_Stats"].unique())
    player = st.selectbox("Выберите игрока", players)
    stats = ["PTS", "TRB", "AST", "FG_Pct", "eFG_Pct"]
    stat = st.selectbox("Выберите метрику для прогноза", stats)
    lags = st.slider(
        "Количество лагов (сезонов) в качестве признаков",
        min_value=1,
        max_value=5,
        value=3,
    )

    series_df = df_totals[df_totals["Player_Name_Stats"] == player][
        ["Season_End_Year", stat]
    ]
    series_df = series_df.sort_values("Season_End_Year").dropna()
    values = series_df[stat].values

    min_required = lags + 2
    if len(values) < min_required:
        st.warning(
            f"Недостаточно данных для {player}: нужно минимум {min_required} сезонов, доступно {len(values)}."
        )
        return

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(values.reshape(-1, 1))

    X, y = [], []
    for i in range(lags, len(scaled)):
        X.append(scaled[i - lags : i, 0])
        y.append(scaled[i, 0])
    X = np.array(X)
    y = np.array(y)

    split = len(X) - 2
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    if X_train.size == 0 or X_test.size == 0:
        st.warning(
            "Недостаточно данных после разбиения. Попробуйте уменьшить число лагов или выбрать другого игрока."
        )
        return

    rf = RandomForestRegressor(n_estimators=int(rf_trees), random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_mse = mean_squared_error(y_test, rf_pred)

    X_train_l = X_train.reshape((X_train.shape[0], X_train.shape[1], 1))
    X_test_l = X_test.reshape((X_test.shape[0], X_test.shape[1], 1))
    model = Sequential([LSTM(int(lstm_units), input_shape=(lags, 1)), Dense(1)])
    model.compile(optimizer=optimizer, loss="mse")
    early_stop = EarlyStopping(
        monitor="loss", patience=int(patience), restore_best_weights=True
    )
    model.fit(
        X_train_l,
        y_train,
        epochs=int(lstm_epochs),
        batch_size=int(batch_size),
        verbose=0,
        callbacks=[early_stop],
    )
    lstm_pred = model.predict(X_test_l).flatten()
    lstm_mse = mean_squared_error(y_test, lstm_pred)

    rf_inv = scaler.inverse_transform(rf_pred.reshape(-1, 1)).flatten()
    lstm_inv = scaler.inverse_transform(lstm_pred.reshape(-1, 1)).flatten()
    y_inv = scaler.inverse_transform(y_test.reshape(-1, 1)).flatten()
    seasons = series_df["Season_End_Year"].values
    test_seasons = seasons[-len(y_inv) :]

    st.subheader("Сравнение моделей (MSE)")
    st.write(f"Random Forest MSE: **{rf_mse:.3f}**, LSTM MSE: **{lstm_mse:.3f}**")

    fig, ax = plt.subplots()
    ax.plot(test_seasons, y_inv, marker="o", label="Факт")
    ax.plot(test_seasons, rf_inv, marker="x", label="Random Forest")
    ax.plot(test_seasons, lstm_inv, marker="s", label="LSTM")
    ax.set_xlabel("Сезон")
    ax.set_ylabel(stat)
    ax.set_title(f"{player} — {stat}: Фактическое vs Прогноз")
    ax.legend()
    st.pyplot(fig)
