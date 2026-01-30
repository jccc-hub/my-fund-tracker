import streamlit as st
import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime

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

# --- 超強健數據抓取：不依賴固定欄位名 ---
@st.cache_data(ttl=60)
def get_clean_data():
    try:
        df = ak.fund_value_estimation_em()
        # 強制根據列的順序重命名，避免簡繁體/文字變動問題
        # 0:代碼, 1:名稱, 2:估算淨值, 3:估算漲跌幅
        new_cols = {df.columns[0]: 'f_code', df.columns[1]: 'f_name', 
                    df.columns[2]: 'f_val', df.columns[3]: 'f_pct'}
        return df.rename(columns=new_cols)
    except Exception as e:
        st.error(f"數據抓取失敗: {e}")
        return None

# --- 側邊欄 ---
st.sidebar.header("📂 持倉配置")
with st.sidebar.form("add_form"):
    c_code = st.text_input("基金代碼", placeholder="例如: 025209")
    c_shares = st.number_input("持有份額", min_value=0.0, step=0.01)
    c_cost = st.number_input("買入成本淨值", min_value=0.0, step=0.0001, format="%.4f")
    c_date = st.date_input("買入日期", value=datetime.now())
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

all_data = get_clean_data()

if st.session_state.portfolio and all_data is not None:
    rows = []
    for code, info in st.session_state.portfolio.items():
        target = all_data[all_data['f_code'].astype(str) == str(code)]
        if not target.empty:
            row = target.iloc[0]
            try:
                curr_v = float(row['f_val'])
                pct = float(row['f_pct'])
            except: curr_v, pct = 0.0, 0.0
            
            buy_dt = datetime.strptime(info['date'], "%Y-%m-%d")
            days = (datetime.now() - buy_dt).days
            mkt_val = curr_v * info['shares']
            day_gain = mkt_val * (pct / 100)
            total_gain = (curr_v - info['cost']) * info['shares']
            
            rows.append({
                "代碼": code, "名稱": row['f_name'],
                "淨值估算": curr_v, "當日漲幅": pct,
                "當天收益": day_gain, "累計盈虧": total_gain,
                "持有天數": f"{max(0, days)}天"
            })

    if rows:
        df_final = pd.DataFrame(rows)
        # 指標
        m1, m2, m3 = st.columns(3)
        m1.metric("今日總預估收益", f"¥{df_final['當天收益'].sum():,.2f}")
        m2.metric("累計總盈虧", f"¥{df_final['累計盈虧'].sum():,.2f}")
        m3.metric("總持倉市值", f"¥{sum(df_final['淨值估算'] * pd.Series([st.session_state.portfolio[c]['shares'] for c in df_final['代碼']])):,.2f}")

        st.subheader("📋 詳細持倉數據")
        st.dataframe(df_final.style.format({
            '淨值估算': '{:.4f}', '當日漲幅': '{:+.2f}%', 
            '當天收益': '{:+.2f}', '累計盈虧': '{:+.2f}'
        }), use_container_width=True)

        st.divider()
        st.subheader("📊 深度分析：業績走勢與關聯板塊")
        sel = st.selectbox("選擇基金進行深度分析", df_final['代碼'].tolist())
        if sel:
            l, r = st.columns([2, 1])
            with l:
                try:
                    h = ak.fund_open_fund_info_em(symbol=sel, indicator="單位淨值走勢")
                    # 自動抓取第一列(日期)和第二列(淨值)
                    h = h.iloc[:, [0, 1]]
                    h.columns = ['date', 'val']
                    h['date'] = pd.to_datetime(h['date'])
                    st.line_chart(h.set_index('date')['val'])
                except: st.error("走勢數據暫時無法獲取")
            with r:
                try:
                    s = ak.fund_stock_holding_em(symbol=sel, date="20251231")
                    if not s.empty:
                        # 自動抓取名稱與比例列
                        s = s.iloc[:, [0, 1, 2]] # 假設前三列包含名稱和比例
                        st.write("**🔍 關聯重倉股票：**")
                        st.dataframe(s.head(10), hide_index=True)
                    else: st.write("暫無板塊持倉數據")
                except: st.write("無法獲取板塊數據")
else:
    st.info("💡 尚未添加基金或數據加載中...")
