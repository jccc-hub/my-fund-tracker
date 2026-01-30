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

# --- 強大數據抓取：自動修正所有欄位名稱並加入簡繁翻譯 ---
@st.cache_data(ttl=60)
def get_clean_data():
    try:
        df = ak.fund_value_estimation_em()
        mapping = {
            '基金代码': 'f_code', '基金代碼': 'f_code',
            '基金名称': 'f_name', '基金名稱': 'f_name',
            '估算净值': 'f_val', '估算淨值': 'f_val',
            '估算涨跌幅': 'f_pct', '估算漲跌幅': 'f_pct'
        }
        df = df.rename(columns=mapping)
        return df
    except Exception as e:
        st.error(f"數據源異常: {e}")
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
        target = all_data[all_data['f_code'] == str(code)]
        if not target.empty:
            row = target.iloc[0]
            curr_v = float(row.get('f_val', 0))
            pct = float(row.get('f_pct', 0))
            
            # 1. 持有天數
            buy_dt = datetime.strptime(info['date'], "%Y-%m-%d")
            days = (datetime.now() - buy_dt).days
            
            # 2. 當天收益
            mkt_val = curr_v * info['shares']
            day_gain = mkt_val * (pct / 100)
            
            # 3. 累計盈虧
            total_gain = (curr_v - info['cost']) * info['shares']
            
            rows.append({
                "代碼": code, "名稱": row.get('f_name', '未知'),
                "淨值估算": curr_v, "當日漲幅": pct,
                "當天收益": day_gain, "累計盈虧": total_gain,
                "持有天數": f"{max(0, days)}天",
                "關聯板塊": "點擊下方查看詳情"
            })

    if rows:
        df_final = pd.DataFrame(rows)
        
        # 視覺化指標
        m1, m2, m3 = st.columns(3)
        m1.metric("今日總預估收益", f"¥{df_final['當天收益'].sum():,.2f}")
        m2.metric("累計總盈虧", f"¥{df_final['累計盈虧'].sum():,.2f}")
        m3.metric("總持倉市值", f"¥{sum(df_final['淨值估算'] * pd.Series([st.session_state.portfolio[c]['shares'] for c in df_final['代碼']])):,.2f}")

        # 表格顯示 (解決你看不到細節的問題)
        st.subheader("📋 詳細持倉數據 (包含漲幅、收益、天數)")
        st.dataframe(df_final.style.format({
            '淨值估算': '{:.4f}', '當日漲幅': '{:+.2f}%', 
            '當天收益': '{:+.2f}', '累計盈虧': '{:+.2f}'
        }), use_container_width=True)

        # 走勢圖與板塊分析
        st.divider()
        st.subheader("📊 深度分析：業績走勢與關聯板塊")
        sel = st.selectbox("選擇一支基金進行深度分析", df_final['代碼'].tolist())
        if sel:
            col_l, col_r = st.columns([2, 1])
            with col_l:
                hist = ak.fund_open_fund_info_em(symbol=sel, indicator="單位淨值走勢")
                hist['淨值日期'] = pd.to_datetime(hist['淨值日期'])
                st.line_chart(hist.set_index('淨值日期')['單位淨值'])
            with col_r:
                st.write("**🔍 關聯重倉股票/板塊：**")
                stocks = ak.fund_stock_holding_em(symbol=sel, date="20251231")
                if not stocks.empty:
                    st.write(stocks[['持股名稱', '持股比例']].head(10))
                else:
                    st.write("暫無持倉數據")
    else:
        st.warning("數據匹配中，請確認代碼是否正確。")
else:
    st.info("💡 尚未添加基金。請在左側填寫持倉資訊。")
