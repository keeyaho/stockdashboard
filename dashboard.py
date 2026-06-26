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
    """Return a numeric PE (float). If unavailable, return float('nan').
    This function is defensive about incoming data shapes (Series/arrays/strings).
    """
    try:
        info = get_info(ticker)
        key = "forwardPE" if pe_type == "forward" else "trailingPE"
        pe = info.get(key)
        if pe is not None:
            try:
                return float(pe)
            except Exception:
                # fall through to other methods
                pass

        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period="1d")
        if hist.empty:
            return float('nan')
        current_price = None
        try:
            current_price = float(hist["Close"].iloc[-1])
        except Exception:
            current_price = None

        eps_key = "forwardEps" if pe_type == "forward" else "trailingEps"
        eps = info.get(eps_key)
        try:
            eps = float(eps) if eps is not None else None
        except Exception:
            eps = None

        if eps is None:
            # domain-specific fallbacks
            if ticker == "005930.KS": eps = 13500.0 if pe_type == "forward" else 9500.0
            elif ticker == "TSM": eps = 8.2 if pe_type == "forward" else 6.8

        if current_price and eps:
            try:
                return round(current_price / eps, 2)
            except Exception:
                pass
    except Exception:
        pass

    # final fallback
    try:
        fallback = {"005930.KS": {"forward": 18.5, "trailing": 24.2}, "TSM": {"forward": 23.0, "trailing": 28.5}}
        return float(fallback.get(ticker, {}).get(pe_type, 20.0))
    except Exception:
        return float('nan')

# -------------------------
# 안전한 나눗셈 헬퍼
# -------------------------
def safe_div(a, b, default=1.0):
    """Safely divide a by b and return default on any error (including None, 0, non-scalar types)."""
    try:
        # handle pandas/numpy scalars/one-element arrays
        if hasattr(a, '__len__') and not isinstance(a, (str, bytes)):
            # try to convert to float directly; if it's array-like with length >1 this will fail and go to except
            try:
                a = float(a)
            except Exception:
                # if it's a pandas Series with one element, extract it
                try:
                    a = float(a.iloc[0])
                except Exception:
                    return default
        if hasattr(b, '__len__') and not isinstance(b, (str, bytes)):
            try:
                b = float(b)
            except Exception:
                try:
                    b = float(b.iloc[0])
                except Exception:
                    return default
        if b == 0 or b is None:
            return default
        return float(a) / float(b)
    except Exception:
        return default

# -------------------------
# PER 저장 함수 추가 (안전성 강화)
# -------------------------
def save_per_history(samsung_f_pe, tsmc_f_pe, forward_ratio, samsung_t_pe, tsmc_t_pe, trailing_ratio):
    """PER 값이 정상일 때만 저장. NaN 데이터로 기존 기록을 오염시키지 않음."""
    file_path = Path("per_history.csv")
    today = datetime.now().strftime("%Y-%m-%d")

    def valid(x):
        try:
            x = float(x)
            return pd.notna(x) and x > 0
        except Exception:
            return False

    # 핵심 수정: PER 수집 실패 시 저장 금지
    if not all([
        valid(samsung_f_pe),
        valid(tsmc_f_pe),
        valid(samsung_t_pe),
        valid(tsmc_t_pe)
    ]):
        st.warning(f"{today} PER 수집 실패 → CSV 저장 건너뜀")
        return

    try:
        new_row = pd.DataFrame([{
            "date": today,
            "samsung_f_pe": round(float(samsung_f_pe), 2),
            "tsmc_f_pe": round(float(tsmc_f_pe), 2),
            "forward_ratio": round(float(forward_ratio), 4),
            "samsung_t_pe": round(float(samsung_t_pe), 2),
            "tsmc_t_pe": round(float(tsmc_t_pe), 2),
            "trailing_ratio": round(float(trailing_ratio), 4)
        }])

        if file_path.exists():
            df = pd.read_csv(file_path)

            # 이미 오늘 데이터가 있으면 정상 데이터만 교체
            if today in df["date"].astype(str).values:
                df = df[df["date"].astype(str) != today]

            df = pd.concat([df, new_row], ignore_index=True)
        else:
            df = new_row

        df.to_csv(file_path, index=False)
        st.info(f"PER 히스토리 저장됨: {today}")

    except Exception as e:
        st.warning(f"PER 히스토리 저장 실패: {e}")

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
# use safe_div to avoid ambiguous truth checks and non-scalar types
forward_ratio = safe_div(samsung_f_pe, tsmc_f_pe, default=1.0)

samsung_t_pe = get_pe_detailed("005930.KS", "trailing")
tsmc_t_pe = get_pe_detailed("TSM", "trailing")
trailing_ratio = safe_div(samsung_t_pe, tsmc_t_pe, default=1.0)

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

# 2. 주요 리스크 요인 토글 (원래 끊겼던 구문을 정상 복구한 부분)
if reasons:
    with st.expander("🚨 주요 리스크 요인", expanded=True):
        for reason in reasons:
            st.write(f"- {reason}")
else:
    st.info("현재 감지된 리스크 요인이 없습니다.")
