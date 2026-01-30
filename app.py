import streamlit as st
import akshare as ak
import pandas as pd
import json
import os

# 1. 頁面配置
st.set_page_config(page_title="A股基金監控", layout="wide")

DB_FILE = "fund_data.json"

# 2. 數據持久化
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

# 3. 側邊欄：持倉管理
st.sidebar.header("📁 持倉管理")
with st.sidebar.form("add_form"):
    code = st.text_input("基金代碼 (如 005827)")
    shares = st.number_input("份額", min_value=0.0, step=0.1)
    cost = st.number_input("成本淨值", min_value=0.0, step=0.0001, format="%.4f")
    if st.form_submit_button("💾 保存持倉"):
        if code:
            try:
                # 獲取基金名稱
                all_f = ak.fund_name_em()
                name = all_f[all_f['基金代碼'] == code]['基金簡稱'].values[0]
                st.session_state.portfolio[code] = {"name": name, "shares": shares, "cost": cost}
                save_data(st.session_state.portfolio)
                st.success(f"已加入: {name}")
                st.rerun()
            except: st.error("代碼有誤")

if st.sidebar.button("🗑️ 清空所有數據"):
    save_data({}); st.session_state.portfolio = {}; st.rerun()

# 4. 主界面
st.title("📈 A股基金實時估值看板")

if st.session_state.portfolio:
    try:
        # 獲取數據
        with st.spinner('獲取最新估值中...'):
            all_est = ak.fund_value_estimation_em()
        
        rows = []
        for c, info in st.session_state.portfolio.items():
            res = all_est[all_est['基金代碼'] == c]
            if not res.empty:
                curr = float(res['估算淨值'].values[0])
                chg = float(res['估算漲跌幅'].values[0])
                mkt_val = curr * info['shares']
                profit = mkt_val - (info['cost'] * info['shares'])
                rows.append({
                    "代碼": c, "名稱": info['name'], "估算淨值": curr, 
                    "今日漲跌": chg, "市值": mkt_val, "總盈虧": profit,
                    "時間": res['漲跌幅數據時間'].values[0]
                })

        df = pd.DataFrame(rows)

        # 頂部指標
        c1, c2, c3 = st.columns(3)
        c1.metric("總市值", f"¥{df['市值'].sum():,.2f}")
        c2.metric("預估今日盈虧", f"¥{(df['市值'] * (df['今日漲跌']/100)).sum():,.2f}")
        c3.metric("累計總盈虧", f"¥{df['總盈虧'].sum():,.2f}")

        # 詳細表格
        st.dataframe(df.style.format({'估算淨值': '{:.4f}', '今日漲跌': '{:+.2f}%', '市值': '{:,.2f}', '總盈虧': '{:+.2f}'}), use_container_width=True)

        # 走勢圖
        st.divider()
        sel = st.selectbox("選擇基金查看歷史走勢", df['代碼'].tolist())
        if sel:
            hist = ak.fund_open_fund_info_em(symbol=sel, indicator="單位淨值走勢")
            hist['淨值日期'] = pd.to_datetime(hist['淨值日期'])
            st.line_chart(hist.set_index('淨值日期')['單位淨值'])

    except Exception as e:
        st.error(f"數據加載中，請刷新頁面 (Error: {e})")
else:
    st.info("請在左側添加你的第一支基金持倉。")

# 5. 每 5 分鐘自動刷新頁面 (Streamlit 官方推薦方式)
st.empty()
# st.write("提示: 點擊右上角三條線可以選擇 'Always rerun' 保持實時更新")
