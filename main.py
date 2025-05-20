import streamlit as st
from page_source.page1 import app as stats_app
from page_source.page2 import app as topn_app
from page_source.page3 import app as timeseries_app
from page_source.page7 import app as clustering_app
from page_source.page8 import app as forecast_app
from page_source.page4 import app as match_prediction_app
from page_source.page9 import app as sklearn_vs_tensorflow_app

st.set_page_config(page_title="NBA Analytics Dashboard", layout="wide")

st.title("🏀 NBA Analytics Dashboard")


tabs = st.tabs(
    [
        "Player/Team Stats",
        "Top-N Rankings",
        "Time Series Plots",
        "Forecast",
        "Clustering",
        "Match prediction",
        "Sklearn vs Tensorflow",
    ]
)

with tabs[0]:
    stats_app()


with tabs[1]:
    topn_app()

with tabs[2]:
    timeseries_app()

with tabs[3]:
    forecast_app()

with tabs[4]:
    clustering_app()

with tabs[5]:
    match_prediction_app()

with tabs[6]:
    sklearn_vs_tensorflow_app()
