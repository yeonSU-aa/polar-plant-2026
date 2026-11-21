import io

import numpy as np
import pandas as pd
import streamlit as st

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(layout="wide", page_title="극지식물 생육 차이 분석")
st.title("🌱 우리 학교 극지식물 개체별 생육 차이 분석")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
   font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------- 열 이름 표준화 ----------
def std_cols(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif k == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"
    df = df.rename(columns=rename)
    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(
                df[c].astype(str).str.replace(",", "").str.extract(r"(-?\d+\.?\d*)")[0],
                errors="coerce",
            )
            if num.notna().mean() >= 0.5:
                df[c] = num
    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]
    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = pd.to_datetime(parts[0], format="%Y%m%d") + pd.to_timedelta(parts[1].astype(int), unit="h")
        df["time"] = parsed
    return df

# ---------- 차트 도우미 ----------
def make_bar_grid(df, y_cols, titles):
    fig = make_subplots(rows=2, cols=2, subplot_titles=titles)
    for i, y in enumerate(y_cols):
        r = (i // 2) + 1
        c = (i % 2) + 1
        fig.add_trace(go.Bar(x=df["개체번호"], y=df[y], name=y), row=r, col=c)
    fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
    return fig

# ---------- 파일 업로드 및 데이터 로딩 ----------
st.sidebar.title("📊 데이터")
env_file = st.sidebar.file_uploader("환경 CSV", type="csv")
growth_file = st.sidebar.file_uploader("생육 결과 데이터", type="csv")

def get_school_name(file):
    if file is None:
        return "우리 학교"
    return file.name.replace(".csv", "").split("_")[0]

school_name = get_school_name(env_file) if env_file is not None else get_school_name(growth_file)

@st.cache_data
def load_csv(file):
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

with st.spinner("CSV 파일을 읽고 있어요..."):
    env_df = load_csv(env_file) if env_file is not None else pd.DataFrame()
    growth_df = load_csv(growth_file) if growth_file is not None else pd.DataFrame()

env_df = std_cols(env_df) if not env_df.empty else env_df
growth_df = std_cols(growth_df) if not growth_df.empty else growth_df

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

with st.sidebar:
    st.subheader("📋 생육 측정 항목 선택")
    growth_items = [c for c in growth_df.columns if c != "개체번호"]
    selected_items = st.multiselect("생육 측정 항목", options=growth_items, default=["잎 수", "지상부 길이"])

# ---------- Tab 1: 실험 개요 ----------
with tab1:
    try:
        st.subheader("📌 연구 배경 및 목적")
        st.write(
            "극지식물은 낮은 온도와 짧은 생육 기간에 적응한 식물로, "
            "같은 환경 안에서도 개체마다 생육 상태가 다를 수 있습니다. "
            "이 대시보드는 환경 데이터와 생육 측정 데이터를 함께 살펴보며 "
            "개체 간 생중량 차이와 잎 수·지상부 길이 같은 생육 요인과의 관계를 "
            "학생이 직접 찾아볼 수 있도록 만든 도구입니다."
        )

        st.markdown("### 🔍 데이터 요약")
        rows = []
        if not env_df.empty:
            period = "측정 기간 없음"
            if "time" in env_df.columns and env_df["time"].notna().any():
                period = f"{env_df['time'].min().strftime('%Y-%m-%d')} ~ {env_df['time'].max().strftime('%Y-%m-%d')}"
            rows.append(
                {
                    "구분": "환경 데이터",
                    "측정 기간": period,
                    "측정 항목 수": sum(c != "time" for c in env_df.columns),
                }
            )
        if not growth_df.empty:
            rows.append(
                {
                    "구분": "생육 결과",
                    "측정 기간": "측정일별 1회",
                    "측정 항목 수": sum(c != "개체번호" for c in growth_df.columns),
                }
            )
            rows.append(
                {
                    "구분": "총 개체 수",
                    "측정 기간": f"{growth_df['개체번호'].nunique()}개체",
                    "측정 항목 수": "-",
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch")

        st.markdown("### 🎯 핵심 지표")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if not growth_df.empty and "개체번호" in growth_df.columns:
                st.metric("총 개체 수", f"{growth_df['개체번호'].nunique()}")
            else:
                st.metric("총 개체 수", "업로드 대기")
        with col2:
            if "temperature" in env_df.columns and env_df["temperature"].notna().any():
                st.metric("평균 온도", f"{env_df['temperature'].mean():.2f} ℃")
            else:
                st.metric("평균 온도", "측정 없음")
        with col3:
            if "humidity" in env_df.columns and env_df["humidity"].notna().any():
                st.metric("평균 습도", f"{env_df['humidity'].mean():.2f} %")
            else:
                st.metric("평균 습도", "측정 없음")
        with col4:
            if (
                not growth_df.empty
                and "생중량" in growth_df.columns
                and growth_df["생중량"].notna().any()
            ):
                st.metric("평균 생중량", f"{growth_df['생중량'].mean():.2f} g")
            else:
                st.metric("평균 생중량", "측정 없음")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ---------- Tab 2: 환경 데이터 ----------
with tab2:
    try:
        if env_df.empty:
            st.info("환경 CSV를 업로드하면 일별 환경 변화 그래프를 볼 수 있어요.")
        else:
            st.markdown("### 🌡️ 환경 데이터 요약 (평균·최소·최대)")
            env_cols = [c for c in ["temperature", "humidity", "ph", "ec"] if c in env_df.columns]
            if env_cols:
                summary = env_df[env_cols].describe().loc[["mean", "min", "max"]]
                st.dataframe(summary, width="stretch")
            else:
                st.info("온도·습도·pH·EC 열이 없어요.")

            if "time" in env_df.columns and env_df["time"].notna().any() and env_cols:
                daily = env_df.copy()
                daily["date"] = daily["time"].dt.strftime("%Y-%m-%d")
                daily = daily.groupby("date", as_index=False)[env_cols].mean()

                fig = make_subplots(
                    rows=2, cols=1, subplot_titles=("일별 평균 온도", "일별 평균 습도"), shared_xaxes=True
                )
                if "temperature" in daily.columns:
                    fig.add_trace(
                        go.Scatter(x=daily["date"], y=daily["temperature"], mode="lines", name="온도"),
                        row=1,
                        col=1,
                    )
                if "humidity" in daily.columns:
                    fig.add_trace(
                        go.Scatter(x=daily["date"], y=daily["humidity"], mode="lines", name="습도"),
                        row=2,
                        col=1,
                    )
                fig.update_layout(height=420, font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                st.plotly_chart(fig, width="stretch")

                if "ph" in daily.columns and "ec" in daily.columns:
                    fig2 = make_subplots(rows=1, cols=1, subplot_titles=("일별 평균 pH·EC"))
                    fig2.add_trace(
                        go.Scatter(x=daily["date"], y=daily["ph"], mode="lines", name="pH"), row=1, col=1
                    )
                    fig2.add_trace(
                        go.Scatter(x=daily["date"], y=daily["ec"], mode="lines", name="EC"), row=1, col=1
                    )
                    fig2.update_layout(height=340, font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                    st.plotly_chart(fig2, width="stretch")
            else:
                st.info("시간 열이 없거나 날짜 형식을 읽을 수 없어요.")

            with st.expander("🌱 환경 데이터 원본 테이블 + CSV 다운로드"):
                st.dataframe(env_df, width="stretch")
                csv = env_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "환경 CSV 다운로드",
                    csv,
                    file_name=f"{school_name}_환경데이터.csv",
                    mime="text/csv",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

# ---------- Tab 3: 생육 결과 ----------
with tab3:
    try:
        if growth_df.empty:
            st.info("생육 결과 CSV를 업로드하면 개체별 생육 비교 그래프를 볼 수 있어요.")
        else:
            st.markdown("### 🥇 핵심 결과 카드")
            col1, col2, col3 = st.columns(3)
            with col1:
                if "생중량" in growth_df.columns and growth_df["생중량"].notna().any():
                    st.metric("평균 생중량", f"{growth_df['생중량'].mean():.2f} g")
                else:
                    st.metric("평균 생중량", "측정 없음")
            with col2:
                if "생중량" in growth_df.columns and growth_df["생중량"].notna().any():
                    max_idx = growth_df["생중량"].idxmax()
                    st.metric("최대 개체", f"{growth_df.loc[max_idx, '개체번호']}")
            with col3:
                if "생중량" in growth_df.columns and growth_df["생중량"].notna().any():
                    min_idx = growth_df["생중량"].idxmin()
                    st.metric("최소 개체", f"{growth_df.loc[min_idx, '개체번호']}")

            st.markdown("### 📈 개체별 생육 비교")
            y_cols = []
            if "생중량" in growth_df.columns:
                y_cols.append("생중량")
            if "잎 수" in growth_df.columns:
                y_cols.append("잎 수")
            if "지상부 길이" in growth_df.columns:
                y_cols.append("지상부 길이")
            if "지하부 길이" in growth_df.columns:
                y_cols.append("지하부 길이")

            if "개체번호" in growth_df.columns and y_cols:
                stats = growth_df.groupby("개체번호", as_index=False)[y_cols].mean()
                titles = ["평균 생중량 ⭐", "평균 잎 수", "평균 지상부 길이", "평균 지하부 길이"]
                if len(y_cols) < 4:
                    titles = titles[: len(y_cols)]
                fig = make_bar_grid(stats, y_cols, titles)
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("개체번호 또는 생육 측정 열이 없어요.")

            st.markdown("### 🎲 생중량 분포")
            if "생중량" in growth_df.columns:
                fig = px.violin(growth_df, y="생중량", box=True, title="생중량 분포")
                fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("생체중량 열이 없어요.")

            st.markdown("### 🔗 상관관계 분석 (산점도 + 추세선)")
            if "생중량" in growth_df.columns:
                if selected_items:
                    x_cands = [c for c in selected_items if c in growth_df.columns and c != "생중량"]
                else:
                    x_cands = []
                if not x_cands:
                    x_cands = [c for c in ["잎 수", "지상부 길이"] if c in growth_df.columns]
                if x_cands:
                    plot_df = growth_df[["생중량"] + x_cands].dropna()
                    if len(plot_df) >= 2:
                        for col in x_cands:
                            fig = px.scatter(plot_df, x=col, y="생중량", title=f"{col} vs 생중량")
                            x = plot_df[col]
                            y = plot_df["생중량"]
                            slope, intercept = np.polyfit(x, y, 1)
                            fig.add_trace(
                                go.Scatter(
                                    x=x,
                                    y=intercept + slope * x,
                                    mode="lines",
                                    name="추세선",
                                    line=dict(dash="dash"),
                                )
                            )
                            corr = x.corr(y)
                            st.write(f"**{col} vs 생중량** 상관계수: {corr:.3f}")
                            fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                            st.plotly_chart(fig, width="stretch")
                    else:
                        st.info("비교할 점이 2개 미만이라 상관계수를 계산하지 않아요.")
                else:
                    st.info("선택할 생육 측정 항목이 없어요.")
            else:
                st.info("생체중량 열이 없어요.")

            st.markdown("### 🏆 생중량 상위 25% vs 하위 25% 비교")
            if "생중량" in growth_df.columns and growth_df["생중량"].notna().sum() >= 4:
                bio = growth_df["생중량"].dropna()
                q25 = bio.quantile(0.25)
                q75 = bio.quantile(0.75)
                bottom = growth_df[growth_df["생중량"] <= q25]
                top = growth_df[growth_df["생중량"] >= q75]

                rows = []
                for label, grp in [("하위 25%", bottom), ("상위 25%", top)]:
                    row = {"구분": label, "개체 수": len(grp)}
                    if "잎 수" in grp.columns:
                        row["평균 잎 수"] = round(grp["잎 수"].mean(), 2)
                    else:
                        row["평균 잎 수"] = "—"
                    if "지상부 길이" in grp.columns:
                        row["평균 지상부 길이(mm)"] = round(grp["지상부 길이"].mean(), 2)
                    else:
                        row["평균 지상부 길이(mm)"] = "—"
                    if "지하부 길이" in grp.columns:
                        row["평균 지하부 길이(mm)"] = round(grp["지하부 길이"].mean(), 2)
                    else:
                        row["평균 지하부 길이(mm)"] = "—"
                    rows.append(row)
                st.dataframe(pd.DataFrame(rows), width="stretch")
            else:
                st.info("비교할 개체가 충분하지 않아 상위·하위 25% 비교를 생략해요.")

            with st.expander("🌱 생육 데이터 원본 테이블 + CSV 다운로드"):
                st.dataframe(growth_df, width="stretch")
                csv = growth_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "생육 CSV 다운로드",
                    csv,
                    file_name=f"{school_name}_생육결과데이터.csv",
                    mime="text/csv",
                )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
