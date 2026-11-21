
 
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os

# 페이지 설정
st.set_page_config(
    page_title="그린란드고추냉이 생육 분석",
    page_icon="🌱",
    layout="wide"
)

# 한글 폰트 설정
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

st.title("🌱 그린란드고추냉이의 생육 수준에 따른 뿌리 특성 비교")
st.caption("같은 스마트팜에서 자란 개체들의 생육 차이와 뿌리 특성 분석")

# CSV 읽기
@st.cache_data
def read_csv(data):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

# 열 이름 표준화
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
                df[c].astype(str).str.replace(",", "").str.extract(
                    r"(-?\d+\.?\d*)"
                )[0],
                errors="coerce"
            )
            if num.notna().mean() >= 0.5:
                df[c] = num

    if "생중량" not in df.columns:
        if {"지상부 질량", "지하부 질량"} <= set(df.columns):
            df["생중량"] = df["지상부 질량"] + df["지하부 질량"]

    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")

        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = (
                pd.to_datetime(parts[0], format="%Y%m%d")
                + pd.to_timedelta(parts[1].astype(int), unit="h")
            )

        df["time"] = parsed

    return df


# 사이드바: 파일 업로드
st.sidebar.header("📁 데이터 업로드")

env_file = st.sidebar.file_uploader(
    "환경 데이터 CSV",
    type="csv",
    key="env"
)

growth_file = st.sidebar.file_uploader(
    "생육 결과 데이터 CSV",
    type="csv",
    key="growth"
)

# 파일은 여기에서 한 번만 읽기
env_df = pd.DataFrame()
growth_df = pd.DataFrame()

env_school = ""
growth_school = ""

with st.spinner("CSV 데이터를 불러오는 중입니다..."):

    if env_file is not None:
        env_df = std_cols(read_csv(env_file.getvalue()))
        env_school = os.path.splitext(env_file.name)[0].split("_")[0]

    if growth_file is not None:
        growth_df = std_cols(read_csv(growth_file.getvalue()))
        growth_school = os.path.splitext(growth_file.name)[0].split("_")[0]

# 생육 측정 항목 선택
metric_options = [
    c for c in [
        "생중량", "잎 수", "지상부 길이",
        "지하부 길이", "지상부 질량", "지하부 질량"
    ]
    if c in growth_df.columns
    and pd.api.types.is_numeric_dtype(growth_df[c])
]

if metric_options:
    selected_metric = st.sidebar.selectbox(
        "📊 생육 측정 항목 선택",
        metric_options
    )
else:
    selected_metric = None

st.sidebar.divider()
st.sidebar.caption("환경 데이터와 생육 결과 데이터는 각각 따로 업로드할 수 있습니다.")

# 공통 함수
def style_fig(fig, title, y_title=None):
    fig.update_layout(
        title=title,
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
        template="plotly_white",
        hovermode="closest",
        margin=dict(l=40, r=30, t=65, b=40),
        yaxis_title=y_title
    )
    return fig


def bar_chart(data, x, y, title, y_title, color=None):
    fig = px.bar(
        data,
        x=x,
        y=y,
        color=color,
        title=title,
        text_auto=".2f"
    )
    fig.update_traces(textposition="outside")
    return style_fig(fig, title, y_title)


def comparison_chart(labels, values, title, y_title):
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=labels,
        y=values,
        text=[f"{v:.2f}" for v in values],
        textposition="outside"
    ))

    return style_fig(fig, title, y_title)


def valid_numeric(df, col):
    if col not in df.columns:
        return pd.Series(dtype=float)

    return pd.to_numeric(df[col], errors="coerce").dropna()


# 탭 구성
tab1, tab2, tab3 = st.tabs([
    "🔎 1. 탐구의 배경",
    "📊 2. 생육 그룹별 특징 비교",
    "🧪 3. 가설 검증과 최종 결론"
])


