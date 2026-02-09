import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="梧桐-疼痛管理", layout="wide", page_icon="🌿")

# --- 核心算法 ---
def round_dose(dose):
    if dose <= 0: return 0
    # 四舍五入至 10 的倍数，最小 10mg
    rounded = math.floor(dose / 10 + 0.5) * 10
    return max(10, int(rounded))

def get_day_results(df, am_base, pm_base):
    rescue_total = 0
    numeric_scores = []
    for s in df['评分']:
        s_str = str(s).strip()
        if s_str in ["睡觉", "", "None", "nan", "未记录"]:
            numeric_scores.append(None) # 视为无痛/睡眠
        else:
            try:
                val = float(s_str)
                numeric_scores.append(val)
                # 增加用药逻辑
                if val >= 8: rescue_total += 20
                elif val >= 4: rescue_total += 10
            except:
                numeric_scores.append(None)
    
    total_today = am_base + pm_base + rescue_total
    base_next = total_today / 2
    
    # 获取 12 小时切片
    day_slice = numeric_scores[0:12]
    night_slice = numeric_scores[12:24]
    
    # 修改后的减量逻辑：只要没有 >=1 的评分，就视为无痛（睡觉、留空、0均可）
    def check_halve(scores):
        # 只要列表中没有任何一个值 >= 1，就返回 True (减半)
        for x in scores:
            if x is not None and x >= 1:
                return False
        return True

    next_am = base_next / 2 if check_halve(day_slice) else base_next
    next_pm = base_next / 2 if check_halve(night_slice) else base_next
    
    return rescue_total, round_dose(next_am), round_dose(next_pm)

# --- 数据初始化 ---
if 'all_days_data' not in st.session_state:
    st.session_state.all_days_data = {}
if 'target_date' not in st.session_state:
    st.session_state.target_date = datetime.now().date()

# --- 日期控制 ---
def set_date(new_date):
    st.session_state.target_date = new_date

curr_d = st.session_state.target_date
prev_d = curr_d - timedelta(days=1)
next_d = curr_d + timedelta(days=1)

hours = [f"{i:02d}:00-{i+1:02d}:00" for i in range(24)]
display_hours = hours[8:] + hours[:8]

for d in [prev_d, curr_d, next_d]:
    ds = str(d)
    if ds not in st.session_state.all_days_data:
        st.session_state.all_days_data[ds] = {
            "df": pd.DataFrame({"时间段": display_hours, "评分": [""] * 24, "止痛处理": [""] * 24}),
            "am_base": 30, "pm_base": 30
        }

# --- 侧边栏：规则说明 ---
with st.sidebar:
    st.title("🌿 梧桐疼痛管理")
    st.session_state.target_date = st.date_input("📅 跳转日期", value=st.session_state.target_date)
    
    st.markdown("""
    <div style="font-size: 12px; color: #666; background-color: #f0f2f6; padding: 10px; border-radius: 5px;">
    <b>📋 最新用药规则</b><br>
    1. <b>基数：</b>次日建议 = 昨日总用药量(含加药) / 2<br>
    2. <b>增加：</b>评分 ≥4 加10mg，≥8 加20mg<br>
    3. <b>减少：</b>12h内<b>没有评分 ≥1</b> (含0、睡觉、留空) 则对应半天减半。<br>
    4. <b>修正：</b>结果四舍五入至10的倍数，最小10mg。
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🗑️ 清空记录"):
        st.session_state.all_days_data = {}
        st.rerun()

# --- 计算逻辑 ---
res_p, am_c, pm_c = get_day_results(st.session_state.all_days_data[str(prev_d)]["df"], 
                                     st.session_state.all_days_data[str(prev_d)]["am_base"], 
                                     st.session_state.all_days_data[str(prev_d)]["pm_base"])
st.session_state.all_days_data[str(curr_d)]["am_base"] = am_c
st.session_state.all_days_data[str(curr_d)]["pm_base"] = pm_c

# --- 主界面 ---
st.header(f"📅 疼痛管理：{curr_d}")
col_l, col_m, col_r = st.columns([1, 2.5, 1])

with col_l:
    st.subheader("⬅️ 昨日")
    with st.container(border=True):
        st.write(f"日期: {prev_d}")
        st.metric("基础量", f"{st.session_state.all_days_data[str(prev_d)]['am_base']}/{st.session_state.all_days_data[str(prev_d)]['pm_base']}")
        st.button("↩️ 切换昨日", on_click=set_date, args=(prev_d,), use_container_width=True)

with col_m:
    st.subheader("⏺️ 今日编辑")
    st.info(f"今日初始基数：早 {am_c}mg / 晚 {pm_c}mg")
    
    # 批量填充
    with st.expander("⚡ 批量填充工具"):
        c1, c2, c3 = st.columns(3)
        qv = c1.selectbox("选值", options=["睡觉", "0", "1", "3", "5", "10"])
        qr = c2.selectbox("区间", options=["全天", "白天(08-20)", "晚上(20-08)"])
        if c3.button("执行填充", use_container_width=True):
            idxs = range(24) if qr=="全天" else (range(12) if qr=="白天(08-20)" else range(12, 24))
            for i in idxs: st.session_state.all_days_data[str(curr_d)]["df"].at[i, "评分"] = qv
            st.rerun()

    # Data Editor
    st.session_state.all_days_data[str(curr_d)]["df"] = st.data_editor(
        st.session_state.all_days_data[str(curr_d)]["df"],
        column_config={
            "时间段": st.column_config.TextColumn(disabled=True),
            "评分": st.column_config.SelectboxColumn("评分", options=["睡觉", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]),
            "止痛处理": st.column_config.TextColumn("止痛处理")
        },
        hide_index=True,
        use_container_width=True,
        key=f"ed_{curr_d}"
    )

res_c, am_n, pm_n = get_day_results(st.session_state.all_days_data[str(curr_d)]["df"], am_c, pm_c)

with col_r:
    st.subheader("➡️ 明日预估")
    with st.container(border=True):
        st.write(f"日期: {next_d}")
        st.metric("预估早/晚", f"{am_n}/{pm_n}")
        st.write(f"今日加药累计: {res_c} mg")
        st.button("➡️ 切换明日", on_click=set_date, args=(next_d,), use_container_width=True)