import streamlit as st
import akshare as ak
import pandas as pd
import json
import os

st.set_page_config(page_title="A股基金監控看板", layout="wide")

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

@st.cache_data(ttl=300)
def get_all_estimates():
    try:
        df = ak.fund_value_estimation_em()
        # 自動修正欄位名稱，確保能找到代碼和名稱
        rename_dict = {
            '基金代码': '基金代碼',
            '基金名称': '基金名稱',
            '估算净值': '估算淨值',
            '估算涨跌幅': '估算漲跌幅'
        }
        df = df.rename(columns=rename_dict)
        return df
    except Exception as e:
        st.error(f"數據抓取失敗: {e}")
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
    save_data({}); st.session_state.portfolio = {}; st.rerun()

# --- 主界面 ---
st.title("📈 A股基金實時監控看板")

all_estimates = get_all_estimates()

if st.session_state.portfolio and all_estimates is not None:
    rows = []
    # 這裡做了安全性檢查，防止 KeyError
    code_col = '基金代碼' if '基金代碼' in all_estimates.columns else all_estimates.columns[0]
    
    for code, info in st.session_state.portfolio.items():
        target = all_estimates[all_estimates[code_col] == code]
        if not target.empty:
            # 使用位置索引獲取數據，避免欄位名稱變動導致崩潰
            name = target.iloc[0].get('基金名稱', '未知基金')
            curr_val = float(target.iloc[0].get('估算淨值', 0))
            pct = float(target.iloc[0].get('估算漲跌幅', 0))
            
            mkt_val = curr_val * info['shares']
            profit = (curr_val - info['cost']) * info['shares']
            
            rows.append({
                "代碼": code, "名稱": name, "實時估值": curr_val,
                "今日漲跌": pct, "當前市值": mkt_val, "累計盈虧": profit
            })
    
    if rows:
        df_display = pd.DataFrame(rows)
        c1, c2 = st.columns(2)
        c1.metric("總市值", f"¥{df_display['當前市值'].sum():,.2f}")
        c2.metric("累計盈虧", f"¥{df_display['累計盈虧'].sum():,.2f}", f"{df_display['今日漲跌'].mean():+.2f}%")
        
        st.dataframe(df_display.style.format({
            '實時估值': '{:.4f}', '今日漲跌': '{:+.2f}%', 
            '當前市值': '{:,.2f}', '累計盈虧': '{:+.2f}'
        }), use_container_width=True)
    else:
        st.info("尚未匹配到數據，請確認代碼是否正確。")
elif not st.session_state.portfolio:
    st.info("💡 請在左側輸入基金代碼（如：005827）並點擊「添加持倉」。")
