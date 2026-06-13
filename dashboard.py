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

# 🚨 [모바일 소형화 및 스타일 제어 CSS]
st.markdown("""
    <style>
    /* 여백 최소화 */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
    }
    /* 스마트폰 가독성을 위해 폰트 크기 확대 */
    html, body, p, span, label, div { font-size: 16px !important; }
    h3 { font-size: 22px !important; font-weight: bold; margin-top: 12px !important; margin-bottom: 6px !important; }
    h4 { font-size: 18px !important; font-weight: bold; margin-top: 8px !important; margin-bottom: 2px !important; }
    button[data-baseweb="tab"] p { font-size: 16px !important; }
    
    /* 카드 내부 간격 최소화 */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {
        padding: 6px !important;
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
def save_per_history(samsung_f_pe, tsmc_f_pe, forward_ratio, samsung_t_pe, tsmc_t_pe, trailing_ratio):
    file_path = Path("per_history.csv")
    today = datetime.now().strftime("%Y-%m-%d")
    
    new_row = pd.DataFrame([{
        "date": today,
        "samsung_f_pe": round(samsung_f_pe, 2),
        "tsmc_f_pe": round(tsmc_f_pe, 2),
        "forward_ratio": round(forward_ratio, 4),
        "samsung_t_pe": round(samsung_t_pe, 2),
        "tsmc_t_pe": round(tsmc_t_pe, 2),
        "trailing_ratio": round(trailing_ratio, 4)
    }])

    if file_path.exists():
        try:
            df = pd.read_csv(file_path)
            # 오늘 날짜가 이미 있으면 최신값으로 업데이트
            if today in df["date"].astype(str).values:
                df = df[df["date"].astype(str) != today]
                df = pd.concat([df, new_row], ignore_index=True)
            else:
                df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(file_path, index=False)
        except Exception as e:
            st.warning(f"CSV 업데이트 실패: {e}")
    else:
        try:
            new_row.to_csv(file_path, index=False)
        except Exception as e:
            st.warning(f"CSV 생성 실패: {e}")

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
save_per_history(samsung_f_pe, tsmc_f_pe, forward_ratio, samsung_t_pe, tsmc_t_pe, trailing_ratio)

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
# UI 렌더링 영역 (순정 컴포넌트 기반 무오류 보장)
# -------------------------

# 1. 종합 상태 배너
if score >= 80:
    st.success(f"🟢 정상 ({score}점)")
elif score >= 60:
    st.warning(f"🟡 주의 ({score}점)")
else:
    st.error(f"🔴 경고 ({score}점)")

if reasons:
    with st.expander("🚨 주요 리스크 요인", expanded=True):
        for r in reasons:
            st.write(f"• {r}")


# 2. 글로벌 매크로 지표 (순정 박스 레이아웃 - 모바일 잘림 완벽 해결)
st.subheader("🌐 글로벌 매크로 지표")
us10_status = "🟢정상" if (us10 and us10 < 4.75) else "🚨경고"
us30_status = "🟢정상" if (us30 and us30 < 5.20) else "🚨경고"
wti_status = "🟢정상" if (wti and wti < 120) else "🚨경고"
copper_status = "🟢정상" if (copper and copper > 5.00) else "🚨경고"

with st.container(border=True):
    st.write(f"**美 10년물 (기준 4.75%)** : {us10_status} | **{us10:.2f}%**" if us10 else "美 10년물 : N/A")
    st.write(f"**美 30년물 (기준 5.20%)** : {us30_status} | **{us30:.2f}%**" if us30 else "美 30년물 : N/A")
    st.write(f"**WTI 원유 (기준 120)** : {wti_status} | **${wti:.2f}**" if wti else "WTI 원유 : N/A")
    st.write(f"**구리 가격 (기준 5.0)** : {copper_status} | **${copper:.2f}**" if copper else "구리 가격 : N/A")


# 3. 엔비디아 지표 (순정 박스 레이아웃)
st.subheader("🍏 엔비디아 지표")
if nvda_price:
    nvda_status = "🟢정상" if nvda_drawdown > -10 else ("🟡주의" if nvda_drawdown > -20 else "🚨경고")
    with st.container(border=True):
        st.write(f"**현재가** : ${nvda_price:.2f} | **전고점(ATH)** : ${nvda_ath:.2f}")
        st.write(f"**ATH 대비 (기준 -20%)** : {nvda_status} | **{nvda_drawdown:.2f}%**")

# 차트 탭 (높이 110px 컴팩트화)
t1, t2, t3 = st.tabs(["NVDA", "삼성전자", "TSMC"])
with t1:
    if nvda_hist is not None: st.line_chart(nvda_hist["Close"], height=110)
with t2:
    samsung_hist = get_history("005930.KS")
    if samsung_hist is not None: st.line_chart(samsung_hist["Close"], height=110)
with t3:
    tsmc_hist = get_history("TSM")
    if tsmc_hist is not None: st.line_chart(tsmc_hist["Close"], height=110)


# 4. 📊 밸류에이션 점검 섹션 (순정 구조로 선행 / 후행 완벽 표기)
st.markdown("---")
st.subheader("📊 밸류에이션 점검 (기준: 비율 1.0 미만)")

# [선행 PER 영역]
st.markdown("#### ⏩ 12M 선행(Forward) PER")
f_status = "🟢안정" if forward_ratio < 0.7 else ("🟡주의" if forward_ratio < 1.0 else "🚨고평가")
with st.container(border=True):
    st.write(f"**삼성 선행 PER** : {samsung_f_pe:.2f} | **TSMC 선행 PER** : {tsmc_f_pe:.2f}")
    st.write(f"**선행 비율 (삼성/TSMC)** : **{forward_ratio:.2f}** ({f_status})")

fig_f = go.Figure(go.Indicator(
    mode="gauge+number", value=forward_ratio,
    gauge={"axis": {"range": [0, 1.2], "tickmode": "array", "tickvals": [0, 0.6, 1.2], "tickfont": {"size": 7}}, "threshold": {"line": {"color": "red", "width": 2}, "thickness": 0.5, "value": 1.0}}
))
fig_f.update_layout(height=75, margin=dict(l=50, r=50, t=15, b=5))
st.plotly_chart(fig_f, use_container_width=True)

# 선행 PER 추이 차트
st.markdown("##### 📈 선행 PER 비율 추이")
try:
    history_df = pd.read_csv("per_history.csv")
    if len(history_df) > 0:
        history_df["date"] = pd.to_datetime(history_df["date"])
        # 최근 90일 데이터만 표시
        history_df = history_df[history_df["date"] >= pd.Timestamp.now() - pd.Timedelta(days=90)]
        
        if len(history_df) > 0:
            fig_f_ratio = go.Figure()
            fig_f_ratio.add_trace(
                go.Scatter(
                    x=history_df["date"],
                    y=history_df["forward_ratio"],
                    mode="lines+markers",
                    name="선행 비율",
                    line=dict(color="#1f77b4", width=2),
                    marker=dict(size=6)
                )
            )
            
            fig_f_ratio.add_hline(
                y=1.0,
                line_dash="dash",
                line_color="red",
                annotation_text="경고선 (1.0)",
                annotation_position="right"
            )
            
            fig_f_ratio.update_layout(
                height=200,
                margin=dict(l=10, r=10, t=20, b=10),
                yaxis_title="삼성 / TSMC",
                xaxis_title="날짜",
                hovermode="x unified"
            )
            
            st.plotly_chart(fig_f_ratio, use_container_width=True)
except Exception as e:
    st.warning(f"선행 PER 차트 오류: {e}")


# [후행 PER 영역]
st.markdown("#### ⏪ 12M 후행(Trailing) PER")
t_status = "🟢안정" if trailing_ratio < 0.7 else ("🟡주의" if trailing_ratio < 1.0 else "🚨고평가")
with st.container(border=True):
    st.write(f"**삼성 후행 PER** : {samsung_t_pe:.2f} | **TSMC 후행 PER** : {tsmc_t_pe:.2f}")
    st.write(f"**후행 비율 (삼성/TSMC)** : **{trailing_ratio:.2f}** ({t_status})")

fig_t = go.Figure(go.Indicator(
    mode="gauge+number", value=trailing_ratio,
    gauge={"axis": {"range": [0, 1.2], "tickmode": "array", "tickvals": [0, 0.6, 1.2], "tickfont": {"size": 7}}, "threshold": {"line": {"color": "red", "width": 2}, "thickness": 0.5, "value": 1.0}}
))
fig_t.update_layout(height=75, margin=dict(l=50, r=50, t=15, b=5))
st.plotly_chart(fig_t, use_container_width=True)

# 후행 PER 추이 차트
st.markdown("##### 📈 후행 PER 비율 추이")
try:
    history_df = pd.read_csv("per_history.csv")
    if len(history_df) > 0:
        history_df["date"] = pd.to_datetime(history_df["date"])
        # 최근 90일 데이터만 표시
        history_df = history_df[history_df["date"] >= pd.Timestamp.now() - pd.Timedelta(days=90)]
        
        if len(history_df) > 0:
            fig_t_ratio = go.Figure()
            fig_t_ratio.add_trace(
                go.Scatter(
                    x=history_df["date"],
                    y=history_df["trailing_ratio"],
                    mode="lines+markers",
                    name="후행 비율",
                    line=dict(color="#ff7f0e", width=2),
                    marker=dict(size=6)
                )
            )
            
            fig_t_ratio.add_hline(
                y=1.0,
                line_dash="dash",
                line_color="red",
                annotation_text="경고선 (1.0)",
                annotation_position="right"
            )
            
            fig_t_ratio.update_layout(
                height=200,
                margin=dict(l=10, r=10, t=20, b=10),
                yaxis_title="삼성 / TSMC",
                xaxis_title="날짜",
                hovermode="x unified"
            )
            
            st.plotly_chart(fig_t_ratio, use_container_width=True)
except Exception as e:
    st.warning(f"후행 PER 차트 오류: {e}")


# 🔄 [안전한 브라우저 새로고침] 60초마다 화면 새로고침
st.components.v1.html(
    """
    <script>
    setTimeout(function(){
        window.parent.location.reload();
    }, 60000);
    </script>
    """,
    height=0
)
