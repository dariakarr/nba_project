def app():
    import pandas as pd
    import streamlit as st
    import altair as alt

    @st.cache_data
    def load_data():
        player_totals = pd.read_csv("data/nba_player_totals_2000-2024.csv")
        team_standings = pd.read_csv("data/nba_team_standings_2000-2024.csv")
        return player_totals, team_standings

    player_totals, team_standings = load_data()
    st.header("Топ-N игроков / команд по метрике")

    player_metric_desc = {
        "PTS": "Всего набранных очков",
        "TRB": "Всего подборов",
        "AST": "Всего передач",
        "STL": "Всего перехватов",
        "BLK": "Всего блок-шотов",
        "TOV": "Всего потерь",
        "FG": "Заброшено бросков с игры",
        "FGA": "Совершено бросков с игры",
        "FG%": "Процент попаданий с игры",
        "3P": "Заброшено трехочковых",
        "3PA": "Совершено попыток трехочковых",
        "3P%": "Процент попаданий трехочковых",
        "FT": "Заброшено штрафных",
        "FTA": "Совершено попыток штрафных",
        "FT%": "Процент попаданий штрафных",
        "eFG%": "Эффективный процент попаданий с игры",
    }
    team_metric_desc = {
        "W": "Всего побед",
        "L": "Всего поражений",
        "W/L%": "Процент побед",
        "PS/G": "Очков за игру",
        "PA/G": "Пропущено очков за игру",
        "SRS": "Простая рейтинговая система (атака - защита + сила расписания)",
        "GB": "Отставание от первого места (в играх)",
    }

    entity = st.radio("Выберите тип:", ["Игрок", "Команда"], key="topn_entity")
    years = sorted(player_totals["SeasonEndYear"].unique())
    start_year, end_year = st.select_slider(
        "Выберите сезон:",
        options=years,
        value=(years[0], years[-1]),
        key="topn_entity_year_slider",
    )
    N = st.slider(
        "Выберите N (количество записей):",
        min_value=1,
        max_value=20,
        value=5,
        key="topn_entity_slider",
    )

    if entity == "Игрок":
        metric = st.selectbox(
            "Выберите метрику:",
            list(player_metric_desc.keys()),
            key="topn_player_metric",
        )
        st.markdown(f"**Описание метрики:** {player_metric_desc[metric]}")

        df = player_totals[
            (player_totals["SeasonEndYear"] >= start_year)
            & (player_totals["SeasonEndYear"] <= end_year)
        ]
        agg = "mean" if metric.endswith("%") else "sum"
        df_group = df.groupby("Player")[metric].agg(agg).reset_index()
        df_group = df_group.sort_values(by=metric, ascending=False).head(N)

        st.subheader(f"Топ {N} игроков по метрике {metric} ({start_year}-{end_year})")
        st.dataframe(df_group)
        st.bar_chart(df_group.set_index("Player")[metric])

        st.subheader(f"Распределение {metric} среди всех игроков")
        hist = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                alt.X(f"{metric}:Q", bin=True, title=metric),
                alt.Y("count()", title="Количество"),
            )
            .properties(width=700, height=300)
        )
        st.altair_chart(hist, use_container_width=True)

        st.subheader(f"Тренды по сезонам для топ-{N} игроков ({metric})")
        df_trend = df[df["Player"].isin(df_group["Player"])]
        df_trend = (
            df_trend.groupby(["SeasonEndYear", "Player"])[metric].agg(agg).reset_index()
        )
        pivot = df_trend.pivot(index="SeasonEndYear", columns="Player", values=metric)
        st.line_chart(pivot)

        st.subheader("Среднее за игру для топ-игроков")
        df_games = df.groupby("Player")["G"].sum().reset_index()
        df_metric = df.groupby("Player")[metric].agg(agg).reset_index()
        df_pg_metric = pd.merge(df_metric, df_games, on="Player")
        df_pg_metric["Per_Game"] = df_pg_metric[metric] / df_pg_metric["G"]
        df_pg_metric = df_pg_metric[df_pg_metric["Player"].isin(df_group["Player"])]
        st.bar_chart(df_pg_metric.set_index("Player")["Per_Game"])

        st.subheader("Распределение метрики по сезонам (ящик с усами)")
        box = (
            alt.Chart(df)
            .mark_boxplot()
            .encode(x="SeasonEndYear:O", y=f"{metric}:Q")
            .properties(width=700, height=300)
        )
        st.altair_chart(box, use_container_width=True)

        st.subheader("Суммарный вклад топ-игроков")
        df_group["Pct"] = df_group[metric] / df_group[metric].sum()
        df_group = df_group.sort_values(by="Pct", ascending=False)
        df_group["Cumulative"] = df_group["Pct"].cumsum()
        cum_line = (
            alt.Chart(df_group)
            .mark_line(point=True)
            .encode(
                x=alt.X("Player:N", sort=None),
                y=alt.Y("Cumulative:Q", title="Накопительный %"),
            )
        )
        cum_bar = (
            alt.Chart(df_group)
            .mark_bar()
            .encode(
                x=alt.X("Player:N", sort=None), y=alt.Y(f"{metric}:Q", title=metric)
            )
        )
        st.altair_chart(cum_bar + cum_line, use_container_width=True)

    else:
        metric = st.selectbox(
            "Выберите метрику:", list(team_metric_desc.keys()), key="topn_team_metric"
        )
        st.markdown(f"**Описание метрики:** {team_metric_desc[metric]}")

        df = team_standings[
            (team_standings["SeasonEndYear"] >= start_year)
            & (team_standings["SeasonEndYear"] <= end_year)
        ]
        agg = "sum" if metric in ["W", "L", "GB"] else "mean"
        df_group = df.groupby("Team")[metric].agg(agg).reset_index()
        df_group = df_group.sort_values(by=metric, ascending=False).head(N)

        st.subheader(f"Топ {N} команд по метрике {metric} ({start_year}-{end_year})")
        st.dataframe(df_group)
        st.bar_chart(df_group.set_index("Team")[metric])

        st.subheader(f"Распределение {metric} среди всех команд")
        hist = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                alt.X(f"{metric}:Q", bin=True, title=metric),
                alt.Y("count()", title="Количество"),
            )
            .properties(width=700, height=300)
        )
        st.altair_chart(hist, use_container_width=True)

        st.subheader(f"Тренды по сезонам для топ-{N} команд ({metric})")
        df_trend = df[df["Team"].isin(df_group["Team"])]
        df_trend = (
            df_trend.groupby(["SeasonEndYear", "Team"])[metric].agg(agg).reset_index()
        )
        pivot = df_trend.pivot(index="SeasonEndYear", columns="Team", values=metric)
        st.line_chart(pivot)

        st.subheader("Распределение метрики по сезонам (ящик с усами)")
        box = (
            alt.Chart(df)
            .mark_boxplot()
            .encode(x="SeasonEndYear:O", y=f"{metric}:Q")
            .properties(width=700, height=300)
        )
        st.altair_chart(box, use_container_width=True)

        st.subheader("Суммарный вклад топ-команд")
        df_group["Pct"] = df_group[metric] / df_group[metric].sum()
        df_group = df_group.sort_values(by="Pct", ascending=False)
        df_group["Cumulative"] = df_group["Pct"].cumsum()
        cum_line = (
            alt.Chart(df_group)
            .mark_line(point=True)
            .encode(
                x=alt.X("Team:N", sort=None),
                y=alt.Y("Cumulative:Q", title="Накопительный %"),
            )
        )
        cum_bar = (
            alt.Chart(df_group)
            .mark_bar()
            .encode(x=alt.X("Team:N", sort=None), y=alt.Y(f"{metric}:Q", title=metric))
        )
        st.altair_chart(cum_bar + cum_line, use_container_width=True)

        st.subheader("Тепловая карта метрики по сезонам и командам")
        df_heat = df.groupby(["SeasonEndYear", "Team"])[metric].agg(agg).reset_index()
        heat = (
            alt.Chart(df_heat)
            .mark_rect()
            .encode(
                x="SeasonEndYear:O",
                y="Team:N",
                color=alt.Color(f"{metric}:Q", scale=alt.Scale(scheme="greens")),
            )
            .properties(width=700, height=400)
        )
        st.altair_chart(heat, use_container_width=True)
