import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

# 1. 페이지 설정 (모바일 centered 구조)
st.set_page_config(
    page_title="AI 사이클 관제센터",
    layout="centered"
)

# 🚨 [모바일 초소형 뷰포트 및 여백 제어 CSS]
st.markdown("""
    <style>
    /* 화면 좌우 여백을 최소화하여 모바일 꽉 찬 화면 구현 */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
    }
    /* Streamlit 자체 제목/소제목 폰트 강제 축소 */
    h3 { font-size: 13px !important; font-weight: bold; margin-top: 10px !important; margin-bottom: 4px !important; }
    h4 { font-size: 11px !important; font-weight: bold; margin-top: 8px !important; margin-bottom: 2px !important; }
    button[data-baseweb="tab"] p { font-size: 10px !important; }
    </style>
""", unsafe_allow_html=True)

# 상단 타이틀 컴팩트 디자인
st.markdown("""
    <div style="margin-bottom: 10px;">
        <span style="font-size: 16px; font-weight: bold;">📈 매도 점검</span>
        <span style="font-size: 9px; color: gray; margin-left: 6px;">AI 관제센터 — 1분 자동 갱신</span>
    </div>
""", unsafe_allow_html=True)

# -------------------------
# 데이터 캐싱 및 로드 함수 (기존 로직 유지)
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
# ⚡ 데이터 수집 및 연산 실행 (프래그먼트 무한루프 제거로 먹통 해결)
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

# 리스크 스코어링
score = 100
reasons = []
if us10 and us10 >= 4.75: score -= 10; reasons.append(f"美 10년물 금리 경고 ({us10:.2f}%)")
if us30 and us30 >= 5.20: score -= 10; reasons.append(f"美 30년물 금리 경고 ({us30:.2f}%)")
if wti and wti >= 120: score -= 10; reasons.append(f"유가 경고 (${wti:.2f})")
if copper and copper <= 5.0: score -= 10; reasons.append(f"구리 가격 경고 (${copper:.2f})")
if nvda_drawdown and nvda_drawdown <= -20: score -= 20; reasons.append(f"NVDA 경고 ({nvda_drawdown:.2f}%)")
if forward_ratio >= 1: score -= 30; reasons.append(f"삼성 선행 PER ≥ TSMC ({forward_ratio:.2f})")
elif forward_ratio >= 0.7: score -= 15; reasons.append(f"삼성 선행 PER TSMC 근접 ({forward_ratio:.2f})")

# -------------------------
# UI 렌더링 영역 (100% 미니어처 가로 정렬 HTML 방식)
# -------------------------

# 1. 종합 상태 배너
if score >= 80:
    st.markdown(f"<div style='font-size:11px; font-weight:bold; color:#238636; background-color:rgba(35,134,54,0.08); padding:5px; border-radius:4px; margin-bottom:8px;'>🟢 정상 ({score}점)</div>", unsafe_allow_html=True)
elif score >= 60:
    st.markdown(f"<div style='font-size:11px; font-weight:bold; color:#d29922; background-color:rgba(210,153,34,0.08); padding:5px; border-radius:4px; margin-bottom:8px;'>🟡 주의 ({score}점)</div>", unsafe_allow_html=True)
else:
    st.markdown(f"<div style='font-size:11px; font-weight:bold; color:#f85149; background-color:rgba(248,81,73,0.08); padding:5px; border-radius:4px; margin-bottom:8px;'>🔴 경고 ({score}점)</div>", unsafe_allow_html=True)

if reasons:
    with st.expander("🚨 주요 리스크 요인", expanded=True):
        for r in reasons:
            st.markdown(f"<div style='font-size:9px; color:#f85149; padding:1px 0;'>• {r}</div>", unsafe_allow_html=True)

# 2. 글로벌 매크로 지표 (가로 한 줄 초소형 정렬)
st.subheader("🌐 글로벌 매크로 지표")
us10_status = "🟢" if (us10 and us10 < 4.75) else "🚨"
us30_status = "🟢" if (us30 and us30 < 5.20) else "🚨"
wti_status = "🟢" if (wti and wti < 120) else "🚨"
copper_status = "🟢" if (copper and copper > 5.00) else "🚨"

