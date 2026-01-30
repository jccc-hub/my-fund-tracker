import streamlit as st
import akshare as ak
import pandas as pd
import time
import json
import os

# 頁面設置
st.set_page_config(page_title="A股基金實時管家", layout="wide")

DB_FILE = "fund_data.json"

def load_data():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# --- 側邊欄 ---
st.sidebar.header("📂 帳戶管理")
with st.sidebar.form("add_form"):
    code = st.text_input("基金代碼", placeholder="如: 005827")
    shares = st.number_input("份額", min_value=0.0)
    cost = st.number_input("成本淨值", min_value=0.0, format="%.4f")
    if st.form_submit_button("加入持倉"):
        try:
            name = ak.fund_name_em().query(f"基金代碼=='{code}'")['基金簡稱'].values[0]
            st.session_state.portfolio[code] = {"name": name, "shares": shares, "cost": cost}
            save_data(st.session_state.portfolio)
            st.rerun()
        except: st.sidebar.error("代碼錯誤")

if st.sidebar.button("清空數據"):
    save_data({}); st.session_state.portfolio = {}; st.rerun()

# --- 主界面 ---
st.title("🚀 A股基金實時監控與走勢分析")

if st.session_state.portfolio:
    # 獲取實時數據
    all_est = ak.fund_value_estimation_em()
    rows = []
    for c, info in st.session_state.portfolio.items():
        res = all_est[all_est['基金代碼'] == c]
        if not res.empty:
            curr = float(res['估算淨值'].values[0])
            chg = float(res['估算漲跌幅'].values[0])
            mkt_val = curr * info['shares']
            profit = mkt_val - (info['cost'] * info['shares'])
            rows.append({"代碼": c, "名稱": info['name'], "估算淨值": curr, "今日漲跌": chg, "市值": mkt_val, "總盈虧": profit})

    df = pd.DataFrame(rows)
    
    # 頂部數據卡片
    c1, c2 = st.columns(2)
    c1.metric("總市值", f"¥{df['市值'].sum():,.2f}")
    c2.metric("累計盈虧", f"¥{df['總盈虧'].sum():,.2f}", delta=f"{(df['總盈虧'].sum()/((df['市值']-df['總盈虧']).sum())*100):.2f}%")

    # 數據表
    st.subheader("📋 我的持倉")
    selected_code = st.selectbox("選擇基金查看走勢圖", df['代碼'].tolist())
    st.dataframe(df.style.highlight_max(axis=0, color='#ffcccc'), use_container_width=True)

    # --- 走勢圖模塊 ---
    if selected_code:
        st.subheader(f"📈 基金歷史淨值走勢 ({selected_code})")
        with st.spinner('正在讀取歷史數據...'):
            # 獲取近一年的歷史淨值
            hist_df = ak.fund_open_fund_info_em(symbol=selected_code, indicator="單位淨值走勢")
            hist_df['淨值日期'] = pd.to_datetime(hist_df['淨值日期'])
            hist_df = hist_df.set_index('淨值日期').sort_index()
            
            # 使用 Streamlit 原生圖表
            st.line_chart(hist_df['單位淨值'])

else:
    st.info("請在左側添加基金。")

time.sleep(60)
st.rerun()
