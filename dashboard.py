import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import time

# 1. 페이지 설정 (최대한 압축 레이아웃)
st.set_page_config(
    page_title="AI 사이클 관제센터",
    layout="centered"
)

# 🚨 [모바일 초소형 강제 스타일] Streamlit의 모든 글씨와 간격을 강제로 축소합니다.
st.markdown("""
    <style>
    /* 전체 폰트 및 요소 축소 */
    html, body, [data-testid="stWidgetLabel"], .stText, p, span, label {
        font-size: 10px !important;
    }
    /* 타이틀 및 헤더 크기 대폭 축소 */
    div.main-title { font-size: 16px !important; font-weight: bold; margin-bottom: 2px; }
    div.main-caption { font-size: 9px !important; color: gray; margin-bottom: 8px; }
    h3 { font-size: 12px !important; font-weight: bold; margin-top: 8px !important; margin-bottom: 4px !important; }
    h4 { font-size: 10px !important; font-weight: bold; margin-top: 6px !important; margin-bottom: 2px !important; }
    
    /* 탭(Tab) 글자 크기 축소 */
    button[data-baseweb="tab"] p {
        font-size: 10px !important;
    }
    
    /* 모바일 좌우 여백 최소화하여 꽉 차게 변경 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    /* 스크롤바 안 생기도록 내부 카드 마진 제거 */
    div[data-testid="stVerticalBlock"] {
        gap: 6px !important;
    }
    </style>
    
    <div class="main-title">📈 매도 점검</div>
    <div class="main-caption">AI 사이클 관제센터 — 1분 주기 자동 갱신 중</div>
""", unsafe_allow_html=True)

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
    
    if pe:
        return float(pe)
        
    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period="1d")
        if hist.empty:
            return None
        current_price = float(hist["Close"].iloc[-1])
        
        eps_key = "forwardEps" if pe_type == "forward" else "trailingEps"
        eps = info.get(eps_key)
        
        if not eps:
            if ticker == "005930.KS":
                eps = 13500.0 if pe_type == "forward" else 9500.0
            elif ticker == "TSM":
                eps = 8.2 if pe_type == "forward" else 6.8
                
        if current_price and eps:
            return round(current_price / eps, 2)
    except:
        pass
        
    fallback = {
        "005930.KS": {"forward": 18.5, "trailing": 24.2},
        "TSM": {"forward": 23.0, "trailing": 28.5}
    }
    return fallback.get(ticker, {}).get(pe_type, 20.0)


