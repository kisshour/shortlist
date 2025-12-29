import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import requests

# --- [1. 기본 설정] ---
st.set_page_config(page_title="RSI 숏 바스켓 진단모드", layout="wide")

TELEGRAM_TOKEN = "8378935636:AAH7JJmu7_B_YQ4P6CQ7TcAh3YYeG4ANTBU"
CHAT_ID = "-5285479874"

# 16종 리스트 (OP 제외, JTO 포함)
short_candidates = [
    'JUP', 'WLD', 'FIL', 'FF', 'ENS', 'ZRO', 'ONDO', 'EIGEN', 
    'KITE', 'XPL', 'TRUMP', 'BARD', 'KAITO', '2Z', 'PUMP', 'JTO'
]

if 'last_alert_times' not in st.session_state:
    st.session_state.last_alert_times = {}

# 바이낸스 연결 설정 (IP 차단 대비 타임아웃 강화)
exchange = ccxt.binance({
    'options': {'defaultType': 'future'},
    'enableRateLimit': True,
    'timeout': 30000
})

# --- [2. 기능 함수] ---
def fetch_data(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        if not bars or len(bars) < 2: return None, None, None
        df_ohlcv = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        c = df_ohlcv['c']
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(com=13).mean()
        loss = (-delta.clip(upper=0)).ewm(com=13).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))
        return round(rsi.iloc[-1], 2), round(rsi.iloc[-2], 2), c.iloc[-1]
    except Exception as e:
        return None, None, None

# --- [3. 웹 UI 구성] ---
st.title("🛡️ v18.9 숏 바스켓 (KeyError 해결 버전)")

# [진단 섹션] 바이낸스 연결 확인
with st.expander("📡 서버 연결 상태 진단 (필독)"):
    try:
        status = exchange.fetch_status()
        st.success(f"바이낸스 서버 연결 성공! (상태: {status.get('status')})")
    except Exception as e:
        st.error(f"바이낸스 연결 실패: {e}")
        st.warning("⚠️ Streamlit 서버 IP가 바이낸스에 의해 차단되었을 가능성이 99%입니다.")
        st.info("이 경우 가격이 모두 N/A로 표시되지만, 빨간 에러 화면은 나타나지 않습니다.")

placeholder = st.empty()

# --- [4. 메인 루프] ---
while True:
    with placeholder.container():
        now_dt = datetime.now()
        st.subheader(f"⏱️ 마지막 갱신: {now_dt.strftime('%H:%M:%S')}")

        # [핵심] 빈 데이터프레임을 미리 구조화하여 생성 (KeyError 방지)
        columns = ["Symbol", "Price", "RSI (15m)", "Status"]
        data_list = []

        all_symbols = ['BTC/USDT', 'ETH/USDT'] + [s + '/USDT' for s in short_candidates]

        with st.spinner('데이터 수집 중...'):
            for s in all_symbols:
                rsi, rsi_prev, price = fetch_data(s)
                base_sym = s.split('/')[0]
                
                # 데이터가 없어도 N/A로 행을 추가하여 구조 유지
                row = {
                    "Symbol": base_sym,
                    "Price": f"${price:,.4f}" if price else "N/A",
                    "RSI (15m)": rsi if rsi is not None else 0.0,
                    "Status": "🔴 SHORT" if rsi and rsi >= 70 else ("🟢 LONG" if rsi and rsi <= 30 else "⚪ WAIT")
                }
                data_list.append(row)
                
                # 텔레그램 알림 (데이터가 정상일 때만)
                if rsi and base_sym in short_candidates:
                    direc = "SHORT" if rsi >= 70 else ("LONG" if rsi <= 30 else None)
                    if direc:
                        l_key = (base_sym, direc)
                        last_time = st.session_state.last_alert_times.get(l_key)
                        if last_time is None or (now_dt - last_time) > timedelta(hours=1):
                            msg = f"[{now_dt.strftime('%H:%M')}] {base_sym}\nPrice: ${price}\nRSI: {rsi}"
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                          data={'chat_id': CHAT_ID, 'text': msg})
                            st.session_state.last_alert_times[l_key] = now_dt
                time.sleep(0.05)

        # 데이터프레임 생성 (컬럼 강제 지정)
        df = pd.DataFrame(data_list, columns=columns)
        
        # [정렬 및 출력] 데이터가 0인 상태여도 컬럼이 존재하므로 에러 없음
        st.table(df.sort_values(by="RSI (15m)", ascending=False).reset_index(drop=True))
        
        st.info("💡 30초마다 자동으로 새로고침됩니다.")
        time.sleep(30)