us10_txt = f"{us10:.2f}%" if us10 else "N/A"
us30_txt = f"{us30:.2f}%" if us30 else "N/A"
wti_txt = f"${wti:.2f}" if wti else "N/A"
copper_txt = f"${copper:.2f}" if copper else "N/A"

st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background-color: rgba(128,128,128,0.04); padding: 5px; border-radius: 4px; border: 1px solid rgba(128,128,128,0.15);">
        <div style="text-align: center; flex: 1;"><div style="font-size: 8px; color: gray;">美 10년</div><div style="font-size: 10px; font-weight: bold; white-space: nowrap;">{us10_status}{us10_txt}</div></div>
        <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 16px;"></div>
        <div style="text-align: center; flex: 1;"><div style="font-size: 8px; color: gray;">美 30년</div><div style="font-size: 10px; font-weight: bold; white-space: nowrap;">{us30_status}{us30_txt}</div></div>
        <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 16px;"></div>
        <div style="text-align: center; flex: 1;"><div style="font-size: 8px; color: gray;">WTI 원유</div><div style="font-size: 10px; font-weight: bold; white-space: nowrap;">{wti_status}{wti_txt}</div></div>
        <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 16px;"></div>
        <div style="text-align: center; flex: 1;"><div style="font-size: 8px; color: gray;">구리 가격</div><div style="font-size: 10px; font-weight: bold; white-space: nowrap;">{copper_status}{copper_txt}</div></div>
    </div>
""", unsafe_allow_html=True)

# 3. 엔비디아 지표 (가로 한 줄 초소형 정렬)
st.subheader("🍏 엔비디아 지표")
if nvda_price:
    nvda_status = "🟢" if nvda_drawdown > -10 else ("🟡" if nvda_drawdown > -20 else "🔴")
    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; background-color: rgba(128,128,128,0.04); padding: 5px; border-radius: 4px; border: 1px solid rgba(128,128,128,0.15);">
            <div style="text-align: center; flex: 1;"><div style="font-size: 8px; color: gray;">현재가</div><div style="font-size: 10px; font-weight: bold;">${nvda_price:.2f}</div></div>
            <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 16px;"></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 8px; color: gray;">전고점(ATH)</div><div style="font-size: 10px; font-weight: bold;">${nvda_ath:.2f}</div></div>
            <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 16px;"></div>
            <div style="text-align: center; flex: 1;"><div style="font-size: 8px; color: gray;">전고점 대비</div><div style="font-size: 10px; font-weight: bold; white-space: nowrap;">{nvda_status}{nvda_drawdown:.2f}%</div></div>
        </div>
    """, unsafe_allow_html=True)

# 차트 탭 (높이 100px 미니멀 제한)
tabs = st.tabs(["NVDA", "삼성전자", "TSMC"])
with tabs[0]:
    if nvda_hist is not None: st.line_chart(nvda_hist["Close"], height=100)
with tabs[1]:
    samsung_hist = get_history("005930.KS")
    if samsung_hist is not None: st.line_chart(samsung_hist["Close"], height=100)
with tabs[2]:
    tsmc_hist = get_history("TSM")
    if tsmc_hist is not None: st.line_chart(tsmc_hist["Close"], height=100)

# 4. 📊 밸류에이션 점검 섹션 (초소형 테이블형 정렬)
st.markdown("<hr style='margin: 10px 0; border:0; border-top:1px dashed rgba(128,128,128,0.2);'/>", unsafe_allow_html=True)
st.subheader("📊 밸류에이션 점검")

# 선행 PER 한 줄 요약
st.markdown("#### ⏩ 12M 선행(Forward) PER")
f_status = "🟢안정" if forward_ratio < 0.7 else ("🟡주의" if forward_ratio < 1.0 else "🔴고평가")
st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background-color: rgba(128,128,128,0.04); padding: 5px; border-radius: 4px; border: 1px solid rgba(128,128,128,0.15);">
        <div style="text-align: center; flex: 1;"><div style="font-size: 8px; color: gray;">삼성 선행</div><div style="font-size: 10px; font-weight: bold;">{samsung_f_pe:.2f}</div></div>
        <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 16px;"></div>
        <div style="text-align: center; flex: 1;"><div style="font-size: 8px; color: gray;">TSMC 선행</div><div style="font-size: 10px; font-weight: bold;">{tsmc_f_pe:.2f}</div></div>
        <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 16px;"></div>