# -------------------------
# ⚡ 자동 갱신 프래그먼트 함수
# -------------------------
@st.fragment
def run_dashboard(interval_seconds=60):
    
    # 데이터 수집
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

    if us10 and us10 >= 4.75:
        score -= 10
        reasons.append(f"미국 10년물 금리 경고 ({us10:.2f}%)")

    if us30 and us30 >= 5.20:
        score -= 10
        reasons.append(f"미국 30년물 금리 경고 ({us30:.2f}%)")

    if wti and wti >= 120:
        score -= 10
        reasons.append(f"유가 경고 (${wti:.2f})")

    if copper and copper <= 5.0:
        score -= 10
        reasons.append(f"구리 가격 경고 (${copper:.2f})")

    if nvda_drawdown and nvda_drawdown <= -20:
        score -= 20
        reasons.append(f"NVDA 경고 ({nvda_drawdown:.2f}%)")

    if forward_ratio >= 1:
        score -= 30
        reasons.append(f"삼성 선행 PER ≥ TSMC 선행 PER ({forward_ratio:.2f})")
    elif forward_ratio >= 0.7:
        score -= 15
        reasons.append(f"삼성 선행 PER이 TSMC에 근접 ({forward_ratio:.2f})")

    # 종합 상태 표시 (미니어처 폰트 적용)
    if score >= 80:
        st.markdown(f"<div style='font-size:11px; font-weight:bold; color:#238636; background-color:rgba(35,134,54,0.1); padding:4px; border-radius:4px;'>🟢 정상 ({score}점)</div>", unsafe_allow_html=True)
    elif score >= 60:
        st.markdown(f"<div style='font-size:11px; font-weight:bold; color:#d29922; background-color:rgba(210,153,34,0.1); padding:4px; border-radius:4px;'>🟡 주의 ({score}점)</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='font-size:11px; font-weight:bold; color:#f85149; background-color:rgba(248,81,73,0.1); padding:4px; border-radius:4px;'>🔴 경고 ({score}점)</div>", unsafe_allow_html=True)

    # 리스크 요인 노출
    if reasons:
        with st.expander("🚨 주요 리스크 요인", expanded=True):
            for r in reasons:
                st.markdown(f"<span style='font-size:9px;'>• {r}</span>", unsafe_allow_html=True)

    # 🌐 글로벌 매크로 지표 섹션 (초소형 9~10px 한 줄 배치)
    st.subheader("🌐 글로벌 매크로 지표")
    
    us10_status = "🟢" if (us10 and us10 < 4.75) else "🚨"
    us30_status = "🟢" if (us30 and us30 < 5.20) else "🚨"
    wti_status = "🟢" if (wti and wti < 120) else "🚨"
    copper_status = "🟢" if (copper and copper > 5.00) else "🚨"

    us10_txt = f"{us10:.2f}%" if us10 else "N/A"
    us30_txt = f"{us30:.2f}%" if us30 else "N/A"
    wti_txt = f"${wti:.2f}" if wti else "N/A"
    copper_txt = f"${copper:.2f}" if copper else "N/A"

    macro_html = f"""
    <div style="display: flex; justify-content: space-between; align-items: center; background-color: rgba(128,128,128,0.04); padding: 5px 3px; border-radius: 4px; border: 1px solid rgba(128,128,128,0.15); gap: 1px;">
        <div style="text-align: center; flex: 1;">
            <div style="font-size: 8px; color: gray; white-space: nowrap;">美 10년</div>
            <div style="font-size: 10px; font-weight: bold; white-space: nowrap;">{us10_status}{us10_txt}</div>
        </div>
        <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 18px;"></div>
        <div style="text-align: center; flex: 1;">
            <div style="font-size: 8px; color: gray; white-space: nowrap;">美 30년</div>
            <div style="font-size: 10px; font-weight: bold; white-space: nowrap;">{us30_status}{us30_txt}</div>
        </div>
        <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 18px;"></div>
        <div style="text-align: center; flex: 1;">
            <div style="font-size: 8px; color: gray; white-space: nowrap;">WTI 원유</div>
            <div style="font-size: 10px; font-weight: bold; white-space: nowrap;">{wti_status}{wti_txt}</div>
        </div>
        <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 18px;"></div>
        <div style="text-align: center; flex: 1;">
            <div style="font-size: 8px; color: gray; white-space: nowrap;">구리 가격</div>
            <div style="font-size: 10px; font-weight: bold; white-space: nowrap;">{copper_status}{copper_txt}</div>
        </div>
    </div>
    """
    st.markdown(macro_html, unsafe_allow_html=True)

    # 🍏 엔비디아 섹션
    st.subheader("🍏 엔비디아 지표")
    if nvda_price:
        nvda_status = "🟢" if nvda_drawdown > -10 else ("🟡" if nvda_drawdown > -20 else "🔴")
        nvda_html = f"""
        <div style="display: flex; justify-content: space-between; align-items: center; background-color: rgba(128,128,128,0.04); padding: 5px 3px; border-radius: 4px; border: 1px solid rgba(128,128,128,0.15); gap: 1px;">
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 8px; color: gray;">현재가</div>
                <div style="font-size: 10px; font-weight: bold;">${nvda_price:.2f}</div>
            </div>
            <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 18px;"></div>
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 8px; color: gray;">전고점</div>
                <div style="font-size: 10px; font-weight: bold;">${nvda_ath:.2f}</div>
            </div>
            <div style="border-left: 1px solid rgba(128,128,128,0.15); height: 18px;"></div>
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 8px; color: gray;">전고점대비</div>
                <div style="font-size: 10px; font-weight: bold;">{nvda_status}{nvda_drawdown:.2f}%</div>
            </div>
        </div>
        """
        st.markdown(nvda_html, unsafe_allow_html=True)

    # 차트 탭 (높이 110px 초소형 제한)
    tabs = st.tabs(["NVDA", "삼성전자", "TSMC"])
    with tabs[0]:
        if nvda_hist is not None: st.line_chart(nvda_hist["Close"], height=110)
    with tabs[1]:
        samsung_hist = get_history("005930.KS")
        if samsung_hist is not None: st.line_chart(samsung_hist["Close"], height=110)
    with tabs[2]:
        tsmc_hist = get_history("TSM")
        if tsmc_hist is not None: st.line_chart(tsmc_hist["Close"], height=110)

    # 📊 밸류에이션 점검 섹션
    st.markdown("<hr style='margin: 8px 0;'/>", unsafe_allow_html=True)
    st.subheader("📊 밸류에이션 점검")
    
    # 1. 선행 PER