# ==================================================
# 탭 1. 탐구의 배경
# ==================================================
with tab1:
    try:
        st.header("같은 환경인데 왜 다르게 자랐을까?")

        st.markdown("""
        그린란드고추냉이는 같은 스마트팜에서 같은 기간 동안 재배되었지만,
        개체마다 생육 상태에 차이가 나타났다.

        이번 탐구에서는 개체별 생중량을 기준으로 생육 차이를 확인하고,
        뿌리의 길이와 질량이 생육 수준에 어떤 관계가 있는지 알아보고자 한다.
        """)

        if growth_df.empty:
            st.info("생육 결과 CSV를 업로드하면 개체별 분석이 시작됩니다.")

        elif "생중량" not in growth_df.columns:
            st.info("생중량 또는 지상부·지하부 질량 열을 확인할 수 없습니다.")

        else:
            data = growth_df.copy()
            data["생중량"] = pd.to_numeric(data["생중량"], errors="coerce")
            data = data.dropna(subset=["생중량"])

            if len(data) < 2:
                st.info("분석할 수 있는 생중량 데이터가 2개 미만입니다.")
            else:
                school = growth_school or "업로드한 학교"
                min_idx = data["생중량"].idxmin()
                max_idx = data["생중량"].idxmax()

                min_value = data.loc[min_idx, "생중량"]
                max_value = data.loc[max_idx, "생중량"]

                min_id = data.loc[min_idx, "개체번호"] if "개체번호" in data.columns else "-"
                max_id = data.loc[max_idx, "개체번호"] if "개체번호" in data.columns else "-"

                st.caption(
                    f"분석 학교: {school} | 분석 개체 수: {len(data)}개"
                )

                c1, c2, c3 = st.columns(3)

                c1.metric("분석 개체 수", f"{len(data)}개")
                c2.metric("가장 가벼운 개체", f"{min_value:.2f}g")
                c3.metric("가장 무거운 개체", f"{max_value:.2f}g")

                st.divider()

                st.subheader("① 개체별 생중량 차이")

                if max_value > 0 and min_value > 0:
                    st.metric(
                        "가장 무거운 개체와 가장 가벼운 개체의 차이",
                        f"{max_value / min_value:.2f}배"
                    )

                plot_data = data.copy()

                if "개체번호" in plot_data.columns:
                    plot_data["표시번호"] = plot_data["개체번호"].astype(str)
                else:
                    plot_data["표시번호"] = [
                        str(i + 1) for i in range(len(plot_data))
                    ]

                plot_data["그룹"] = "일반 개체"
                plot_data.loc[plot_data["생중량"] == min_value, "그룹"] = "가장 가벼운 개체"
                plot_data.loc[plot_data["생중량"] == max_value, "그룹"] = "가장 무거운 개체"

                fig = px.bar(
                    plot_data,
                    x="표시번호",
                    y="생중량",
                    color="그룹",
                    color_discrete_map={
                        "일반 개체": "#91B7A0",
                        "가장 가벼운 개체": "#E69B8B",
                        "가장 무거운 개체": "#477D63"
                    },
                    hover_data=["생중량"],
                    title="개체별 생중량 비교"
                )

                fig.update_layout(
                    font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
                    template="plotly_white",
                    xaxis_title="개체번호",
                    yaxis_title="생중량(g)"
                )

                st.plotly_chart(fig, width="stretch")

                st.subheader("② 가장 무거운 개체와 가장 가벼운 개체")

                a, b = st.columns(2)

                with a:
                    st.metric(
                        f"가장 가벼운 개체 ({min_id})",
                        f"{min_value:.2f}g"
                    )

                with b:
                    st.metric(
                        f"가장 무거운 개체 ({max_id})",
                        f"{max_value:.2f}g"
                    )

                st.subheader("③ 탐구 목적과 가설")

                st.markdown("""
                **탐구 목적**

                같은 환경에서 재배한 식물도 개체별 생육 차이가 발생하는 이유를
                뿌리 길이와 뿌리 질량을 중심으로 분석한다.

                **탐구 가설**

                덜 자란 개체일수록 뿌리 질량 대비 길이가 클 것이다.

                즉, 뿌리 질량 1g당 길이가 덜 자란 그룹에서 더 크게 나타날 것으로 예상하였다.
                """)

                st.info(
                    "뿌리 질량 대비 길이 = 뿌리 길이(mm) ÷ 뿌리 질량(g)"
                )

        # 환경 데이터 확인
        st.divider()
        st.subheader("④ 재배 환경 데이터 확인")

        if env_df.empty:
            st.info("환경 CSV를 업로드하면 온도와 습도 등 환경 데이터를 확인할 수 있습니다.")
        else:
            env_cols = [
                c for c in ["temperature", "humidity", "ph", "ec"]
                if c in env_df.columns
                and pd.api.types.is_numeric_dtype(env_df[c])
            ]

            if not env_cols:
                st.info("표시할 수 있는 환경 수치 열이 없습니다.")
            else:
                env_labels = {
                    "temperature": "온도",
                    "humidity": "습도",
                    "ph": "pH",
                    "ec": "EC"
                }

                cols = st.columns(len(env_cols))

                for i, col in enumerate(env_cols):
                    vals = valid_numeric(env_df, col)

                    if len(vals) > 0:
                        cols[i].metric(
                            env_labels.get(col, col),
                            f"{vals.mean():.2f}"
                        )

                if "time" in env_df.columns:
                    chart_df = env_df[["time"] + env_cols].copy()
                    chart_df = chart_df.dropna(subset=["time"])
                    chart_df = chart_df.sort_values("time")

                    if not chart_df.empty:
                        selected_env = st.selectbox(
                            "환경 그래프 선택",
                            env_cols,
                            format_func=lambda x: env_labels.get(x, x),
                            key="env_select"
                        )

                        chart_df[selected_env] = pd.to_numeric(
                            chart_df[selected_env], errors="coerce"
                        )
                        chart_df = chart_df.dropna(subset=[selected_env])

                        if len(chart_df) >= 2:
                            fig = px.line(
                                chart_df,
                                x="time",
                                y=selected_env,
                                title=f"{env_labels.get(selected_env, selected_env)} 변화"
                            )
                            st.plotly_chart(
                                style_fig(fig, "재배 환경 변화"),
                                width="stretch"
                            )
                        else:
                            st.info("환경 그래프를 만들 데이터가 부족합니다.")
                else:
                    st.info("시간 열이 없어 환경 변화 그래프를 표시하지 않습니다.")

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")


