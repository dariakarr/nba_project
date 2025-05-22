def app():
    import pandas as pd
    import streamlit as st
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
    import altair as alt

    st.header("4. Прогноз исхода матча 📈")
    st.markdown(
        "Мы обучаем Random Forest на показателях 'Four Factors' команд, чтобы предсказать победу хозяев. "
        "Признаки — это разница (хозяева - гости) по следующим метрикам: Pace, eFG%, TOV%, ORB%, FT/FGA и ORtg."
    )

    st.sidebar.header("Гиперпараметры")
    st.sidebar.markdown("Для предсказания исхода матча")
    max_depth = st.sidebar.slider("Максимальная глубина дерева:", 1, 20, 5)
    feature_opts = ["Pace", "eFG_Pct", "TOV_Pct", "ORB_Pct", "FT_per_FGA"]
    selected = st.sidebar.multiselect(
        "Выберите признаки:", feature_opts, default=feature_opts
    )
    n_estimators = st.sidebar.number_input("Количество деревьев:", 10, 200, 100, 10)

    schedule = pd.read_csv("data/games_schedule.csv")
    ff = pd.read_csv("data/game_four_factors.csv")
    ff_home = ff.rename(columns={c: f"home_{c}" for c in feature_opts})
    ff_away = ff.rename(columns={c: f"away_{c}" for c in feature_opts})
    df = schedule.merge(
        ff_home[["Game_ID", "Team_ID"] + [f"home_{c}" for c in feature_opts]],
        left_on=["Game_ID", "Home_Team_ID"],
        right_on=["Game_ID", "Team_ID"],
    ).drop(columns=["Team_ID"])
    df = df.merge(
        ff_away[["Game_ID", "Team_ID"] + [f"away_{c}" for c in feature_opts]],
        left_on=["Game_ID", "Visitor_Team_ID"],
        right_on=["Game_ID", "Team_ID"],
    ).drop(columns=["Team_ID"])

    for feat in feature_opts:
        df[f"{feat}_diff"] = df[f"home_{feat}"] - df[f"away_{feat}"]
    feats = [f + "_diff" for f in selected]

    train_mask = df["Season_End_Year"] <= 2022
    X_train = df.loc[train_mask, feats]
    y_train = df.loc[train_mask, "Home_Win"]
    X_test = df.loc[~train_mask, feats]
    y_test = df.loc[~train_mask, "Home_Win"]

    st.subheader("Распределение классов в обучающей выборке")
    train_counts = y_train.value_counts().reset_index()
    train_counts.columns = ["Home_Win", "Количество"]
    dist_chart = (
        alt.Chart(train_counts)
        .mark_bar()
        .encode(
            x=alt.X("Home_Win:O", title="Победа хозяев (0 = поражение, 1 = победа)"),
            y=alt.Y("Количество:Q", title="Количество игр"),
            color=alt.Color("Home_Win:O", legend=None),
        )
        .properties(width=300, height=200)
    )
    st.altair_chart(dist_chart)

    clf = RandomForestClassifier(
        n_estimators=int(n_estimators), max_depth=int(max_depth), random_state=42
    )
    clf.fit(X_train, y_train)
    y_train_pred = clf.predict(X_train)
    y_pred = clf.predict(X_test)
    train_acc = accuracy_score(y_train, y_train_pred)
    test_acc = accuracy_score(y_test, y_pred)
    cv_scores = cross_val_score(clf, X_train, y_train, cv=5)

    st.subheader("Результаты модели")
    st.write(f"Accuracy: **{train_acc:.2%}**")
    st.write(f"Accuracy (5-fold CV): {cv_scores.mean():.2%} ± {cv_scores.std():.2%}")
    st.write(f"Test accuracy (2023–24): **{test_acc:.2%}**")
    if train_acc - test_acc > 0.1:
        st.warning(
            "Большой разрыв между обучающей и тестовой точностью указывает на переобучение. "
            "Попробуйте уменьшить max_depth или сократить число признаков."
        )

    st.subheader("Confusion matrix (test)")
    cm = confusion_matrix(y_test, y_pred)
    cm_df = (
        pd.DataFrame(
            cm,
            index=["Факт: Поражение", "Факт: Победа"],
            columns=["Прогноз: Поражение", "Прогноз: Победа"],
        )
        .reset_index()
        .melt(id_vars="index")
    )
    cm_chart = (
        alt.Chart(cm_df)
        .mark_rect()
        .encode(x="variable:N", y="index:N", color="value:Q")
        .properties(width=300, height=200)
    )
    st.altair_chart(cm_chart)

    st.subheader("Отчет классификации (test)")
    report = classification_report(y_test, y_pred, output_dict=True)
    rpt_df = pd.DataFrame(report).transpose()
    st.dataframe(rpt_df)

    st.subheader("Важность признаков")
    imp = pd.DataFrame({"Признак": feats, "Важность": clf.feature_importances_})
    imp = imp.sort_values("Важность", ascending=False)
    imp_chart = (
        alt.Chart(imp)
        .mark_bar()
        .encode(x="Важность:Q", y=alt.Y("Признак:N", sort="-x"))
        .properties(width=400, height=250)
    )
    st.altair_chart(imp_chart)

    st.subheader("Симуляция матча")
    season = st.selectbox("Сезон:", sorted(df["Season_End_Year"].unique()))
    teams = sorted(df["Home_Team_ID"].unique())
    home = st.selectbox("Хозяева:", teams)
    away = st.selectbox("Гости:", teams)
    if st.button("Спрогнозировать победу хозяев"):
        hist = df[df["Season_End_Year"] == season]
        home_avg = hist[hist["Home_Team_ID"] == home][
            [f"home_{f}" for f in feature_opts]
        ].mean()
        away_avg = hist[hist["Visitor_Team_ID"] == away][
            [f"away_{f}" for f in feature_opts]
        ].mean()
        diff = (home_avg.values - away_avg.values).reshape(1, -1)
        prob = clf.predict_proba(diff)[0][1]
        st.write(f"Вероятность победы {home}: **{prob:.1%}**")

    st.markdown("---")
    st.subheader("Объяснение признаков")
    st.markdown("- Pace_diff: владений за игру (хозяева минус гости)")
    st.markdown("- eFG_Pct_diff: разница в эффективном % попаданий")
    st.markdown("- TOV_Pct_diff: разница в частоте потерь")
    st.markdown("- ORB_Pct_diff: разница в проценте подборов в нападении")
    st.markdown("- FT_per_FGA_diff: разница штрафных на бросок с игры")
    st.markdown("- ORtg_diff: разница в атакующем рейтинге (очки на 100 владений)")
