import streamlit as st
import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="專業級基金監控看板", layout="wide")

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

# --- 數據抓取函數 (帶緩存) ---
@st.cache_data(ttl=600)
def get_fund_estimate():
    df = ak.fund_value_estimation_em()
    return df.rename(columns={'基金代码': '基金代碼', '基金名称': '基金名稱', '估算净值': '估算淨值', '估算涨跌幅': '估算漲跌幅'})

@st.cache_data(ttl=3600)
def get_fund_rel_sectors(code):
    try:
        # 獲取持倉股票，進而推算關聯板塊
        stocks = ak.fund_stock_holding_em(symbol=code, date="20251231") # 使用最新季度
        if not stocks.empty:
            return ", ".join(stocks['持股名稱'].head(3).tolist()) + " 等相關板塊"
    except: return "暫無數據"
    return "暫無數據"

# --- 側邊欄：持倉管理 ---
st.sidebar.header("📂 持倉配置")
with st.sidebar.form("add_form"):
    c_code = st.text_input("基金代碼", placeholder="005827")
    c_shares = st.number_input("持有份額", min_value=0.0, step=0.01)
    c_cost = st.number_input("買入成本淨值", min_value=0.0, step=0.0001, format="%.4f")
    c_date = st.date_input("買入日期", value=datetime.now())
    if st.form_submit_button("➕ 添加/更新持倉"):
        if c_code:
            st.session_state.portfolio[c_code] = {
                "shares": c_shares, 
                "cost": c_cost, 
                "date": c_date.strftime("%Y-%m-%d")
            }
            save_data(st.session_state.portfolio)
            st.rerun()

if st.sidebar.button("🗑️ 清空所有紀錄"):
    save_data({}); st.session_state.portfolio = {}; st.rerun()

# --- 主界面 ---
st.title("📊 專業基金實時監控系統")

all_est = get_fund_estimate()

if st.session_state.portfolio and all_est is not None:
    rows = []
    for code, info in st.session_state.portfolio.items():
        target = all_est[all_est['基金代碼'] == code]
        if not target.empty:
            curr_val = float(target.iloc[0]['估算淨值'])
            pct = float(target.iloc[0]['估算漲跌幅'])
            
            # 計算持有天數
            buy_date = datetime.strptime(info['date'], "%Y-%m-%d")
            days = (datetime.now() - buy_date).days
            
            # 當日收益 = 當前市值 * (漲跌幅 / (1 + 漲跌幅)) <- 這是估算昨日淨值後的算法
            # 簡單算法：當前市值 * 今日漲跌百分比
            mkt_val = curr_val * info['shares']
            today_profit = mkt_val * (pct / 100)
            total_profit = (curr_val - info['cost']) * info['shares']
            
            rows.append({
                "代碼": code, "名稱": target.iloc[0]['基金名稱'],
                "估算淨值": curr_val, "今日漲跌": pct,
                "當日收益": today_profit, "累計盈虧": total_profit,
                "持有天數": f"{max(0, days)}天",
                "關聯板塊": get_fund_rel_sectors(code)
            })
    
    if rows:
        df_display = pd.DataFrame(rows)
        
        # 頂部核心指標
        m1, m2, m3 = st.columns(3)
        m1.metric("今日總預估收益", f"¥{df_display['當日收益'].sum():,.2f}")
        m2.metric("累計總盈虧", f"¥{df_display['累計盈虧'].sum():,.2f}")
        m3.metric("平均持倉天數", f"{int(pd.to_numeric(df_display['持有天數'].str.replace('天','')).mean())}天")

        # 數據表格
        st.subheader("📋 實時持倉細節")
        st.dataframe(df_display.style.format({
            '估算淨值': '{:.4f}', '今日漲跌': '{:+.2f}%', 
            '當日收益': '{:+.2f}', '累計盈虧': '{:+.2f}'
        }), use_container_width=True)

        # 業績走勢圖
        st.divider()
        st.subheader("📈 業績走勢分析")
        sel_code = st.selectbox("選擇基金查看淨值走勢", df_display['代碼'].tolist())
        if sel_code:
            hist_df = ak.fund_open_fund_info_em(symbol=sel_code, indicator="單位淨值走勢")
            hist_df['淨值日期'] = pd.to_datetime(hist_df['淨值日期'])
            st.line_chart(hist_df.set_index('淨值日期')['單位淨值'])
    else:
        st.warning("數據匹配中，請稍後...")

elif not st.session_state.portfolio:
    st.info("💡 尚未添加基金。請使用左側表單輸入您的持倉。")
