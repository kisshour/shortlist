import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import requests

# --- [1. 기본 설정] ---
st.set_page_config(page_title="RSI 숏 바스켓 통합본", layout="wide")

TELEGRAM_TOKEN = "8378935636:AAH7JJmu7_B_YQ4P6CQ7TcAh3YYeG4ANTBU"
CHAT_ID = "-5285479874"
CMC_API_KEY = "01bbeb036590498d97c169346dc19782"

short_candidates = [
    'JUP', 'WLD', 'FIL', 'FF', 'ENS', 'ZRO', 'ONDO', 'EIGEN', 
    'KITE', 'XPL', 'TRUMP', 'BARD', 'KAITO', '2Z', 'PUMP', 'JTO'
]

# 텔레그램 중복 알림 방지용 세션 상태 설정
if 'last_alert_times' not in st.session_state:
    st.session_state.last_alert_times = {}

exchange = ccxt.binance({'options': {'defaultType': 'future'}})

# --- [2. 기능 함수] ---
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': CHAT_ID, 'text': msg})
    except: pass

def fetch_data(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        c = df['c']
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(com=13).mean()
        loss = (-delta.clip(upper=0)).ewm(com=13).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))
        return round(rsi.iloc[-1], 2), round(rsi.iloc[-2], 2), c.iloc[-1]
    except: return None, None, None

# --- [3. 웹 UI 구성] ---
st.title("🚀 v18.6 통합 숏 바스켓 대시보드")
st.info("웹 모니터링 + 텔레그램 그룹방 알림이 동시에 작동 중입니다.")

placeholder = st.empty()

# --- [4. 메인 감시 루프] ---
while True:
    with placeholder.container():
        now_dt = datetime.now()
        curr_time = now_dt.strftime('%H:%M:%S')
        st.subheader(f"⏱️ 실시간 데이터 (최종 업데이트: {curr_time})")

        data_list = []
        all_symbols = ['BTC/USDT', 'ETH/USDT'] + [s + '/USDT' for s in short_candidates]

        for s in all_symbols:
            rsi, rsi_prev, price = fetch_data(s)
            if rsi is not None:
                base_sym = s.split('/')[0]
                status = "⚪ WAIT"
                if rsi >= 70: status = "🔴 SHORT"
                elif rsi <= 30: status = "🟢 LONG"

                data_list.append({
                    "Symbol": base_sym,
                    "Price": f"${price:,.4f}" if price < 1 else f"${price:,.2f}",
                    "RSI (15m)": rsi,
                    "Status": status
                })

                # --- 텔레그램 알림 로직 통합 ---
                if base_sym in short_candidates:
                    direc = None
                    if rsi >= 70: direc = "SHORT"
                    elif rsi <= 30: direc = "LONG"

                    if direc:
                        l_key = (base_sym, direc)
                        last_time = st.session_state.last_alert_times.get(l_key)
                        
                        # 1시간 내 중복 알림 방지
                        if last_time is None or (now_dt - last_time) > timedelta(hours=1):
                            msg = f"[{curr_time}] {base_sym}\nPrice: ${price}\nRSI: {rsi}\nStatus: {direc} 진입 구간"
                            send_telegram(msg)
                            st.session_state.last_alert_times[l_key] = now_dt

        # 화면 출력
        df = pd.DataFrame(data_list)
        st.table(df.sort_values(by="RSI (15m)", ascending=False).reset_index(drop=True))
        
        # 새로고침 간격 (30초)
        time.sleep(30)