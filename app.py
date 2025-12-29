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

if 'last_alert_times' not in st.session_state:
    st.session_state.last_alert_times = {}

# 바이낸스 선물 거래소 연결
exchange = ccxt.binance({'options': {'defaultType': 'future'}, 'enableRateLimit': True})

# --- [2. 기능 함수] ---
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': CHAT_ID, 'text': msg}, timeout=5)
    except: pass

def fetch_data(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        if not bars: return None, None, None
        df = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        c = df['c']
        delta = c.diff()
        gain = delta.clip(lower=0).ewm(com=13).mean()
        loss = (-delta.clip(upper=0)).ewm(com=13).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))
        return round(rsi.iloc[-1], 2), round(rsi.iloc[-2], 2), c.iloc[-1]
    except Exception as e:
        return None, None, None

# --- [3. 웹 UI 구성] ---
st.title("🚀 v18.7 통합 숏 바스켓 대시보드")

placeholder = st.empty()

# --- [4. 메인 감시 루프] ---
while True:
    with placeholder.container():
        now_dt = datetime.now()
        curr_time = now_dt.strftime('%H:%M:%S')
        st.subheader(f"⏱️ 실시간 데이터 (최종 업데이트: {curr_time})")

        data_list = []
        all_symbols = ['BTC/USDT', 'ETH/USDT'] + [s + '/USDT' for s in short_candidates]

        # 데이터 수집 시 프로그레스 바나 상태 메시지 표시
        with st.spinner('데이터를 수집하고 있습니다...'):
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

                    # 텔레그램 알림 로직
                    if base_sym in short_candidates:
                        direc = "SHORT" if rsi >= 70 else ("LONG" if rsi <= 30 else None)
                        if direc:
                            l_key = (base_sym, direc)
                            last_time = st.session_state.last_alert_times.get(l_key)
                            if last_time is None or (now_dt - last_time) > timedelta(hours=1):
                                msg = f"[{curr_time}] {base_sym}\nPrice: ${price}\nRSI: {rsi}\nStatus: {direc} 진입"
                                send_telegram(msg)
                                st.session_state.last_alert_times[l_key] = now_dt
                time.sleep(0.05) # 거래소 요청 제한 방지

        # --- [에러 방지 핵심] 데이터가 있을 때만 정렬 및 출력 ---
        if data_list:
            df = pd.DataFrame(data_list)
            # 컬럼명이 확실히 존재하는지 체크 후 정렬
            if "RSI (15m)" in df.columns:
                st.table(df.sort_values(by="RSI (15m)", ascending=False).reset_index(drop=True))
            else:
                st.write("데이터 컬럼을 생성하는 중 오류가 발생했습니다.")
        else:
            st.warning("거래소에서 데이터를 가져오지 못했습니다. 잠시 후 다시 시도합니다.")
        
        time.sleep(30)
