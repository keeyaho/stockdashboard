import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

from pathlib import Path
from datetime import datetime

# 1. 페이지 설정 (모바일 최적화)
st.set_page_config(
    page_title="AI 사이클 관제센터",
    layout="centered"
)

# 🚨 [모바일 소형화 및 스타일 제어 CSS 전체 교체]
st.markdown("""
    <style>

    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
    }

    html, body, p, span, label, div {
        font-size: 15px !important;
    }

    h3 {
        font-size: 20px !important;
        font-weight: bold;
        margin-top: 12px !important;
        margin-bottom: 8px !important;
    }

    h4 {
        font-size: 17px !important;
        font-weight: bold;
        margin-top: 8px !important;
        margin-bottom: 4px !important;
    }

    button[data-baseweb="tab"] p {
        font-size: 15px !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        padding: 10px !important;
    }

    </style>
""", unsafe_allow_html=True)

# 상단 타이틀 컴팩트 디자인
st.caption("📈 매도 점검 | AI 사이클 관제센터 (1분 자동 갱신)")

# -------------------------
# 데이터 캐싱 및 로드 함수
# -------------------------
@st.cache_data(ttl=60)
def get_history(ticker):
    try:
        df = yf.Ticker(ticker).history(period="1y")
        return df if not df.empty else None
    except:
        return None

@st.cache_data(ttl=60)
def get_info(ticker):
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

def get_latest(ticker):
    hist = get_history(ticker)
    if hist is None or hist.empty:
        return None
    return float(hist["Close"].iloc[-1])

@st.cache_data(ttl=60)
def get_pe_detailed(ticker, pe_type="forward"):
    info = get_info(ticker)
    key = "forwardPE" if pe_type == "forward" else "trailingPE"
    pe = info.get(key)
    if pe: return float(pe)
    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period="1d")
        if hist.empty: return None
        current_price = float(hist["Close"].iloc[-1])
        eps_key = "forwardEps" if pe_type == "forward" else "trailingEps"
        eps = info.get(eps_key)
        if not eps:
            if ticker == "005930.KS": eps = 13500.0 if pe_type == "forward" else 9500.0
            elif ticker == "TSM": eps = 8.2 if pe_type == "forward" else 6.8
        if current_price and eps: return round(current_price / eps, 2)
    except: pass
    fallback = {"005930.KS": {"forward": 18.5, "trailing": 24.2}, "TSM": {"forward": 23.0, "trailing": 28.5}}
    return fallback.get(ticker, {}).get(pe_type, 20.0)

# -------------------------
# PER 저장 함수 추가
# -------------------------
def save_per_history(samsung_f_pe, tsmc_f_pe, forward_ratio):
    file_path = Path("per_history.csv")
    today = datetime.now().strftime("%Y-%m-%d")
    
    new_row = pd.DataFrame([{
        "date": today,
        "samsung_forward_pe": samsung_f_pe,
        "tsmc_forward_pe": tsmc_f_pe,
        "ratio": round(forward_ratio, 4)
    }])

    if file_path.exists():
        try:
            df = pd.read_csv(file_path)
            if today not in df["date"].astype(str).values:
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_csv(file_path, index=False)
        except Exception:
            pass
    else:
        try:
            new_row.to_csv(file_path, index=False)
        except Exception:
            pass

# -------------------------
# ⚡ 데이터 수집 및 연산 실행
# -------------------------
us10 = get_latest("^TNX")
us30 = get_latest("^TYX")
wti = get_latest("CL=F")
copper = get_latest("HG=F")

nvda_hist = get_history("NVDA")
if nvda_hist is not None and not nvda_hist.empty:
    nvda_price = float(nvda_hist["Close"].iloc[-1])
    nvda_ath = float(nvda_hist["High"].max())
    nvda_drawdown = ((nvda_price - nvda_ath) / nvda_ath) * 100
else:
    nvda_price, nvda_ath, nvda_drawdown = None, None, None

samsung_f_pe = get_pe_detailed("005930.KS", "forward")
tsmc_f_pe = get_pe_detailed("TSM", "forward")
forward_ratio = samsung_f_pe / tsmc_f_pe if tsmc_f_pe else 1.0

samsung_t_pe = get_pe_detailed("005930.KS", "trailing")
tsmc_t_pe = get_pe_detailed("TSM", "trailing")
trailing_ratio = samsung_t_pe / tsmc_t_pe if tsmc_t_pe else 1.0

# PER 계산 후 자동 저장 실행
save_per_history(samsung_f_pe, tsmc_f_pe, forward_ratio)

# 리스크 스코어링 및 구리 경고 로직 수정
score = 100
reasons = []
if us10 and us10 >= 4.75: score -= 10; reasons.append(f"美 10년물 금리 경고 ({us10:.2f}%)")
if us30 and us30 >= 5.20: score -= 10; reasons.append(f"美 30년물 금리 경고 ({us30:.2f}%)")
if wti and wti >= 120: score -= 10; reasons.append(f"유가 경고 (${wti:.2f})")

# 구리 가격 경고 수정 (5달러 이상일 때 경고 및 감점)
if copper and copper >= 5.0:
    score -= 10
    reasons.append(f"구리 가격 경고 (${copper:.2f})")

copper_status = "🟢정상" if (copper and copper < 5.00) else "🚨경고"


# -------------------------
# 📊 UI 및 차트 시각화 예시 (게이지 및 차트 추가 영역)
# -------------------------
st.write(f"### 🛡️ 리스크 스코어: {score}점")
if reasons:
    for r in reasons:
        st.write(f"- {r}")

# [예시용 게이지 생성 객체 - 기존 코드 유지용]
fig_f = go.Figure(go.Indicator(
    mode = "gauge+number",
    value = forward_ratio,
    title = {'text': "선행 PER 비율 (삼성/TSMC)"},
    gauge = {'axis': {'range': [None, 2]},
             'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 1.0}}
))

fig_t = go.Figure(go.Indicator(
    mode = "gauge+number",
    value = trailing_ratio,
    title = {'text': "후행 PER 비율 (삼성/TSMC)"},
    gauge = {'axis': {'range': [None, 2]},
             'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 1.0}}
))

# 5. 게이지 크게 조절 (높이 75 -> 120 변경)
fig_f.update_layout(
    height=120,
    margin=dict(l=50, r=50, t=15, b=5)
)

fig_t.update_layout(
    height=120,
    margin=dict(l=50, r=50, t=15, b=5)
)

# 화면 출력
st.plotly_chart(fig_f, use_container_width=True)
st.plotly_chart(fig_t, use_container_width=True)


# 6. PER 추이 차트 추가 (후행 PER 출력 바로 밑에 배치)
st.markdown("#### 📈 삼성/TSMC 선행 PER 비율 추이")

try:
    history_df = pd.read_csv("per_history.csv")

    if len(history_df) > 0:
        history_df["date"] = pd.to_datetime(history_df["date"])

        fig_ratio = go.Figure()

        # 데이터가 1개일 때도 점으로 표현될 수 있도록 모드 유지
        fig_ratio.add_trace(
            go.Scatter(
                x=history_df["date"],
                y=history_df["ratio"],
                mode="lines+markers",
                name="PER Ratio"
            )
        )

        fig_ratio.add_hline(
            y=1.0,
            line_dash="dash",
            annotation_text="경고선"
        )

        fig_ratio.update_layout(
            height=260,
            margin=dict(l=10, r=10, t=20, b=10),
            yaxis_title="삼성 / TSMC"
        )

        st.plotly_chart(fig_ratio, use_container_width=True)
except Exception:
    pass
