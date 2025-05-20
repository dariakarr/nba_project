def app():
    import pandas as pd
    import streamlit as st
    import altair as alt
    from prophet import Prophet

    @st.cache_data
    def load_data():
        per_game = pd.read_csv("data/parsed_player_per_game_stats.csv")
        team_misc = pd.read_csv("data/parsed_team_misc_stats.csv")
        return per_game, team_misc

    per_game, team_misc = load_data()
    st.header("Прогнозирование с помощью Prophet")
    st.markdown(
        "Используется библиотека [Prophet](https://facebook.github.io/prophet/) для прогнозирования метрик игроков и команд на основе временных рядов."
    )

    entity = st.radio("Выберите тип сущности:", ["Игрок", "Команда"], key="fc_entity")
    years = sorted(per_game["Season_End_Year"].unique())
    start_year, end_year = st.select_slider(
        "Выберите диапазон сезонов:",
        options=years,
        value=(years[0], years[-1]),
        key="fc_year_slider",
    )
    periods = st.number_input(
        "Количество лет для прогноза:",
        min_value=1,
        max_value=10,
        value=3,
        key="fc_periods",
    )

    if entity == "Игрок":
        players = sorted(per_game["Player_Name_Stats"].unique())
        player = st.selectbox("Выберите игрока:", players, key="fc_player_select")
        stat = st.selectbox(
            "Выберите метрику для прогноза:",
            ["PTS", "TRB", "AST", "FG_Pct", "3P_Pct"],
            key="fc_stat",
        )

        df = per_game[
            (per_game["Player_Name_Stats"] == player)
            & (per_game["Season_End_Year"] >= start_year)
            & (per_game["Season_End_Year"] <= end_year)
        ][["Season_End_Year", stat]].copy()
        df = df.rename(columns={"Season_End_Year": "ds", stat: "y"})

        df["ds"] = pd.to_datetime(df["ds"].astype(str) + "-01-01")
        df["Season"] = df["ds"].dt.year.astype(str)

        st.subheader(f"{player} — {stat}: временной ряд и прогноз")

        actual = (
            alt.Chart(df)
            .mark_line(color="blue", point=True)
            .encode(
                x=alt.X("Season:O", title="Сезон"),
                y=alt.Y("y:Q", title=stat),
                tooltip=["Season", "y"],
            )
            .properties(width=700, height=300)
        )
        st.altair_chart(actual, use_container_width=True)

        if st.button("Построить прогноз", key="run_fc_player"):
            model = Prophet(interval_width=0.9)
            model.fit(df[["ds", "y"]])
            future = model.make_future_dataframe(periods=periods, freq="Y")
            forecast = model.predict(future)
            forecast["Season"] = forecast["ds"].dt.year.astype(str)
            hist_end = df["ds"].max()
            fc_future = forecast[forecast["ds"] > hist_end]

            band = (
                alt.Chart(fc_future)
                .mark_area(opacity=0.3)
                .encode(x="Season:O", y="yhat_lower:Q", y2="yhat_upper:Q")
            )
            pred_line = (
                alt.Chart(fc_future)
                .mark_line(color="red", point=True)
                .encode(x="Season:O", y="yhat:Q")
            )
            st.altair_chart(actual + band + pred_line, use_container_width=True)

    else:
        teams = sorted(team_misc["Tm_ID"].unique())
        team = st.selectbox("Выберите команду:", teams, key="fc_team_select")
        metric = st.selectbox(
            "Выберите метрику для прогноза:",
            ["SRS", "ORtg", "Pace", "eFG_Pct", "TOV_Pct"],
            key="fc_metric",
        )

        df = team_misc[
            (team_misc["Tm_ID"] == team)
            & (team_misc["Season_End_Year"] >= start_year)
            & (team_misc["Season_End_Year"] <= end_year)
        ][["Season_End_Year", metric]].copy()
        df = df.rename(columns={"Season_End_Year": "ds", metric: "y"})
        df["ds"] = pd.to_datetime(df["ds"].astype(str) + "-01-01")
        df["Season"] = df["ds"].dt.year.astype(str)

        st.subheader(f"{team} — {metric}: временной ряд и прогноз")
        actual = (
            alt.Chart(df)
            .mark_line(color="blue", point=True)
            .encode(
                x=alt.X("Season:O", title="Сезон"),
                y=alt.Y("y:Q", title=metric),
                tooltip=["Season", "y"],
            )
            .properties(width=700, height=300)
        )
        st.altair_chart(actual, use_container_width=True)

        if st.button("Построить прогноз", key="run_fc_team"):
            model = Prophet(interval_width=0.9)
            model.fit(df[["ds", "y"]])
            future = model.make_future_dataframe(periods=periods, freq="Y")
            forecast = model.predict(future)
            forecast["Season"] = forecast["ds"].dt.year.astype(str)
            hist_end = df["ds"].max()
            fc_future = forecast[forecast["ds"] > hist_end]

            band = (
                alt.Chart(fc_future)
                .mark_area(opacity=0.3)
                .encode(x="Season:O", y="yhat_lower:Q", y2="yhat_upper:Q")
            )
            pred_line = (
                alt.Chart(fc_future)
                .mark_line(color="red", point=True)
                .encode(x="Season:O", y="yhat:Q")
            )
            st.altair_chart(actual + band + pred_line, use_container_width=True)
