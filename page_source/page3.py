def app():
    import pandas as pd
    import streamlit as st
    import altair as alt

    @st.cache_data
    def load_data():
        per_game = pd.read_csv("data/parsed_player_per_game_stats.csv")
        totals = pd.read_csv("data/parsed_player_totals_stats.csv")
        team_misc = pd.read_csv("data/parsed_team_misc_stats.csv")
        return per_game, totals, team_misc

    per_game, totals, team_misc = load_data()

    st.header("Графики по сезонам")

    entity = st.radio("Выберите тип сущности:", ["Игрок", "Команда"], key="ts_entity")
    years = sorted(per_game["Season_End_Year"].unique())
    start_year, end_year = st.select_slider(
        "Выберите диапазон сезонов:",
        options=years,
        value=(years[0], years[-1]),
        key="ts_year_slider",
    )
    normalize = st.checkbox(
        "Нормализовать метрики (база = 100 в стартовом сезоне)", key="ts_normalize"
    )

    if entity == "Игрок":
        players = sorted(per_game["Player_Name_Stats"].unique())
        player = st.selectbox("Выберите игрока:", players, key="ts_player_select")
        stats_options = ["PTS", "TRB", "AST", "FG_Pct", "3P_Pct", "FT_Pct"]
        stats = st.multiselect(
            "Выберите метрики для графика:",
            stats_options,
            default=["PTS", "TRB", "AST"],
            key="ts_stats_multi",
        )

        df = per_game[
            (per_game["Player_Name_Stats"] == player)
            & (per_game["Season_End_Year"] >= start_year)
            & (per_game["Season_End_Year"] <= end_year)
        ].copy()
        if "TS_Pct" in stats:
            df["TS_Pct"] = df["PTS"] / (2 * (df["FGA"] + 0.44 * df["FTA"]))
            if "TS_Pct" not in stats_options:
                stats.append("TS_Pct")

        df_plot = df[["Season_End_Year"] + stats].set_index("Season_End_Year")
        if normalize:
            if start_year in df_plot.index:
                base = df_plot.loc[start_year]
            else:
                base = df_plot.iloc[0]
            df_plot = df_plot.divide(base).multiply(100)

        df_reset = df_plot.reset_index()
        chart = (
            alt.Chart(df_reset)
            .transform_fold(stats, as_=["Метрика", "Значение"])
            .mark_line(point=True)
            .encode(
                x=alt.X("Season_End_Year:O", title="Сезон"),
                y=alt.Y(
                    "Значение:Q",
                    title=("Нормализованное значение" if normalize else "Значение"),
                ),
                color=alt.Color("Метрика:N", title="Метрика"),
            )
            .properties(width=800, height=400)
        )
        st.altair_chart(chart, use_container_width=True)

    else:
        teams = sorted(team_misc["Tm_ID"].unique())
        metric_options = ["SRS", "ORtg", "DRtg", "Pace", "eFG_Pct", "TOV_Pct"]

        if st.checkbox("Сравнить несколько команд", key="ts_compare"):
            teams_cmp = st.multiselect(
                "Выберите команды для сравнения:",
                teams,
                default=teams[:2],
                key="ts_teams_cmp",
            )
            metric_cmp = st.selectbox(
                "Выберите метрику для сравнения:", metric_options, key="ts_cmp_metric"
            )
            df_cmp = team_misc[
                (team_misc["Tm_ID"].isin(teams_cmp))
                & (team_misc["Season_End_Year"] >= start_year)
                & (team_misc["Season_End_Year"] <= end_year)
            ].copy()
            df_cmp_plot = df_cmp[["Season_End_Year", "Tm_ID", metric_cmp]]
            if normalize:
                pivot = df_cmp_plot.pivot(
                    index="Season_End_Year", columns="Tm_ID", values=metric_cmp
                )
                if start_year in pivot.index:
                    base = pivot.loc[start_year]
                else:
                    base = pivot.iloc[0]
                pivot = pivot.divide(base).multiply(100)
                df_cmp_plot = pivot.reset_index().melt(
                    "Season_End_Year", var_name="Tm_ID", value_name=metric_cmp
                )

            chart_cmp = (
                alt.Chart(df_cmp_plot)
                .mark_line(point=True)
                .encode(
                    x=alt.X("Season_End_Year:O", title="Сезон"),
                    y=alt.Y(
                        f"{metric_cmp}:Q",
                        title=("Нормализованная " if normalize else "") + metric_cmp,
                    ),
                    color=alt.Color("Tm_ID:N", title="Команда"),
                )
                .properties(width=800, height=400)
            )
            st.subheader("Сравнение команд")
            st.altair_chart(chart_cmp, use_container_width=True)

        team = st.selectbox("Выберите команду:", teams, key="ts_team_select")
        metrics = st.multiselect(
            "Выберите метрики для графика одной команды:",
            metric_options,
            default=["SRS", "ORtg"],
            key="ts_team_stats",
        )

        df = team_misc[
            (team_misc["Tm_ID"] == team)
            & (team_misc["Season_End_Year"] >= start_year)
            & (team_misc["Season_End_Year"] <= end_year)
        ].copy()
        df_plot = df[["Season_End_Year"] + metrics].set_index("Season_End_Year")
        if normalize:
            if start_year in df_plot.index:
                base = df_plot.loc[start_year]
            else:
                base = df_plot.iloc[0]
            df_plot = df_plot.divide(base).multiply(100)
        df_reset = df_plot.reset_index()
        chart = (
            alt.Chart(df_reset)
            .transform_fold(metrics, as_=["Метрика", "Значение"])
            .mark_line(point=True)
            .encode(
                x=alt.X("Season_End_Year:O", title="Сезон"),
                y=alt.Y(
                    "Значение:Q",
                    title=("Нормализованное значение" if normalize else "Значение"),
                ),
                color=alt.Color("Метрика:N", title="Метрика"),
            )
            .properties(width=800, height=400)
        )
        st.subheader(f"График по сезонам для команды {team}")
        st.altair_chart(chart, use_container_width=True)
