import streamlit as st
import akshare as ak
import pandas as pd
import os
from datetime import datetime

# 頁面基礎設置
st.set_page_config(page_title="專業基金監控", layout="wide")
st.title("📊 專業基金實時監控系統")

# --- 數據抓取：最強健的欄位映射邏輯 ---
@st.cache_data(ttl=60)
def fetch_data():
    try:
        df = ak.fund_value_estimation_em()
        # 列印所有欄位到日誌，方便除錯
        print(f"Current columns: {df.columns.tolist()}")
        
        # 強制重命名所有可能的變體
        col_map = {
            '基金代码': 'code', '基金代碼': 'code',
            '基金名称': 'name', '基金名稱': 'name',
            '估算净值': 'val', '估算淨值': 'val',
            '估算涨跌幅': 'pct', '估算漲跌幅': 'pct'
        }
        df = df.rename(columns=col_map)
        return df
    except Exception as e:
        st.error(f"API 連線失敗: {e}")
        return None

# --- 持倉管理 ---
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

with st.sidebar:
    st.header("📂 持倉配置")
    c_code = st.text_input("基金代碼", placeholder="025209")
    c_shares = st.number_input("持有份額", min_value=0.0)
    c_cost = st.number_input("買入成本淨值", min_value=0.0, format="%.4f")
    c_date = st.date_input("買入日期")
    
    if st.button("➕ 添加/更新"):
        if c_code:
            st.session_state.portfolio[c_code] = {
                "shares": c_shares, "cost": c_cost, "date": str(c_date)
            }
            st.rerun()
    
    if st.button("🗑️ 清空紀錄"):
        st.session_state.portfolio = {}
        st.rerun()

# --- 主畫面邏輯 ---
all_df = fetch_data()

if st.session_state.portfolio and all_df is not None:
    results = []
    for code, info in st.session_state.portfolio.items():
        # 確保 code 是字串匹配
        target = all_df[all_df['code'].astype(str) == str(code)]
        
        if not target.empty:
            row = target.iloc[0]
            # 使用 .get() 確保不會因為 KeyError 崩潰
            v = float(row.get('val', 0))
            p = float(row.get('pct', 0))
            name = row.get('name', '未知')
            
            # 計算數據
            buy_dt = datetime.strptime(info['date'], "%Y-%m-%d")
            days = (datetime.now() - buy_dt).days
            mkt_v = v * info['shares']
            day_gain = mkt_v * (p / 100)
            total_gain = (v - info['cost']) * info['shares']
            
            results.append({
                "代碼": code, "名稱": name, "估算淨值": v, "漲幅": p,
                "今日收益": day_gain, "累計盈虧": total_gain, "持有天數": f"{max(0, days)}天"
            })
    
    if results:
        res_df = pd.DataFrame(results)
        # 顯示指標
        k1, k2 = st.columns(2)
        k1.metric("今日總盈虧", f"¥{res_df['今日收益'].sum():,.2f}")
        k2.metric("累計總盈虧", f"¥{res_df['累計盈虧'].sum():,.2f}")
        
        # 顯示表格
        st.dataframe(res_df.style.format({
            '估算淨值': '{:.4f}', '漲幅': '{:+.2f}%',
            '今日收益': '{:+.2f}', '累計盈虧': '{:+.2f}'
        }), use_container_width=True)
    else:
        st.warning("查無此基金代碼，請確認是否為 A 股場外基金。")
else:
    st.info("💡 請在左側輸入代碼並點擊保存。")
