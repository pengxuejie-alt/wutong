import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="梧桐-疼痛管理", layout="wide", page_icon="🌿")

# --- 核心算法 ---
def round_dose(dose):
    if dose <= 0: return 0
    rounded = math.floor(dose / 10 + 0.5) * 10
    return max(10, int(rounded))

def get_day_results(data_list, am_base, pm_base):
    rescue_total = 0
    numeric_scores = []
    for item in data_list:
        s = item['score']
        if s == "睡觉" or s == "" or s is None:
            numeric_scores.append(None)
        else:
            try:
                val = int(s)
                numeric_scores.append(val)
                if val >= 8: rescue_total += 20
                elif val >= 4: rescue_total += 10
            except:
                numeric_scores.append(None)
    
    total_today = am_base + pm_base + rescue_total
    base_next = total_today / 2
    day_slice = numeric_scores[0:12]
    night_slice = numeric_scores[12:24]
    
    day_zero = all(x == 0 for x in day_slice if x is not None) and any(x == 0 for x in day_slice)
    night_zero = all(x == 0 for x in night_slice if x is not None) and any(x == 0 for x in night_slice)
    
    next_am = base_next / 2 if day_zero else base_next
    next_pm = base_next / 2 if night_zero else base_next
    
    return rescue_total, round_dose(next_am), round_dose(next_pm)

# --- 数据初始化 ---
if 'all_days_data' not in st.session_state:
    st.session_state.all_days_data = {}
if 'target_date' not in st.session_state:
    st.session_state.target_date = datetime.now().date()

# --- 导航功能 ---
def move_date(offset):
    st.session_state.target_date += timedelta(days=offset)

# --- 侧边栏 ---
with st.sidebar:
    st.title("🌿 梧桐疼痛管理")
    st.session_state.target_date = st.date_input("📅 选择/跳转日期", value=st.session_state.target_date)
    st.divider()
    if st.button("重置所有数据"):
        st.session_state.all_days_data = {}
        st.rerun()

# --- 日期计算与串联 ---
curr_d = st.session_state.target_date
prev_d = curr_d - timedelta(days=1)
next_d = curr_d + timedelta(days=1)

for d in [prev_d, curr_d, next_d]:
    d_str = str(d)
    if d_str not in st.session_state.all_days_data:
        st.session_state.all_days_data[d_str] = {
            "records": [{"score": "", "treatment": ""} for _ in range(24)],
            "am_base": 30, "pm_base": 30
        }

# 逻辑流
res_p, am_c, pm_c = get_day_results(st.session_state.all_days_data[str(prev_d)]["records"], 
                                     st.session_state.all_days_data[str(prev_d)]["am_base"], 
                                     st.session_state.all_days_data[str(prev_d)]["pm_base"])
st.session_state.all_days_data[str(curr_d)]["am_base"] = am_c
st.session_state.all_days_data[str(curr_d)]["pm_base"] = pm_c

res_c, am_n, pm_n = get_day_results(st.session_state.all_days_data[str(curr_d)]["records"], 
                                     st.session_state.all_days_data[str(curr_d)]["am_base"], 
                                     st.session_state.all_days_data[str(curr_d)]["pm_base"])
st.session_state.all_days_data[str(next_d)]["am_base"] = am_n
st.session_state.all_days_data[str(next_d)]["pm_base"] = pm_n

# --- 主界面 ---
st.header(f"📅 正在查看：{curr_d}")

col_y, col_c, col_n = st.columns([1, 2.5, 1])

# --- 左侧面板 ---
with col_y:
    st.subheader(f"⬅️ {prev_d} (昨日)")
    with st.container(border=True):
        st.metric("基础药量", f"{st.session_state.all_days_data[str(prev_d)]['am_base']} / {st.session_state.all_days_data[str(prev_d)]['pm_base']}")
        st.write(f"临时加药: {res_p} mg")
        if st.button("⬅️ 切换至该日编辑", key="btn_prev", use_container_width=True):
            move_date(-1)
            st.rerun()

# --- 中间面板 (修正标题歧义) ---
with col_c:
    st.subheader(f"⏺️ {curr_d} (选定编辑页)")
    st.info(f"该日初始药量建议：早 **{am_c}mg** / 晚 **{pm_c}mg**")
    
    h_col1, h_col2, h_col3 = st.columns([1.2, 1, 2])
    h_col1.caption("时间段")
    h_col2.caption("评分")
    h_col3.caption("止痛处理")

    hours = [f"{i:02d}:00-{i+1:02d}:00" for i in range(24)]
    display_hours = hours[8:] + hours[:8]
    score_options = ["", "睡觉"] + [str(i) for i in range(11)]
    
    current_records = st.session_state.all_days_data[str(curr_d)]["records"]
    
    for i, hr in enumerate(display_hours):
        r_col1, r_col2, r_col3 = st.columns([1.2, 1, 2])
        r_col1.write(f"**{hr}**")
        idx_val = score_options.index(str(current_records[i]['score'])) if str(current_records[i]['score']) in score_options else 0
        new_score = r_col2.selectbox("评分", options=score_options, index=idx_val, key=f"sc_{curr_d}_{i}", label_visibility="collapsed")
        new_treat = r_col3.text_input("处理", value=current_records[i]['treatment'], key=f"tr_{curr_d}_{i}", label_visibility="collapsed")
        
        if new_score != "" and new_score != "睡觉":
            val = int(new_score)
            if val >= 8: r_col2.markdown("<span style='color:red;font-size:10px;'>⚠ 加20mg</span>", unsafe_allow_html=True)
            elif val >= 4: r_col2.markdown("<span style='color:orange;font-size:10px;'>⚠ 加10mg</span>", unsafe_allow_html=True)

        current_records[i]['score'] = new_score
        current_records[i]['treatment'] = new_treat
    st.session_state.all_days_data[str(curr_d)]["records"] = current_records

# --- 右侧面板 ---
with col_n:
    st.subheader(f"➡️ {next_d} (明日)")
    with st.container(border=True):
        st.metric("预测早剂量", f"{am_n} mg")
        st.metric("预测晚剂量", f"{pm_n} mg")
        if st.button("➡️ 切换至该日编辑", key="btn_next", use_container_width=True):
            move_date(1)
            st.rerun()