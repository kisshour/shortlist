import streamlit as st
import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import requests

# --- [1. 설정 및 초기화] ---
st.set_page_config(page_title="Shortlist v2.3", layout="wide")

# [전역 알림 기록 장부] - 중복 알림 방지용
@st.cache_resource
def get_global_alert_tracker():
    return {}

global_alert_times = get_global_alert_tracker()

# [모바일 자동 감지 CSS 수정]
st.markdown("""
    <style>
    th, td { text-align: center !important; }

    /* 모바일 기기 (768px 이하) 대응 */
    @media only screen and (max-width: 768px) {
        /* 인덱스 열 포함 순서 기준:
           1:Index, 2:Symbol, 3:Price, 4:RSI(15m), 5:RSI(4H), 6:RSI GAB, 7:Status, 8:FDV/MC */

        /* 숨길 항목: RSI(4H), RSI GAB, FDV/MC */
        table th:nth-child(5), table td:nth-child(5),
        table th:nth-child(6), table td:nth-child(6),
        table th:nth-child(8), table td:nth-child(8) {
            display: none;
        }

        /* 폰트 크기 최적화 */
        td, th { font-size: 13px !important; padding: 5px !important; }
        h1 { font-size: 22px !important; }
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center;'>🚀 Shortlist v2.3</h1>", unsafe_allow_html=True)

CMC_API_KEY = "01bbeb036590498d97c169346dc19782"
TELEGRAM_TOKEN = "8378935636:AAH7JJmu7_B_YQ4P6CQ7TcAh3YYeG4ANTBU"
CHAT_ID = "-5285479874"

watch_list = ['ETH', 'XPL', 'KITE', 'TRUMP', 'BARD', 'KAITO', 'ZRO', 'WLD', 'ONDO', '2Z', 'PUMP', 'FIL', 'ENS', 'JTO', 'OP', 'JUP', 'MET']

if 'cmc_cache' not in st.session_state: st.session_state.cmc_cache = {}
if 'last_cmc_update' not in st.session_state: st.session_state.last_cmc_update = datetime.min

exchange = ccxt.binance({'options': {'defaultType': 'future'}, 'enableRateLimit': True})

# --- [2. 기능 함수] ---
def get_cmc_data():
    now = datetime.now()
    if (now - st.session_state.last_cmc_update).total_seconds() < 3600 and st.session_state.cmc_cache:
        return st.session_state.cmc_cache
    url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
    headers = {'X-CMC_PRO_API_KEY': CMC_API_KEY}
    params = {'symbol': ",".join(watch_list), 'convert': 'USD'}
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json().get('data', {})
        new_cache = {}
        for s in watch_list:
            if s in data and data[s]:
                q = data[s][0]['quote']['USD']
                mc = q.get('market_cap', 1); fdv = q.get('fully_diluted_market_cap', 0)
                new_cache[s] = f"{fdv/mc:.1f}x"
            else: new_cache[s] = "N/A"
        st.session_state.cmc_cache = new_cache; st.session_state.last_cmc_update = now
        return new_cache
    except: return st.session_state.cmc_cache

def fetch_exchange_data(symbol):
    try:
        pair = f"{symbol}/USDT"
        bars15 = exchange.fetch_ohlcv(pair, timeframe='15m', limit=50)
        df15 = pd.DataFrame(bars15, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        c15 = df15['c']
        rsi_series = 100 - (100 / (1 + (c15.diff().clip(lower=0).ewm(com=13).mean() / (-c15.diff().clip(upper=0).ewm(com=13).mean()))))
        bars4h = exchange.fetch_ohlcv(pair, timeframe='4h', limit=50)
        df4h = pd.DataFrame(bars4h, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
        rsi4h = 100 - (100 / (1 + (df4h['c'].diff().clip(lower=0).ewm(com=13).mean() / (-df4h['c'].diff().clip(upper=0).ewm(com=13).mean()))))
        return round(rsi_series.iloc[-1], 2), round(rsi_series.iloc[-2], 2), round(rsi4h.iloc[-1], 2), c15.iloc[-1]
    except: return None, None, None, None

placeholder = st.empty()

# --- [3. 메인 루프] ---
while True:
    with placeholder.container():
        now_dt = datetime.now()
        st.write(f"⏱️ **Update:** {now_dt.strftime('%H:%M:%S')}")

        ratios = get_cmc_data()
        data_list = []

        for s in watch_list:
            rsi15, rsi15_prev, rsi4h, price = fetch_exchange_data(s)
            if rsi15 is not None:
                arrow = "↗️" if rsi15 > rsi15_prev else ("↘️" if rsi15 < rsi15_prev else "-")

                # 텔레그램 알림
                alert_dir = None
                if rsi15 >= 70: alert_dir = "SHORT"
                elif rsi15 <= 30: alert_dir = "LONG"

                if alert_dir:
                    l_key = (s, alert_dir)
                    last_time = global_alert_times.get(l_key)
                    if last_time is None or (now_dt - last_time) > timedelta(hours=1):
                        msg = f"🔔 [{alert_dir} READY] ${s}\nPrice: ${price:,.4f}\nRSI(15m): {rsi15} {arrow}\nFDV/MC: {ratios.get(s, 'N/A')}"
                        try:
                            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={'chat_id': CHAT_ID, 'text': msg})
                            global_alert_times[l_key] = now_dt
                        except: pass

                status = "⚪ WAIT"
                if rsi15 >= 70 and arrow == "↘️": status = "🔴 SHORT"
                elif rsi15 <= 30 and arrow == "↗️": status = "🟢 LONG"

                data_list.append({
                    "Symbol": f"${s}", "Price": f"${price:,.4f}" if price < 1 else f"${price:,.2f}",
                    "RSI_VAL": rsi15, "RSI(15m)": f"{rsi15:.2f} {arrow}", "RSI(4H)": rsi4h,
                    "Status": status, "FDV/MC": ratios.get(s, "N/A")
                })
            time.sleep(0.05)

        if data_list:
            df = pd.DataFrame(data_list)
            df = df.sort_values(by="RSI_VAL", ascending=False).reset_index(drop=True)
            df.index = df.index + 1
            top_rsi = df.iloc[0]["RSI_VAL"]
            df["RSI GAB"] = df["RSI_VAL"] - top_rsi

            # 컬럼 순서 고정
            final_df = df[["Symbol", "Price", "RSI(15m)", "RSI(4H)", "RSI GAB", "Status", "FDV/MC"]]

            def style_row(row):
                if row.Symbol == '$ETH': return ['background-color: #FFFF00; color: black; font-weight: bold'] * len(row)
                return [''] * len(row)

            st.table(final_df.style.apply(style_row, axis=1).format({'RSI(4H)': "{:.2f}", 'RSI GAB': "{:.2f}"}))

        # --- [하단 안내 사항] ---
        st.write("---")
        st.info("""
        **💡 안내 사항**
        1. 텔레그램 알림은 RSI가 30/70을 돌파하는순간 바로 날라옵니다. 
        2. 웹페이지 RSI 15분 숫자 옆의 화살표는 직전15분봉 RSI보다 높은지 낮은지를 표시합니다. 
        3. STATUS는 RSI 70 이상이고 화살표가 아래(↘️)일때 SHORT, 30 이하고 화살표가 위(↗️)일때 LONG을 표시합니다.
        4. Shortlist에는 시총 50위~200위 사이 주요 거래소 상장 및 FDVMC 비율 높은 상위 16개 코인이 선정됩니다.
        5. 투자 책임은 본인에게 있습니다.
        """)
        time.sleep(30)
