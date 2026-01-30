import streamlit as st
import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime

# 頁面配置
st.set_page_config(page_title="專業基金實時看板", layout="wide")

DB_FILE = "fund_data.json"

# --- 數據儲存功能 ---
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

# --- 強大數據抓取與自動修正欄位 ---
@st.cache_data(ttl=300)
def get_safe_estimate():
    try:
        df = ak.fund_value_estimation_em()
        # 自動統一常見的簡繁體或不同版本欄位名
        mapping = {
            '基金代码': 'code', '基金代碼': 'code',
            '基金名称': 'name', '基金名稱': 'name',
            '估算净值': 'value', '估算淨值': 'value',
            '估算涨跌幅': 'pct', '估算漲跌幅': 'pct',
            '涨跌幅数据时间': 'time', '漲跌幅數據時間': 'time'
        }
        df = df.rename(columns=mapping)
        return df
    except Exception as e:
        st.error(f"數據源連線失敗: {e}")
        return None

@st.cache_data(ttl=3600)
def get_rel_info(code):
    try:
        # 抓取持倉來推算板塊
        stocks = ak.fund_stock_holding_em(symbol=code, date="20251231")
        if not stocks.empty:
            return ", ".join(stocks['持股名稱'].head(3).tolist())
    except: pass
    return "通用板塊"

# --- 側邊欄 ---
st.sidebar.header("📂 持倉管理")
with st.sidebar.form("add_fund"):
    in_code = st.text_input("基金代碼 (6位數)", placeholder="例如: 025209")
    in_shares = st.number_input("持有份額", min_value=0.0, step=100.0)
    in_cost = st.number_input("買入成本淨值", min_value=0.0, step=0.0001, format="%.4f")
    in_date = st.date_input("買入日期", value=datetime.now())
    if st.form_submit_button("💾 保存持倉"):
        if in_code:
            st.session_state.portfolio[in_code] = {
                "shares": in_shares, "cost": in_cost, "date": in_date.strftime("%Y-%m-%d")
            }
            save_data(st.session_state.portfolio)
            st.rerun()

if st.sidebar.button("🗑️ 清空所有數據"):
    save_data({}); st.session_state.portfolio = {}; st.rerun()

# --- 主界面 ---
st.title("📈 專業基金實時監控系統")

data_pool = get_safe_estimate()

if st.session_state.portfolio and data_pool is not None:
    rows = []
    for code, info in st.session_state.portfolio.items():
        # 安全獲取數據列，不論原始名稱為何
        target = data_pool[data_pool['code'] == code]
        
        if not target.empty:
            row_data = target.iloc[0]
            val = float(row_data.get('value', 0))
            pct = float(row_data.get('pct', 0))
            
            # 1. 持有天數
            buy_dt = datetime.strptime(info['date'], "%Y-%m-%d")
            days = (datetime.now() - buy_dt).days
            
            # 2. 當日收益 (估算)
            mkt_val = val * info['shares']
            day_gain = mkt_val * (pct / 100)
            
            # 3. 累計盈虧
            total_gain = (val - info['cost']) * info['shares']
            
            rows.append({
                "代碼": code, "名稱": row_data.get('name', '未知'),
                "淨值估算": val, "當日漲幅": pct,
                "當天收益": day_gain, "累計盈虧": total_gain,
                "持有天數": f"{max(0, days)}天",
                "關聯板塊": get_rel_info(code)
            })

    if rows:
        df_final = pd.DataFrame(rows)
        
        # 頂部視覺指標
        c1, c2, c3 = st.columns(3)
        c1.metric("今日預估收益", f"¥{df_final['當天收益'].sum():,.2f}")
        c2.metric("累計總盈虧", f"¥{df_final['累計盈虧'].sum():,.2f}")
        c3.metric("總市值", f"¥{(df_final['淨值估算'] * pd.Series([st.session_state.portfolio[c]['shares'] for c in df_final['代碼']])).sum():,.2f}")

        # 核心表格
        st.subheader("📋 實時詳細清單")
        st.dataframe(df_final.style.format({
            '淨值估算': '{:.4f}', '當日漲幅': '{:+.2f}%', 
            '當天收益': '{:+.2f}', '累計盈虧': '{:+.2f}'
        }), use_container_width=True)

        # 業績走勢圖
        st.divider()
        st.subheader("📊 業績走勢分析")
        sel_code = st.selectbox("選擇基金查看歷史淨值", df_final['代碼'].tolist())
        if sel_code:
            hist = ak.fund_open_fund_info_em(symbol=sel_code, indicator="單位淨值走勢")
            hist['淨值日期'] = pd.to_datetime(hist['淨值日期'])
            st.line_chart(hist.set_index('淨值日期')['單位淨值'])
    else:
        st.warning("請確認輸入的基金代碼是否為 A 股開放式基金。")

elif not st.session_state.portfolio:
    st.info("💡 尚未添加基金。請在左側輸入代碼、份額與成本。")
