import streamlit as st
import akshare as ak
import pandas as pd
import json
import os

# 頁面配置
st.set_page_config(page_title="A股基金監控管家", layout="wide")

DB_FILE = "fund_data.json"

# --- 數據持久化 ---
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# --- 核心數據抓取（增加緩存防止被封IP） ---
@st.cache_data(ttl=60) # 每 60 秒才真正去抓一次數據，其餘時間用緩存
def get_all_estimates():
    try:
        return ak.fund_value_estimation_em()
    except Exception as e:
        st.error(f"數據源連接失敗，請稍後重試。錯誤: {e}")
        return None

# --- 側邊欄 ---
st.sidebar.header("📂 持倉管理")
with st.sidebar.form("add_form"):
    code = st.text_input("基金代碼 (6位數字)", placeholder="例如: 005827")
    shares = st.number_input("持有份額", min_value=0.0, step=0.01)
    cost = st.number_input("買入成本淨值", min_value=0.0, step=0.0001, format="%.4f")
    if st.form_submit_button("添加持倉"):
        if code:
            st.session_state.portfolio[code] = {"shares": shares, "cost": cost}
            save_data(st.session_state.portfolio)
            st.rerun()

if st.sidebar.button("清空所有紀錄"):
    save_data({})
    st.session_state.portfolio = {}
    st.rerun()

# --- 主界面 ---
st.title("📈 A股基金實時監控看板")

all_estimates = get_all_estimates()

if st.session_state.portfolio and all_estimates is not None:
    rows = []
    for code, info in st.session_state.portfolio.items():
        # 匹配數據
        target = all_estimates[all_estimates['基金代碼'] == code]
        if not target.empty:
            name = target.iloc[0]['基金名稱']
            curr_val = float(target.iloc[0]['估算淨值'])
            pct = float(target.iloc[0]['估算漲跌幅'])
            
            mkt_val = curr_val * info['shares']
            profit = (curr_val - info['cost']) * info['shares']
            
            rows.append({
                "代碼": code, "名稱": name, "實時估值": curr_val,
                "今日漲跌": pct, "持有份額": info['shares'],
                "當前市值": mkt_val, "累計盈虧": profit
            })
    
    if rows:
        df = pd.DataFrame(rows)
        # 顯示卡片
        c1, c2, c3 = st.columns(3)
        c1.metric("總市值", f"¥{df['當前市值'].sum():,.2f}")
        c2.metric("累計盈虧", f"¥{df['累計盈虧'].sum():,.2f}")
        c3.metric("更新時間", all_estimates.iloc[0]['漲跌幅數據時間'])
        
        # 顯示表格
        st.dataframe(df.style.format({
            '實時估值': '{:.4f}', '今日漲跌': '{:+.2f}%', 
            '當前市值': '{:,.2f}', '累計盈虧': '{:+.2f}'
        }), use_container_width=True)
    else:
        st.warning("已輸入代碼，但在實時估值列表中找不到（可能非場外開放式基金）。")

elif not st.session_state.portfolio:
    st.info("請在左側輸入基金代碼並點擊保存。")
