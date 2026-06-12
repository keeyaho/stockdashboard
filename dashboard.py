import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

# 1. 페이지 설정 (모바일 최적화)
st.set_page_config(
    page_title="AI 사이클 관제센터",
    layout="centered"
)

# 🚨 [모바일 완전 꽉 찬 화면 및 제목 축소 CSS 스타일]
st.markdown("""
    <style>
    /* 여백 최소화 */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.3rem !important;
        padding-right: 0.3rem !important;
    }
    /* 스트림릿 기본 텍스트 및 제목 축소 */
    html, body, p, span, label, div { font-size: 10px !important; }
    h3 { font-size: 13px !important; font-weight: bold; margin-top: 12px !important; margin-bottom: 6px !important; }
    h4 { font-size: 11px !important; font-weight: bold; margin-top: 8px !important; margin-bottom: 2px !important; }
    button[data-baseweb="tab"] p { font-size: 10px !important; }
    </style>
""", unsafe_allow_html=True)

# 상단 타이틀 컴팩트 디자인
st.markdown("""
    <div style="margin-bottom: 10px;">
        <span style="font-size: 15px; font-weight: bold;">📈 매도 점검</span>
        <span style="font-size: 9px; color: gray; margin-left: 5px;">AI 관제센터 — 1분 자동 갱신</span>
    </div>
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
# UI 렌더링 영역
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


# 2. 글로벌 매크로 지표 (🚨 안전한 모바일용 테이블 정렬 구조)
st.subheader("🌐 글로벌 매크로 지표")
us10_status = "🟢" if (us10 and us10 < 4.75) else "🚨"
us30_status = "🟢" if (us30 and us30 < 5.20) else "🚨"
wti_status = "🟢" if (wti and wti < 120) else "🚨"
copper_status = "🟢" if (copper and copper > 5.00) else "🚨"

us10_txt = f"{us10:.2f}%" if us10 else "N/A"
us30_txt = f"{us30:.2f}%" if us30 else "N/A"
wti_txt = f"${wti:.2f}" if wti else "N/A"
copper_txt = f"${copper:.2f}" if copper else "N/A"

macro_table_html = f"""
<table style="width:100%; border-collapse:collapse; text-align:center; background-color:rgba(128,128,128,0.04); border:1px solid rgba(128,128,128,0.15); border-radius:4px; font-size:10px;">
  <tr style="color:gray; font-size:8px; background-color:rgba(128,128,128,0.02);">
    <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); width:25%;">美 10년<br>(4.75%)</th>
    <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); border-left:1px solid rgba(128,128,128,0.15); width:25%;">美 30년<br>(5.20%)</th>
    <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); border-left:1px solid rgba(128,128,128,0.15); width:25%;">WTI 원유<br>(120)</th>
    <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); border-left:1px solid rgba(128,128,128,0.15); width:25%;">구리 가격<br>(5.0)</th>
  </tr>
  <tr style="font-weight:bold;">
    <td style="padding:6px; white-space:nowrap;">{us10_status} {us10_txt}</td>
    <td style="padding:6px; border-left:1px solid rgba(128,128,128,0.15); white-space:nowrap;">{us30_status} {us30_txt}</td>
    <td style="padding:6px; border-left:1px solid rgba(128,128,128,0.15); white-space:nowrap;">{wti_status} {wti_txt}</td>
    <td style="padding:6px; border-left:1px solid rgba(128,128,128,0.15); white-space:nowrap;">{copper_status} {copper_txt}</td>
  </tr>
</table>
"""
st.markdown(macro_table_html, unsafe_allow_html=True)


# 3. 엔비디아 지표 (🚨 안전한 모바일용 테이블 정렬 구조)
st.subheader("🍏 엔비디아 지표")
if nvda_price:
    nvda_status = "🟢" if nvda_drawdown > -10 else ("🟡" if nvda_drawdown > -20 else "🔴")
    nvda_table_html = f"""
    <table style="width:100%; border-collapse:collapse; text-align:center; background-color:rgba(128,128,128,0.04); border:1px solid rgba(128,128,128,0.15); border-radius:4px; font-size:10px;">
      <tr style="color:gray; font-size:8px; background-color:rgba(128,128,128,0.02);">
        <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); width:33%;">현재가</th>
        <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); border-left:1px solid rgba(128,128,128,0.15); width:33%;">전고점 (ATH)</th>
        <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); border-left:1px solid rgba(128,128,128,0.15); width:34%;">ATH 대비 (-20%)</th>
      </tr>
      <tr style="font-weight:bold;">
        <td style="padding:6px;">${nvda_price:.2f}</td>
        <td style="padding:6px; border-left:1px solid rgba(128,128,128,0.15);">${nvda_ath:.2f}</td>
        <td style="padding:6px; border-left:1px solid rgba(128,128,128,0.15); white-space:nowrap;">{nvda_status} {nvda_drawdown:.2f}%</td>
      </tr>
    </table>
    """
    st.markdown(nvda_table_html, unsafe_allow_html=True)

# 차트 탭 (인덱스로 확실하게 차트 구분 분리)
t1, t2, t3 = st.tabs(["NVDA", "삼성전자", "TSMC"])
with t1:
    if nvda_hist is not None: st.line_chart(nvda_hist["Close"], height=100)
with t2:
    samsung_hist = get_history("005930.KS")
    if samsung_hist is not None: st.line_chart(samsung_hist["Close"], height=100)
with t3:
    tsmc_hist = get_history("TSM")
    if tsmc_hist is not None: st.line_chart(tsmc_hist["Close"], height=100)


# 4. 📊 밸류에이션 점검 섹션 (🚨 안전한 모바일용 테이블 정렬 구조)
st.markdown("<hr style='margin: 10px 0; border:0; border-top:1px dashed rgba(128,128,128,0.2);'/>", unsafe_allow_html=True)
st.subheader("📊 밸류에이션 점검 (기준: 비율 1.0 미만)")

# [선행 PER 영역]
st.markdown("#### ⏩ 12M 선행(Forward) PER")
f_status = "🟢안정" if forward_ratio < 0.7 else ("🟡주의" if forward_ratio < 1.0 else "🔴고평가")
f_table_html = f"""
<table style="width:100%; border-collapse:collapse; text-align:center; background-color:rgba(128,128,128,0.04); border:1px solid rgba(128,128,128,0.15); border-radius:4px; font-size:10px;">
  <tr style="color:gray; font-size:8px; background-color:rgba(128,128,128,0.02);">
    <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); width:33%;">삼성 선행</th>
    <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); border-left:1px solid rgba(128,128,128,0.15); width:33%;">TSMC 선행</th>
    <th style="padding:4px; border-bottom:1px solid rgba(128,128,128,0.15); border-left:1px solid rgba(128,128,128,0.15); width:34%;">비율 (상태)</th>
  </tr>
  <tr style="font-weight:bold;">
    <td style="padding:6px;">{samsung_f_pe:.2f}</td>
