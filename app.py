import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import requests

# --- [1. 페이지 설정 및 제목] ---
st.set_page_config(page_title="Shortlist v1.0", layout="wide")
st.title("🚀 Shortlist v1.0")

TELEGRAM_TOKEN = "8378935636:AAH7JJmu7_B_YQ4P6CQ7TcAh3YYeG4ANTBU"
CHAT_ID = "-5285479874"

# 숏 바스켓 리스트
short_candidates = [
    'JUP', 'WLD', 'FIL', 'FF', 'ENS', 'ZRO', 'ONDO', 'EIGEN', 
    'KITE', 'XPL', 'TRUMP', 'BARD', 'KAITO', '2Z', 'PUMP', 'JTO'
]

if 'last_alert_times' not in st.session_state:
    st.session_state.last_alert_times = {}

exchange = ccxt.binance({'options': {'defaultType': 'future'}, 'enableRateLimit': True, 'timeout': 30000})

# --- [2. 데이터 수집 함수] ---
def fetch_data(symbol):
    try:
        # 15분 데이터
        bars = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        df15 = pd.DataFrame(bars, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        c15 = df15['c']
        rsi15 = 100 - (100 / (1 + (c15.diff().clip(lower=0).ewm(com=13).mean() / (-c15.diff().clip(upper=0).ewm(com=13).mean()))))
        
        # 4시간 데이터
        bars4h = exchange.fetch_ohlcv(symbol, timeframe='4h', limit=50)
        df4h = pd.DataFrame(bars4h, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        c4h = df4h['c']
        rsi4h = 100 - (100 / (1 + (c4h.diff().clip(lower=0).ewm(com=13).mean() / (-c4h.diff().clip(upper=0).ewm(com=13).mean()))))
        
        return round(rsi15.iloc[-1], 2), round(rsi4h.iloc[-1], 2), c15.iloc[-1]
    except:
        return None, None, None

placeholder = st.empty()

# --- [3. 메인 루프] ---
while True:
    with placeholder.container():
        now_dt = datetime.now()
        st.subheader(f"⏱️ 실시간 업데이트: {now_dt.strftime('%H:%M:%S')}")

        data_list = []
        all_symbols = ['BTC/USDT', 'ETH/USDT'] + [s + '/USDT' for s in short_candidates]

        for s in all_symbols:
            rsi15, rsi4h, price = fetch_data(s)
            base_sym = s.split('/')[0]
            
            row = {
                "Symbol": f"${base_sym}", # $표시 추가
                "Price": f"${price:,.4f}" if price and price < 1 else (f"${price:,.2f}" if price else "N/A"),
                "RSI(15m)": rsi15 if rsi15 is not None else 0.00,
                "RSI(4H)": rsi4h if rsi4h is not None else 0.00, # 4H 추가
                "Status": "🔴 SHORT" if rsi15 and rsi15 >= 70 else ("🟢 LONG" if rsi15 and rsi15 <= 30 else "⚪ WAIT")
            }
            data_list.append(row)
            time.sleep(0.05)

        # --- [4. 데이터 정렬 및 가공] ---
        full_df = pd.DataFrame(data_list)
        
        # BTC, ETH 분리
        top_fix = full_df[full_df['Symbol'].isin(['$BTC', '$ETH'])]
        alts = full_df[~full_df['Symbol'].isin(['$BTC', '$ETH'])]
        
        # 알트코인만 RSI(15m) 기준 내림차순 정렬
        alts_sorted = alts.sort_values(by="RSI(15m)", ascending=False)
        
        # 다시 합치기 (BTC/ETH가 무조건 위로)
        final_df = pd.concat([top_fix, alts_sorted]).reset_index(drop=True)
        final_df.index = final_df.index + 1 # 인덱스 1부터 시작

        # --- [5. 표 스타일링 (가운데 정렬 + 이더리움 노란색)] ---
        def highlight_eth(row):
            if row['Symbol'] == '$ETH':
                return ['background-color: #FFFF00; color: black; font-weight: bold'] * len(row)
            return [''] * len(row)

        styled_df = final_df.style.apply(highlight_eth, axis=1)\
            .set_properties(**{'text-align': 'center'})\
            .format({'RSI(15m)': "{:.2f}", 'RSI(4H)': "{:.2f}"}) # 소수점 두자리 고정

        # 표 출력
        st.dataframe(styled_df, use_container_width=True, height=650)
        
        st.info("💡 15분봉 RSI 기준 정렬 중 (BTC/ETH 상단 고정)")
        time.sleep(30)