# ==================================================
# 탭 2. 생육 그룹별 특징 비교
# ==================================================
with tab2:
    try:
        st.header("덜 자란 개체는 무엇이 달랐을까?")

        st.markdown("""
        전체 개체를 생중량 순서로 정렬한 뒤,
        상위 25%와 하위 25%를 비교하였다.

        상위 그룹은 생중량이 큰 개체이며,
        하위 그룹은 생중량이 작은 개체이다.
        """)

        required = ["생중량", "잎 수", "지하부 길이", "지하부 질량"]

        missing = [c for c in required if c not in growth_df.columns]

        if growth_df.empty:
            st.info("생육 결과 CSV를 업로드해 주세요.")

        elif missing:
            st.info(
                "그룹 비교에 필요한 열이 부족합니다: "
                + ", ".join(missing)
            )

        else:
            data = growth_df.copy()

            for c in required:
                data[c] = pd.to_numeric(data[c], errors="coerce")

            data = data.dropna(subset=["생중량"])
            data = data.sort_values("생중량").reset_index(drop=True)

            if len(data) < 4:
                st.info("상위·하위 그룹을 비교하려면 최소 4개 이상의 개체가 필요합니다.")
            else:
                # 33개체라면 각 그룹은 9개체
                group_size = max(1, int(np.ceil(len(data) * 0.25)))

                low = data.head(group_size).copy()
                high = data.tail(group_size).copy()

                low["그룹"] = "하위 25%"
                high["그룹"] = "상위 25%"

                compare = pd.concat([low, high], ignore_index=True)

                st.caption(
                    f"상위 그룹 {len(high)}개체 | 하위 그룹 {len(low)}개체"
                )

                # 평균 계산
                def group_mean(df, col):
                    vals = valid_numeric(df, col)
                    if len(vals) == 0:
                        return np.nan
                    return vals.mean()

                leaf_low = group_mean(low, "잎 수")
                leaf_high = group_mean(high, "잎 수")

                root_length_low = group_mean(low, "지하부 길이")
                root_length_high = group_mean(high, "지하부 길이")

                root_mass_low = group_mean(low, "지하부 질량")
                root_mass_high = group_mean(high, "지하부 질량")

                st.subheader("① 잎 수 비교")

                if not np.isnan(leaf_low) and not np.isnan(leaf_high):
                    c1, c2 = st.columns(2)

                    c1.metric("하위 25% 평균", f"{leaf_low:.2f}장")
                    c2.metric("상위 25% 평균", f"{leaf_high:.2f}장")

                    fig = comparison_chart(
                        ["하위 25%", "상위 25%"],
                        [leaf_low, leaf_high],
                        "생육 그룹별 잎 수 비교",
                        "평균 잎 수(장)"
                    )
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("잎 수 데이터가 부족합니다.")

                st.divider()
                st.subheader("② 뿌리 길이와 뿌리 질량 비교")

                left, right = st.columns(2)

                with left:
                    if not np.isnan(root_length_low) and not np.isnan(root_length_high):
                        fig = comparison_chart(
                            ["하위 25%", "상위 25%"],
                            [root_length_low, root_length_high],
                            "그룹별 평균 뿌리 길이",
                            "뿌리 길이(mm)"
                        )
                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.info("뿌리 길이 데이터가 부족합니다.")

                with right:
                    if not np.isnan(root_mass_low) and not np.isnan(root_mass_high):
                        fig = comparison_chart(
                            ["하위 25%", "상위 25%"],
                            [root_mass_low, root_mass_high],
                            "그룹별 평균 뿌리 질량",
                            "뿌리 질량(g)"
                        )
                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.info("뿌리 질량 데이터가 부족합니다.")

                st.subheader("③ 그룹별 수치 비교")

                rows = []

                for label, low_val, high_val, unit in [
                    ("잎 수", leaf_low, leaf_high, "장"),
                    ("뿌리 길이", root_length_low, root_length_high, "mm"),
                    ("뿌리 질량", root_mass_low, root_mass_high, "g")
                ]:
                    rows.append({
                        "측정 항목": label,
                        "하위 25% 평균": (
                            f"{low_val:.2f}{unit}" if not np.isnan(low_val) else "-"
                        ),
                        "상위 25% 평균": (
                            f"{high_val:.2f}{unit}" if not np.isnan(high_val) else "-"
                        )
                    })

                st.dataframe(pd.DataFrame(rows), width="stretch")

                st.info("""
                **분석 결과**

                덜 자란 그룹은 잘 자란 그룹보다 잎 수와 뿌리 질량이 적게 나타났다.
                반면 뿌리 길이는 두 그룹 사이에 큰 차이가 나타나지 않았다.

                따라서 생육 차이는 단순히 뿌리가 길고 짧은 것보다
                뿌리 질량과 잎 수의 차이와 관련이 있을 가능성이 있다.
                """)

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")


