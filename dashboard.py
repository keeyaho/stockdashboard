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
# 💡 실시간 반영을 위해 캐시 유지 시간(ttl)을 3600초(1시간)에서 60초(1분)로 단축했습니다.
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

def get_pe(ticker):
    info = get_info(ticker)
    if not info:
        return None
    return info.get("forwardPE") or info.get("trailingPE")


# -------------------------
# ⚡ 자동 갱신 프래그먼트 함수
# -------------------------
# @st.fragment를 사용하면 페이지 전체가 아닌 이 함수 내부의 UI만 쏙 새로고침됩니다.
@st.fragment
def run_dashboard(interval_seconds=60):
    
    # -------------------------
    # 데이터 수집 (매 실행마다 최신화)
    # -------------------------
    us10 = get_latest("^TNX")
    us30 = get_latest("^TYX")
    wti = get_latest("CL=F")
    copper = get_latest("HG=F")

    # 엔비디아 데이터 처리
    nvda_hist = get_history("NVDA")
    if nvda_hist is not None and not nvda_hist.empty:
        nvda_price = float(nvda_hist["Close"].iloc[-1])
        nvda_ath = float(nvda_hist["High"].max())
        nvda_drawdown = ((nvda_price - nvda_ath) / nvda_ath) * 100
    else:
        nvda_price, nvda_ath, nvda_drawdown = None, None, None

    # 삼성전자 / TSMC PER 비율
    samsung_pe = get_pe("005930.KS")
    tsmc_pe = get_pe("TSM")
    ratio = samsung_pe / tsmc_pe if samsung_pe and tsmc_pe else None

    # -------------------------
    # 리스크 점수 계산 및 감점 로직
    # -------------------------
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

    # 💡 경기 침체 신호: 구리 가격이 $3.5 이하로 내려갈 때 경고로 수정
    if copper and copper <= 3.5:
        score -= 10
        reasons.append(f"구리 가격 경고 (${copper:.2f})")

    if nvda_drawdown and nvda_drawdown <= -20:
        score -= 20
        reasons.append(f"NVDA 경고 ({nvda_drawdown:.2f}%)")

    if ratio:
        if ratio >= 1:
            score -= 30
            reasons.append(f"삼성 PER ≥ TSMC PER (비율: {ratio:.2f})")
        elif ratio >= 0.7:
            score -= 15
            reasons.append(f"삼성 PER이 TSMC PER에 근접 (비율: {ratio:.2f})")

    # -------------------------
    # UI 렌더링 시작
    # -------------------------
    
    # 1. 최상단 상태 바
    if score >= 80:
        st.success(f"🟢 정상 ({score}점)")
    elif score >= 60:
        st.warning(f"🟡 주의 ({score}점)")
    else:
        st.error(f"🔴 경고 ({score}점)")

      # 2. 매크로 지표 섹션
    st.subheader("🌐 글로벌 매크로 지표")
    c1, c2, c3, c4 = st.columns(4)
    
    # 미국 10년물 (기준: 4.75%)
    if us10:
        us10_delta = f"기준 4.75% 미만 (정상)" if us10 < 4.75 else f"🚨 기준 4.75% 이상 (경고)"
        # 기준치를 넘으면 빨간색(inverse), 안 넘으면 초록색(normal)으로 표시
        c1.metric(
            label="미국 10년물 금리", 
            value=f"{us10:.2f}%", 
            delta=us10_delta, 
            delta_color="inverse" if us10 >= 4.75 else "normal"
        )
    else:
        c1.metric("미국 10년물 금리", "N/A")

    # 미국 30년물 (기준: 5.20%)
    if us30:
        us30_delta = f"기준 5.20% 미만 (정상)" if us30 < 5.20 else f"🚨 기준 5.20% 이상 (경고)"
        c2.metric(
            label="미국 30년물 금리", 
            value=f"{us30:.2f}%", 
            delta=us30_delta, 
            delta_color="inverse" if us30 >= 5.20 else "normal"
        )
    else:
        c2.metric("미국 30년물 금리", "N/A")

    # WTI 원유 (기준: $120)
    if wti:
        wti_delta = f"기준 $120 미만 (정상)" if wti < 120 else f"🚨 기준 $120 이상 (경고)"
        c3.metric(
            label="WTI 원유", 
            value=f"${wti:.2f}", 
            delta=wti_delta, 
            delta_color="inverse" if wti >= 120 else "normal"
        )
    else:
        c3.metric("WTI 원유", "N/A")

    # 닥터 코퍼 구리 (기준: $3.50)
    if copper:
        # 구리는 가격이 떨어지면 위험하므로 로직 반대
        copper_delta = f"기준 $3.50 초과 (정상)" if copper > 3.50 else f"🚨 기준 $3.50 이하 (경고)"
        c4.metric(
            label="닥터 코퍼 (구리)", 
            value=f"${copper:.2f}", 
            delta=copper_delta, 
            delta_color="normal" if copper > 3.50 else "inverse"
        )
    else:
        c4.metric("닥터 코퍼 (구리)", "N/A")

    # 3. 엔비디아 및 주가 차트 섹션
    st.subheader("엔비디아")
    if nvda_price:
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("현재가", f"${nvda_price:.2f}")
        mc2.metric("ATH", f"${nvda_ath:.2f}")
        mc3.metric("ATH 대비", f"{nvda_drawdown:.2f}%")

    tabs = st.tabs(["NVDA", "삼성전자", "TSMC"])
    with tabs[0]:
        if nvda_hist is not None:
            st.line_chart(nvda_hist["Close"])
    with tabs[1]:
        samsung_hist = get_history("005930.KS")
        if samsung_hist is not None:
            st.line_chart(samsung_hist["Close"])
    with tabs[2]:
        tsmc_hist = get_history("TSM")
        if tsmc_hist is not None:
            st.line_chart(tsmc_hist["Close"])

    if nvda_drawdown is not None:
        if nvda_drawdown <= -20:
            st.error(f"🔴 전고점 대비 {nvda_drawdown:.2f}%")
        elif nvda_drawdown <= -10:
            st.warning(f"🟡 전고점 대비 {nvda_drawdown:.2f}%")
        else:
            st.success(f"🟢 전고점 대비 {nvda_drawdown:.2f}%")

    # 4. 버블 점검 섹션
    st.markdown("---")
    st.subheader("버블 점검")
    bc1, bc2, bc3 = st.columns(3)
    bc1.metric("삼성전자 PER", f"{samsung_pe:.2f}" if samsung_pe else "N/A")
    bc2.metric("TSMC PER", f"{tsmc_pe:.2f}" if tsmc_pe else "N/A")
    bc3.metric("PER 비율", f"{ratio:.2f}" if ratio else "N/A")

    if ratio:
        if ratio >= 1:
            st.error("🔴 삼성 PER ≥ TSMC PER")
        elif ratio >= 0.7:
            st.warning("🟡 삼성 PER이 TSMC PER에 근접")
        else:
            st.success("🟢 정상")

    # 누락되었던 게이지 차트 정상 출력 처리
    if ratio:
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=ratio,
                title={"text": "삼성 PER / TSMC PER"},
                gauge={
                    "axis": {"range": [0, 1.2]},
                    "threshold": {
                        "line": {"color": "red", "width": 4},
                        "thickness": 0.75,
                        "value": 1.0
                    }
                }
            )
        )
        fig.update_layout(height=250)
        st.plotly_chart(fig, use_container_width=True)

    # 5. 최종 감점 사유 리스트
    st.markdown("---")
    st.subheader("🚨 실시간 감점 요인")
    if len(reasons) == 0:
        st.success("현재 매도 신호 없음")
    else:
        for r in reasons:
            st.warning(r)

    # ⏱️ 대기 후 재실행 로직
    # 지정한 시간(초)만큼 일시정지 후 브라우저에 리런 신호를 보냅니다.
    time.sleep(interval_seconds)
    st.rerun()

# -------------------------
# 프로그램 메인 실행
# -------------------------
# 기본 자동 새로고침 주기를 60초(1분)로 설정하여 대시보드를 구동합니다.
run_dashboard(interval_seconds=60)
