import streamlit as st
import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="專業基金實時監控", layout="wide")

# --- 數據儲存 ---
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

# --- 超強健數據抓取 (自動校準欄位) ---
@st.cache_data(ttl=60)
def get_safe_data():
    try:
        df = ak.fund_value_estimation_em()
        if df is None or df.empty: return None
        # 使用列位置索引，徹底避開 KeyError
        # 0:代碼, 1:名稱, 2:估算淨值, 3:估算漲跌幅
        res = df.iloc[:, [0, 1, 2, 3]].copy()
        res.columns = ['code', 'name', 'val', 'pct']
        return res
    except: return None

# --- 側邊欄 ---
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
st.title("📊 專業基金實時監控系統")

real_df = get_safe_data()

if st.session_state.portfolio and real_df is not None:
    rows = []
    for code, info in st.session_state.portfolio.items():
        target = real_df[real_df['code'].astype(str) == str(code)]
        if not target.empty:
            item = target.iloc[0]
            try:
                v, p = float(item['val']), float(item['pct'])
            except: v, p = 0.0, 0.0
            
            # 計算持有天數
            days = (datetime.now() - datetime.strptime(info['date'], "%Y-%m-%d")).days
            # 計算收益
            mkt_val = v * info['shares']
            day_gain = mkt_val * (p / 100)
            total_gain = (v - info['cost']) * info['shares']
            
            rows.append({
                "代碼": code, "名稱": item['name'], "估算淨值": v, "今日漲幅": p,
                "當天收益": day_gain, "累計盈虧": total_gain, "持有天數": f"{max(0, days)}天"
            })

    if rows:
        df_display = pd.DataFrame(rows)
        # 核心指標卡
        c1, c2, c3 = st.columns(3)
        c1.metric("今日預估收益", f"¥{df_display['當天收益'].sum():,.2f}")
        c2.metric("累計總盈虧", f"¥{df_display['累計盈虧'].sum():,.2f}")
        c3.metric("總市值", f"¥{(df_display['估算淨值'] * pd.Series([st.session_state.portfolio[c]['shares'] for c in df_display['代碼']])).sum():,.2f}")

        # 1. 詳細持倉表格
        st.subheader("📋 實時持倉細節")
        st.dataframe(df_display.style.format({
            '估算淨值': '{:.4f}', '今日漲幅': '{:+.2f}%', 
            '當天收益': '{:+.2f}', '累計盈虧': '{:+.2f}'
        }), use_container_width=True)

        # 2. 深度分析 (走勢 + 重倉股)
        st.divider()
        st.subheader("📈 深度分析：業績走勢與重倉股")
        sel = st.selectbox("選擇基金查看分析", df_display['代碼'].tolist())
        if sel:
            l, r = st.columns([2, 1])
            with l:
                st.write("**業績走勢 (淨值)**")
                try:
                    h = ak.fund_open_fund_info_em(symbol=sel, indicator="單位淨值走勢")
                    h = h.iloc[:, [0, 1]] # 強制取前兩列
                    h.columns = ['d', 'v']
                    h['d'] = pd.to_datetime(h['d'])
                    st.line_chart(h.set_index('d')['v'])
                except: st.error("走勢圖加載失敗")
            with r:
                st.write("**基金重倉股 (關聯板塊)**")
                try:
                    s = ak.fund_stock_holding_em(symbol=sel, date="20251231")
                    if not s.empty:
                        # 顯示前10大重倉，對應 App 的重倉股功能
                        st.table(s.iloc[:, [0, 2]].head(10))
                    else: st.write("暫無持倉數據")
                except: st.write("無法獲取板塊數據")
    else:
        st.warning("數據匹配中，請確保代碼輸入正確。")
else:
    st.info("💡 尚未添加基金或數據讀取中...")