# ==================================================
# 탭 3. 가설 검증과 최종 결론
# ==================================================
with tab3:
    try:
        st.header("처음 예상은 맞았을까?")

        st.markdown("""
        마지막으로 뿌리 질량 대비 길이를 계산하고,
        생중량과의 관계를 상관계수와 산점도로 확인한다.
        """)

        required = ["생중량", "지하부 길이", "지하부 질량"]

        missing = [c for c in required if c not in growth_df.columns]

        if growth_df.empty:
            st.info("생육 결과 CSV를 업로드해 주세요.")

        elif missing:
            st.info(
                "가설 검증에 필요한 열이 부족합니다: "
                + ", ".join(missing)
            )

        else:
            data = growth_df.copy()

            for c in required:
                data[c] = pd.to_numeric(data[c], errors="coerce")

            data = data.dropna(subset=required)
            data = data[data["지하부 질량"] > 0].copy()

            if len(data) < 2:
                st.info("가설 검증에 필요한 유효 데이터가 부족합니다.")
            else:
                data["뿌리 질량 대비 길이"] = (
                    data["지하부 길이"] / data["지하부 질량"]
                )

                data = data.replace(
                    [np.inf, -np.inf], np.nan
                ).dropna(subset=["뿌리 질량 대비 길이"])

                data = data.sort_values("생중량").reset_index(drop=True)

                group_size = max(1, int(np.ceil(len(data) * 0.25)))

                low = data.head(group_size)
                high = data.tail(group_size)

                low_ratio = low["뿌리 질량 대비 길이"].mean()
                high_ratio = high["뿌리 질량 대비 길이"].mean()

                st.subheader("① 뿌리 질량 대비 길이 비교")

                c1, c2 = st.columns(2)

                c1.metric(
                    "하위 25% 평균",
                    f"{low_ratio:.2f} mm/g"
                )

                c2.metric(
                    "상위 25% 평균",
                    f"{high_ratio:.2f} mm/g"
                )

                fig = comparison_chart(
                    ["하위 25%", "상위 25%"],
                    [low_ratio, high_ratio],
                    "그룹별 뿌리 질량 대비 길이",
                    "뿌리 질량 대비 길이(mm/g)"
                )

                st.plotly_chart(fig, width="stretch")

                st.divider()
                st.subheader("② 생중량과 뿌리 질량 대비 길이의 관계")

                scatter_data = data[
                    ["생중량", "뿌리 질량 대비 길이"]
                ].dropna()

                if len(scatter_data) >= 2:
                    x = scatter_data["생중량"].to_numpy()
                    y = scatter_data["뿌리 질량 대비 길이"].to_numpy()

                    corr = scatter_data.corr().iloc[0, 1]

                    st.metric(
                        "상관계수(r)",
                        f"{corr:.3f}"
                    )

                    fig = go.Figure()

                    fig.add_trace(go.Scatter(
                        x=x,
                        y=y,
                        mode="markers",
                        name="개체별 데이터",
                        marker=dict(size=10, opacity=0.75)
                    ))

                    # 직접 계산하는 선형 추세선
                    if len(scatter_data) >= 2:
                        slope, intercept = np.polyfit(x, y, 1)

                        x_line = np.linspace(x.min(), x.max(), 100)
                        y_line = slope * x_line + intercept

                        fig.add_trace(go.Scatter(
                            x=x_line,
                            y=y_line,
                            mode="lines",
                            name="선형 추세선",
                            line=dict(width=2, dash="dash")
                        ))

                    fig.update_layout(
                        title="생중량과 뿌리 질량 대비 길이의 관계",
                        xaxis_title="생중량(g)",
                        yaxis_title="뿌리 질량 대비 길이(mm/g)",
                        template="plotly_white",
                        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")
                    )

                    st.plotly_chart(fig, width="stretch")

                    st.caption(
                        "상관계수는 두 변수의 관계가 얼마나 같은 방향 또는 반대 방향으로 나타나는지 보여주는 수치이다. "
                        "0에 가까울수록 선형 관계가 약하고, -1이나 1에 가까울수록 강하다."
                    )

                else:
                    st.info("상관관계와 추세선을 계산할 데이터가 2개 미만입니다.")

                st.divider()
                st.subheader("③ 가설 검증")

                if low_ratio > high_ratio:
                    st.success(
                        "가설 지지: 하위 그룹의 뿌리 질량 대비 길이가 더 크게 나타났습니다."
                    )
                else:
                    st.info(
                        "이번 데이터에서는 가설과 같은 방향의 결과가 나타나지 않았습니다."
                    )

                st.markdown(f"""
                - 하위 그룹: **{low_ratio:.2f}mm/g**
                - 상위 그룹: **{high_ratio:.2f}mm/g**
                """)

                if high_ratio > 0:
                    st.write(
                        f"하위 그룹의 뿌리 질량 대비 길이는 상위 그룹의 약 "
                        f"**{low_ratio / high_ratio:.2f}배**이다."
                    )

                st.divider()
                st.subheader("④ 최종 결론")

                st.markdown("""
                **1.** 덜 자란 그린란드고추냉이일수록 뿌리 질량 대비 길이가 크게 나타났다.

                **2.** 하지만 이는 뿌리가 실제로 더 길어서가 아니라,
                뿌리 질량이 적기 때문에 비율이 커진 결과였다.

                **3.** 두 그룹의 뿌리 길이는 큰 차이가 없었지만,
                뿌리 질량은 뚜렷한 차이를 보였다.

                **4.** 따라서 덜 자란 개체의 주요 특징은 상대적으로 적은 잎 수와 뿌리 질량이라고 해석할 수 있다.
                """)

                st.info(
                    "참고: 상관관계는 두 변수의 관련성을 나타내며, "
                    "한 변수가 다른 변수의 원인이라는 것을 직접 증명하지는 않는다."
                )

                # 분석 데이터 다운로드
                st.divider()
                st.subheader("⑤ 분석 데이터 다운로드")

                download_data = data.copy()

                csv_bytes = download_data.to_csv(
                    index=False
                ).encode("utf-8-sig")

                st.download_button(
                    label="📥 분석 결과 CSV 다운로드",
                    data=csv_bytes,
                    file_name="그린란드고추냉이_생육분석.csv",
                    mime="text/csv"
                )

                # 원본 생육 데이터 다운로드
                original_bytes = growth_df.to_csv(
                    index=False
                ).encode("utf-8-sig")

                st.download_button(
                    label="📥 표준화된 생육 데이터 CSV 다운로드",
                    data=original_bytes,
                    file_name="생육데이터.csv",
                    mime="text/csv"
                )

    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")


# ==================================================
# 사이드바 다운로드 및 데이터 상태
# ==================================================
st.sidebar.divider()
st.sidebar.subheader("📌 데이터 상태")

if env_file is not None:
    st.sidebar.success("환경 데이터 업로드 완료")
else:
    st.sidebar.info("환경 데이터 대기 중")

if growth_file is not None:
    st.sidebar.success("생육 결과 데이터 업로드 완료")
else:
    st.sidebar.info("생육 결과 데이터 대기 중")

st.sidebar.caption(
    "통계 용어 안내\n\n"
    "평균: 전체 값을 더해 개수로 나눈 값\n\n"
    "표준편차: 데이터가 평균에서 얼마나 퍼져 있는지 나타내는 값\n\n"
    "상관계수: 두 변수 사이의 선형적인 관계를 나타내는 값"
)
