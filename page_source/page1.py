def app():
    import pandas as pd
    import streamlit as st
    import altair as alt

    @st.cache_data
    def load_data():
        player_totals = pd.read_csv("data/nba_player_totals_2000-2024.csv")
        team_standings = pd.read_csv("data/nba_team_standings_2000-2024.csv")
        per_game = pd.read_csv("data/parsed_player_per_game_stats.csv")
        totals = pd.read_csv("data/parsed_player_totals_stats.csv")
        team_misc = pd.read_csv("data/parsed_team_misc_stats.csv")
        team_opp = pd.read_csv("data/parsed_team_opponent_stats.csv")
        salaries = pd.read_csv("data/parsed_team_salaries.csv")
        return (
            player_totals,
            team_standings,
            per_game,
            totals,
            team_misc,
            team_opp,
            salaries,
        )

    (player_totals, team_standings, per_game, totals, team_misc, team_opp, salaries) = (
        load_data()
    )

    st.header("Статистика игрока и команды")

    entity = st.radio("Выберите тип", ["Игрок", "Команда"])

    years = sorted(player_totals["SeasonEndYear"].unique())
    start_year, end_year = st.select_slider(
        "Выберите сезон:", options=years, value=(years[0], years[-1])
    )

    if entity == "Игрок":
        players = sorted(player_totals["Player"].unique())
        player = st.selectbox("Select Player:", players)

        df_tot = player_totals[
            (player_totals["Player"] == player)
            & (player_totals["SeasonEndYear"] >= start_year)
            & (player_totals["SeasonEndYear"] <= end_year)
        ]
        df_pg = per_game[
            (per_game["Player_Name_Stats"] == player)
            & (per_game["Season_End_Year"] >= start_year)
            & (per_game["Season_End_Year"] <= end_year)
        ]
        df_sal = salaries[salaries["Player_In_Salary_Table"] == player]

        st.subheader(f"Результаты для {player} ({start_year}-{end_year})")
        if df_tot.empty:
            st.warning("No aggregate data found.")
        else:
            st.dataframe(df_tot)

        st.subheader("Игровые тренды (PTS, TRB, AST)")
        if df_pg.empty:
            st.warning("Данные по играм отсутствуют.")
        else:
            df_plot = df_pg.set_index("Season_End_Year")[["PTS", "TRB", "AST"]]
            st.line_chart(df_plot)

        st.subheader("Процентные показатели по броскам")
        if df_pg.empty:
            st.warning("Данные по играм отсутствуют.")
        else:
            df_shoot = df_pg.set_index("Season_End_Year")[
                ["FG_Pct", "3P_Pct", "FT_Pct"]
            ]
            st.area_chart(df_shoot)

        st.subheader("Процент эффективного броска (TS%)")
        if df_pg.empty:
            st.warning("Нет данных по играм для расчета TS%.")
        else:
            df_ts = df_pg.copy()
            df_ts["TS_Pct"] = df_ts["PTS"] / (2 * (df_ts["FGA"] + 0.44 * df_ts["FTA"]))
            ts_plot = df_ts.set_index("Season_End_Year")["TS_Pct"]
            st.line_chart(ts_plot)

        st.subheader("Главное по сезону")
        if not df_tot.empty:
            best_pts = df_tot.loc[df_tot["PTS"].idxmax()]
            best_trb = df_tot.loc[df_tot["TRB"].idxmax()]
            best_ast = df_tot.loc[df_tot["AST"].idxmax()]
            best_td = (
                df_tot.loc[df_tot["Trp-Dbl"].idxmax()] if "Trp-Dbl" in df_tot else None
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Max PTS in a Season", int(best_pts["PTS"]), delta=None)
            c2.metric("Max TRB in a Season", int(best_trb["TRB"]), delta=None)
            c3.metric("Max AST in a Season", int(best_ast["AST"]), delta=None)
            if best_td is not None:
                c4.metric("Max Triple-Doubles", int(best_td["Trp-Dbl"]), delta=None)

        st.subheader("Тренды по Triple-Doubles")
        if df_tot.empty or "Trp-Dbl" not in df_tot:
            st.info("Не достаточно данных для отображения.")
        else:
            df_td = df_tot.set_index("SeasonEndYear")["Trp-Dbl"]
            st.bar_chart(df_td)

        st.subheader("Заработная плата игрока")
        if df_sal.empty:
            st.info("Нет данных по зарплате игрока.")
        else:
            df_sal_plot = (
                df_sal[["Season_End_Year", "Salary_Value"]]
                .dropna()
                .set_index("Season_End_Year")
            )
            st.line_chart(df_sal_plot)

        st.subheader("PTS vs AST Scatter")
        if df_pg.empty:
            st.warning("Нет данных по играм для отображения.")
        else:
            scatter = df_pg[["Season_End_Year", "PTS", "AST"]].rename(
                columns={"Season_End_Year": "Season"}
            )
            st.altair_chart(
                alt.Chart(scatter)
                .mark_circle(size=60)
                .encode(
                    x="PTS", y="AST", color="Season:N", tooltip=["Season", "PTS", "AST"]
                )
                .interactive(),
                use_container_width=True,
            )

    else:
        teams = sorted(team_standings["Team"].unique())
        team = st.selectbox("Select Team:", teams)

        df_stand = team_standings[
            (team_standings["Team"] == team)
            & (team_standings["SeasonEndYear"] >= start_year)
            & (team_standings["SeasonEndYear"] <= end_year)
        ]
        tm_id = df_stand["Tm_ID"].iloc[0] if not df_stand.empty else None
        df_misc = team_misc[
            (team_misc["Tm_ID"] == tm_id)
            & (team_misc["Season_End_Year"] >= start_year)
            & (team_misc["Season_End_Year"] <= end_year)
        ]
        df_opp = team_opp[
            (team_opp["Tm_ID"] == tm_id)
            & (team_opp["Season_End_Year"] >= start_year)
            & (team_opp["Season_End_Year"] <= end_year)
            & (team_opp["Stat_Type"] == "Team_Per_Game")
        ]

        st.subheader(f"Показатели для {team} ({start_year}-{end_year})")
        if df_stand.empty:
            st.warning("No standings data found.")
        else:
            st.dataframe(df_stand)

        st.subheader("Тренды по команде")
        if df_misc.empty:
            st.warning("No advanced metrics found.")
        else:
            adv = df_misc.set_index("Season_End_Year")[["SRS", "ORtg", "DRtg", "Pace"]]
            st.line_chart(adv)

        st.subheader("W/L (Победы/Поражения)")
        if df_stand.empty:
            st.warning("No data for W/L chart.")
        else:
            df_wl = df_stand.set_index("SeasonEndYear")[["W", "L"]]
            st.bar_chart(df_wl)

        st.subheader("Очки за игру (PF/PA)")
        if df_stand.empty:
            st.warning("No data for PF/PA chart.")
        else:
            df_pts = df_stand.set_index("SeasonEndYear")[["PS/G", "PA/G"]]
            st.area_chart(df_pts)

        st.subheader("Turnover & Shooting Rates")
        if df_misc.empty:
            st.info("Advanced team shooting/turnover data not available.")
        else:
            df_rates = df_misc.set_index("Season_End_Year")[
                ["eFG_Pct", "3PAr", "TOV_Pct"]
            ]
            st.area_chart(df_rates)

        st.subheader("Strength of Schedule")
        if df_misc.empty or "SOS" not in df_misc:
            st.info("SOS data not available.")
        else:
            sos = df_misc.set_index("Season_End_Year")["SOS"]
            st.line_chart(sos)

        st.subheader("Посещаемость")
        if df_misc.empty:
            st.info("Attendance data not available.")
        else:
            df_att = df_misc.copy()
            df_att["Attendance"] = df_att["Attendance"].str.replace(",", "").astype(int)
            df_att_plot = df_att.set_index("Season_End_Year")["Attendance"]
            st.line_chart(df_att_plot)
