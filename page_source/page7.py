def app():
    import streamlit as st
    import pandas as pd
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    import altair as alt

    @st.cache_data
    def load_data():
        per_game = pd.read_csv("data/parsed_player_per_game_stats.csv")
        team_misc = pd.read_csv("data/parsed_team_misc_stats.csv")
        return per_game, team_misc

    per_game, team_misc = load_data()

    st.header("Кластеризация")
    st.markdown(
        "Был использован алгоритм KMeans для кластеризации игроков и команд на основе выбранных метрик."
    )

    entity = st.radio("Тип для кластеризации:", ["Игрок", "Команда"])
    n_clusters = st.slider(
        "Количество кластеров (K):", min_value=2, max_value=10, value=4
    )

    if entity == "Игрок":
        stats_opts = ["PTS", "TRB", "AST", "STL", "BLK"]
        stats = st.multiselect(
            "Выберите метрики для кластеризации:", stats_opts, default=stats_opts
        )
        df = per_game.groupby("Player_Name_Stats")[stats].mean().dropna()
        id_col = "Player_Name_Stats"
    else:
        stats_opts = ["SRS", "ORtg", "DRtg", "Pace"]
        stats = st.multiselect(
            "Выберите метрики для кластеризации:", stats_opts, default=stats_opts
        )
        df = team_misc.groupby("Tm_ID")[stats].mean().dropna()
        id_col = "Tm_ID"

    if df.empty:
        st.warning("Нет данных для кластеризации с выбранными метриками.")
        return

    scaler = StandardScaler()
    X = scaler.fit_transform(df)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42).fit(X)
    df["Cluster"] = kmeans.labels_

    st.markdown(f"**Кластеризация {entity.lower()} на {n_clusters} групп.**")

    centers = pd.DataFrame(
        scaler.inverse_transform(kmeans.cluster_centers_), columns=stats
    )
    centers["Cluster"] = centers.index
    st.subheader("Центроиды кластеров")
    st.dataframe(centers.style.background_gradient(cmap="Blues", subset=stats))

    st.subheader("Профили кластеров")
    cols = st.columns(n_clusters)
    for i, col in enumerate(cols):
        profile = centers[centers["Cluster"] == i][stats].T.reset_index()
        profile.columns = ["Метрика", "Значение"]
        chart = (
            alt.Chart(profile)
            .mark_bar()
            .encode(
                x=alt.X("Метрика:N", title=None),
                y=alt.Y("Значение:Q", title="Значение центроида"),
            )
            .properties(width=150, height=150, title=f"Кластер {i}")
        )
        col.altair_chart(chart, use_container_width=True)

    st.subheader("Назначение кластеров")
    cluster_choice = st.selectbox("Фильтр по кластеру:", sorted(df["Cluster"].unique()))
    df_display = df[df["Cluster"] == cluster_choice].copy()
    df_display.insert(0, id_col, df_display.index)
    st.dataframe(df_display.reset_index(drop=True))

    if entity == "Игрок":
        st.subheader(f"Средние тренды по сезонам для кластера {cluster_choice}")
        members = df[df["Cluster"] == cluster_choice].index.tolist()
        ts_df = per_game[per_game["Player_Name_Stats"].isin(members)]
        ts_summary = ts_df.groupby("Season_End_Year")[stats].mean().reset_index()
        ts_long = ts_summary.melt(
            "Season_End_Year", var_name="Метрика", value_name="Значение"
        )
        ts_chart = (
            alt.Chart(ts_long)
            .mark_line(point=True)
            .encode(
                x=alt.X("Season_End_Year:O", title="Сезон"),
                y=alt.Y("Значение:Q"),
                color=alt.Color("Метрика:N"),
            )
            .properties(width=700, height=300)
        )
        st.altair_chart(ts_chart, use_container_width=True)

    st.subheader("PCA-проекция кластеров")
    pca = PCA(n_components=2)
    coords = pca.fit_transform(X)
    loadings = pd.DataFrame(pca.components_, columns=stats, index=["PC1", "PC2"])
    pc1_dom = loadings.loc["PC1"].abs().idxmax()
    pc2_dom = loadings.loc["PC2"].abs().idxmax()
    df_vis = pd.DataFrame(coords, columns=["PC1", "PC2"], index=df.index)
    df_vis["Cluster"] = df["Cluster"].astype(str)

    scatter = (
        alt.Chart(df_vis.reset_index())
        .mark_circle(size=60)
        .encode(
            x=alt.X("PC1:Q", title=f"PC1 (доминирует: {pc1_dom})"),
            y=alt.Y("PC2:Q", title=f"PC2 (доминирует: {pc2_dom})"),
            color=alt.Color("Cluster:N", legend=alt.Legend(title="Кластер")),
            tooltip=[id_col, "Cluster"],
        )
        .properties(width=700, height=400)
    )
    st.altair_chart(scatter, use_container_width=True)
