import streamlit as st
import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime

# 頁面基礎設置
st.set_page_config(page_title="專業基金實時監控", layout="wide")

DB_FILE = "fund_data.json"

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

# --- 核心：強健的數據抓取邏輯 (直接按位置索引防止 KeyError) ---
@st.cache_data(ttl=60)
def get_realtime_data():
    try:
        df = ak.fund_value_estimation_em()
        if df is None or df.empty: return None
        # 強制只取前四列：[0]代碼, [1]名稱, [2]估算淨值, [3]估算漲跌幅
        df_clean = df.iloc[:, [0, 1, 2, 3]].copy()
        df_clean.columns = ['f_code', 'f_name', 'f_val', 'f_pct']
        return df_clean
    except Exception as e:
        st.error(f"數據加載失敗: {e}")
        return None

# --- 側邊欄：持倉管理 ---
st.sidebar.header("📂 持倉配置")
with st.sidebar.form("add_form"):
    c_code = st.text_input("基金代碼 (如 025209)")
    c_shares = st.number_input("持有份額", min_value=0.0, step=0.01)
    c_cost = st.number_input("買入成本淨值", min_value=0.0, step=0.0001, format="%.4f")
    c_date = st.date_input("買入日期")
    if st.form_submit_button("➕ 保存/更新持倉"):
        if c_code:
            st.session_state.portfolio[c_code] = {
                "shares": c_shares, "cost": c_cost, "date": str(c_date)
            }
            save_data(st.session_state.portfolio)
            st.rerun()

if st.sidebar.button("🗑️ 清空所有數據"):
    save_data({}); st.session_state.portfolio = {}; st.rerun()

# --- 主界面 ---
st.title("📈 專業基金實時監控系統")

all_data = get_realtime_data()

if st.session_state.portfolio and all_data is not None:
    rows = []
    for code, info in st.session_state.portfolio.items():
        # 匹配代碼
        target = all_data[all_data['f_code'].astype(str) == str(code)]
        if not target.empty:
            row = target.iloc[0]
            try:
                v = float(row['f_val'])
                p = float(row['f_pct'])
            except: v, p = 0.0, 0.0
            
            # 持有天數
            buy_dt = datetime.strptime(info['date'], "%Y-%m-%d")
            days = (datetime.now() - buy_dt).days
            
            # 收益計算
            mkt_val = v * info['shares']
            day_gain = mkt_val * (p / 100)
            total_gain = (v - info['cost']) * info['shares']
            
            rows.append({
                "代碼": code, "名稱": row['f_name'],
                "淨值估算": v, "當日漲幅": p,
                "當天收益": day_gain, "累計盈虧": total_gain,
                "持有天數": f"{max(0, days)}天"
            })

    if rows:
        df_final = pd.DataFrame(rows)
        # 頂部指標卡
        m1, m2, m3 = st.columns(3)
        m1.metric("今日總預估收益", f"¥{df_final['當天收益'].sum():,.2f}")
        m2.metric("累計總盈虧", f"¥{df_final['累計盈虧'].sum():,.2f}")
        m3.metric("總持倉市值", f"¥{sum(df_final['淨值估算'] * pd.Series([st.session_state.portfolio[c]['shares'] for c in df_final['代碼']])):,.2f}")

        # 詳細表格
        st.subheader("📋 詳細持倉數據 (包含漲幅、收益、天數)")
        st.dataframe(df_final.style.format({
            '淨值估算': '{:.4f}', '當日漲幅': '{:+.2f}%', 
            '當天收益': '{:+.2f}', '累計盈虧': '{:+.2f}'
        }), use_container_width=True)

        # 深度分析 (業績走勢 + 關聯板塊/重倉股)
        st.divider()
        st.subheader("📊 深度分析：業績走勢與重倉股 (關聯板塊)")
        sel = st.selectbox("選擇一支基金進行分析", df_final['代碼'].tolist())
        if sel:
            col_l, col_r = st.columns([2, 1])
            with col_l:
                try:
                    # 抓取歷史淨值走勢
                    hist = ak.fund_open_fund_info_em(symbol=sel, indicator="單位淨值走勢")
                    hist = hist.iloc[:, [0, 1]] # 只取 [日期, 淨值]
                    hist.columns = ['date', 'value']
                    hist['date'] = pd.to_datetime(hist['date'])
                    st.line_chart(hist.set_index('date')['value'])
                except: st.warning("歷史走勢加載超時，請稍候。")
            
            with col_r:
                try:
                    # 抓取像 App 截圖那樣的「基金重倉股」
                    st.write("**🔍 基金前十大重倉股 (關聯板塊)：**")
                    holdings = ak.fund_stock_holding_em(symbol=sel, date="20251231")
                    if not holdings.empty:
                        # 只取股票名稱和佔比
                        display_h = holdings.iloc[:, [0, 2]].head(10)
                        display_h.columns = ['股票名稱', '持倉佔比']
                        st.table(display_h)
                    else: st.write("暫無重倉股數據")
                except: st.write("板塊數據目前無法獲取")
    else:
        st.warning("數據匹配中，請確保代碼輸入正確。")
else:
    st.info("💡 尚未添加持倉或數據讀取中...")
