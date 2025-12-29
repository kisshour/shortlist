import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import requests

# --- [1. 페이지 설정] ---
st.set_page_config(page_title="RSI 숏 바스켓 진단모드", layout="wide")

TELEGRAM_TOKEN = "8378935636:AAH7JJmu7_B_YQ4P6CQ7TcAh3YYeG4ANTBU"
CHAT_ID = "-5285479874"

short_candidates = [
    'JUP', 'WLD', 'FIL', 'FF', 'ENS', 'ZRO', 'ONDO', 'EIGEN', 
    'KITE', 'XPL', 'TRUMP', 'BARD', 'KAITO', '2Z', 'PUMP', 'JTO'
]

if 'last_alert_times' not in st.session_state:
    st.session_state.last_alert_times = {}

# --- [2. 거래소 연결 설정] ---
# IP 차단 대비를 위해 여러 설정을 시도합니다.
exchange = ccxt.binance({
    'options': {'defaultType': 'future'},
    'enableRateLimit': True,
    'timeout': 20000
})

def fetch_data(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        if not bars or len(bars) < 2: return None, None, None
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        c = df['c']
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(com=13).mean()
        loss = (-delta.clip(upper=0)).ewm(com=13).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))
        return round(rsi.iloc[-1], 2), round(rsi.iloc[-2], 2), c.iloc[-1]
    except Exception as e:
        # 에러 발생 시 로그에 기록 (화면엔 안 보임)
        return None, None, str(e)

# --- [3. 웹 UI 구성] ---
st.title("🛡️ v18.8 숏 바스켓 (진단 모드)")

# 시스템 상태 확인란
with st.expander("📡 시스템 연결 상태 확인"):
    try:
        exchange.fetch_status()
        st.success("바이낸스 서버 연결 성공!")
    except Exception as e:
        st.error(f"바이낸스 연결 실패: {e}")
        st.info("💡 힌트: 스트림릿 서버 IP가 바이낸스에 의해 차단되었을 가능성이 높습니다.")

placeholder = st.empty()

# --- [4. 메인 루프] ---
while True:
    with placeholder.container():
        now_dt = datetime.now()
        st.subheader(f"⏱️ 마지막 업데이트: {now_dt.strftime('%H:%M:%S')}")

        data_list = []
        # 테스트를 위해 BTC, ETH 먼저 확인
        all_symbols = ['BTC/USDT', 'ETH/USDT'] + [s + '/USDT' for s in short_candidates]

        with st.spinner('데이터를 불러오는 중...'):
            for s in all_symbols:
                rsi, rsi_prev, price = fetch_data(s)
                base_sym = s.split('/')[0]
                
                if rsi is not None:
                    data_list.append({
                        "Symbol": base_sym,
                        "Price": f"${price:,.4f}",
                        "RSI (15m)": rsi,
                        "Status": "🔴 SHORT" if rsi >= 70 else ("🟢 LONG" if rsi <= 30 else "⚪ WAIT")
                    })
                else:
                    # 데이터 로드 실패 시에도 리스트에 추가하여 KeyError 방지
                    data_list.append({
                        "Symbol": base_sym,
                        "Price": "N/A",
                        "RSI (15m)": 0.0,
                        "Status": "⚠️ Connection Error"
                    })
                time.sleep(0.1)

        # 무조건 데이터프레임 구조를 미리 정의 (KeyError 방지 핵심)
        df = pd.DataFrame(data_list, columns=["Symbol", "Price", "RSI (15m)", "Status"])
        
        # 정렬하여 출력
        st.dataframe(df.sort_values(by="RSI (15m)", ascending=False), use_container_width=True)
        
        st.info("30초마다 자동으로 새로고침됩니다.")
        time.sleep(30)
