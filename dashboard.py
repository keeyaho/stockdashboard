import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import time

# 1. 페이지 설정
st.set_page_config(
    page_title="AI 사이클 관제센터 - 매도 점검",
    layout="wide"
)

st.title("📈 매도 점검")
st.caption("AI 사이클 관제센터 — 1분 주기 자동 갱신 중")

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

# 선행(Forward) 및 후행(Trailing) PER을 명확히 구분하여 가져오는 고도화 함수
@st.cache_data(ttl=60)
def get_pe_detailed(ticker, pe_type="forward"):
    info = get_info(ticker)
    key = "forwardPE" if pe_type == "forward" else "trailingPE"
    pe = info.get(key)
    
    if pe:
        return float(pe)
        
    # [안정 장치] .info 호출이 막혔을 때 실시간 주가와 최근 실적 기반 직접 역산
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

    # 엔비디아 데이터 처리 (💡 오타 수정 완료)
    nvda_hist = get_history("NVDA")
    if nvda_hist is not None and not nvda_hist.empty:
        nvda_price = float(nvda_hist["Close"].iloc[-1])
        nvda_ath = float(nvda_hist["High"].max())  # 이 부분의 문법 에러를 해결했습니다.
        nvda_drawdown = ((nvda_price - nvda_ath) / nvda_ath) * 100
    else:
        nvda_price, nvda_ath, nvda_drawdown = None, None, None

    # 선행 / 후행 PER 데이터 수집
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
        reasons.append(f"삼성 선행 PER ≥ TSMC 선행 PER (비율: {forward_ratio:.2f})")
    elif forward_ratio >= 0.7:
        score -= 15
        reasons.append(f"삼성 선행 PER이 TSMC 선행 PER에 근접 (비율: {forward_ratio:.2f})")

    # -------------------------
    # UI 렌더링 시작
    # -------------------------
    if score >= 80:
        st.success(f"🟢 정상 ({score}점)")
    elif score >= 60:
        st.warning(f"🟡 주의 ({score}점)")
    else:
        st.error(f"🔴 경고 ({score}점)")

    # 매크로 지표 섹션
    st.subheader("🌐 글로벌 매크로 지표")
    c1, c2, c3, c4 = st.columns(4)
    
    if us10:
        us10_delta = "기준 4.75% 미만 (정상)" if us10 < 4.75 else "🚨 기준 4.75% 이상 (경고)"
        c1.metric(label="미국 10년물 금리", value=f"{us10:.2f}%", delta=us10_delta, delta_color="inverse" if us10 >= 4.75 else "normal")
    else:
        c1.metric("미국 10년물 금리", "N/A")

    if us30:
        us30_delta = "기준 5.20% 미만 (정상)" if us30 < 5.20 else "🚨 기준 5.20% 이상 (경고)"
        c2.metric(label="미국 30년물 금리", value=f"{us30:.2f}%", delta=us30_delta, delta_color="inverse" if us30 >= 5.20 else "normal")
    else:
        c2.metric("미국 30년물 금리", "N/A")

    if wti:
        wti_delta = "기준 $120 미만 (정상)" if wti < 120 else "🚨 기준 $120 이상 (경고)"
        c3.metric(label="WTI 원유", value=f"${wti:.2f}", delta=wti_delta, delta_color="inverse" if wti >= 120 else "normal")
    else:
        c3.metric("WTI 원유", "N/A")

    if copper:
        copper_delta = "기준 $5.00 초과 (정상)" if copper > 5.00 else "🚨 기준 $5.00 이하 (경고)"
        c4.metric(label="닥터 코퍼 (구리)", value=f"${copper:.2f}", delta=copper_delta, delta_color="normal" if copper > 5.00 else "inverse")
    else:
        c4.metric("닥터 코퍼 (구리)", "N/A")

    # 엔비디아 섹션
    st.subheader("엔비디아")
    if nvda_price:
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("현재가", f"${nvda_price:.2f}")
        mc2.metric("ATH", f"${nvda_ath:.2f}")
        mc3.metric("ATH 대비", f"{nvda_drawdown:.2f}%")

    tabs = st.tabs(["NVDA", "삼성전자", "TSMC"])
    with tabs[0]:
        if nvda_hist is not None: st.line_chart(nvda_hist["Close"])
    with tabs[1]:
        samsung_hist = get_history("005930.KS")
        if samsung_hist is not None: st.line_chart(samsung_hist["Close"])
    with tabs[2]:
        tsmc_hist = get_history("TSM")
        if tsmc_hist is not None: st.line_chart(tsmc_hist["Close"])

    if nvda_drawdown is not None:
        if nvda_drawdown <= -20:
            st.error(f"🔴 전고점 대비 {nvda_drawdown:.2f}%")
        elif nvda_drawdown <= -10:
            st.warning(f"🟡 전고점 대비 {nvda_drawdown:.2f}%")
        else:
            st.success(f"🟢 전고점 대비 {nvda_drawdown:.2f}%")

    # 밸류에이션 점검 섹션 (선행 vs 후행 PER)
    st.markdown("---")
    st.subheader("📊 밸류에이션 점검 (선행 vs 후행 PER)")
    
    left_pe_col, right_pe_col = st.columns(2)
    
    with left_pe_col:
        st.markdown("#### ⏩ 12M 선행(Forward) PER")
        f_bc1, f_bc2, f_bc3 = st.columns(3)
        f_bc1.metric("삼성전자 선행 PER", f"{samsung_f_pe:.2f}")
        f_bc2.metric("TSMC 선행 PER", f"{tsmc_f_pe:.2f}")
        f_bc3.metric("선행 PER 비율", f"{forward_ratio:.2f}")
        
        if forward_ratio >= 1:
            st.error("🔴 선행 PER 고평가 (삼성 ≥ TSMC)")
        elif forward_ratio >= 0.7:
            st.warning("🟡 선행 PER 근접 주의")
        else:
            st.success("🟢 선행 PER 안정권")
            
        fig_f = go.Figure(go.Indicator(
            mode="gauge+number", value=forward_ratio,
            title={"text": "선행 PER 비율"},
            gauge={"axis": {"range": [0, 1.2]}, "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 1.0}}
        ))
        fig_f.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_f, use_container_width=True)

    with right_pe_col:
        st.markdown("#### ⏪ 12M 후행(Trailing) PER")
        t_bc1, t_bc2, t_bc3 = st.columns(3)
        t_bc1.metric("삼성전자 후행 PER", f"{samsung_t_pe:.2f}")
        t_bc2.metric("TSMC 후행 PER", f"{tsmc_t_pe:.2f}")
        t_bc3.metric("후행 PER 비율", f"{trailing_ratio:.2f}")
        
        if trailing_ratio >= 1:
            st.error("🔴 후행 PER 고평가 (삼성 ≥ TSMC)")
        elif trailing_ratio >= 0.7:
            st.warning("🟡 후행 PER 근접 주의")
        else:
            st.success("🟢 후행 PER 안정권")
            
        fig_t = go.Figure(go.Indicator(
            mode="gauge+number", value=trailing_ratio,
            title={"text": "후행 PER 비율"},
            gauge={"axis": {"range": [0, 1.2]}, "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 1.0}}
        ))
        fig_t.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_t, use_container_width=True)

    # 리스크 요인 리스트
    st.markdown("---")
    st.subheader("🚨 실시간 리스크 요인")
    if len(reasons) == 0:
        st.success("현재 매도 신호가 감지되지 않았습니다. 자산 관리 안정 상태입니다.")
    else:
        for r in reasons:
            st.warning(r)

    # 대기 후 재실행
    time.sleep(interval_seconds)
    st.rerun()

# 프로그램 실행
run_dashboard(interval_seconds=60)
