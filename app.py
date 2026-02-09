import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="梧桐-疼痛管理", layout="wide", page_icon="🌿")

# --- 核心算法 ---
def round_dose(dose):
    if dose <= 0: return 0
    # 25 -> 30 逻辑
    rounded = math.floor(dose / 10 + 0.5) * 10
    return max(10, int(rounded))

def get_day_results(data_list, am_base, pm_base):
    """计算加药量和次日建议。data_list 为 [{"score":, "treatment":}, ...]"""
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
    
    # 减量逻辑：只有明确填0且该时段有记录才减半
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
    # 日历跳转
    st.session_state.target_date = st.date_input("📅 选择/跳转日期", value=st.session_state.target_date)
    
    st.divider()
    st.markdown("""
    <div style='font-size:12px; color:gray;'>
    <b>用药逻辑回顾：</b><br>
    - 评分 4-7: +10mg 速效<br>
    - 评分 ≥ 8: +20mg 速效<br>
    - 12h全为0: 对应半天减半<br>
    - “睡觉”或“不填”不视为0
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("重置所有数据"):
        st.session_state.all_days_data = {}
        st.rerun()

# --- 日期计算与串联 ---
curr_d = st.session_state.target_date
prev_d = curr_d - timedelta(days=1)
next_d = curr_d + timedelta(days=1)

# 初始化所需日期的数据
for d in [prev_d, curr_d, next_d]:
    d_str = str(d)
    if d_str not in st.session_state.all_days_data:
        st.session_state.all_days_data[d_str] = {
            "records": [{"score": "", "treatment": ""} for _ in range(24)],
            "am_base": 30, "pm_base": 30
        }

# 逻辑流：计算昨天 -> 影响今天 -> 影响明天
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
st.header(f"疼痛日记：{curr_d}")

col_y, col_c, col_n = st.columns([1, 2.5, 1])

# --- 左侧：昨天 ---
with col_y:
    st.subheader("⬅️ 昨天")
    with st.container(border=True):
        st.write(f"日期: {prev_d}")
        st.metric("基础药量", f"{st.session_state.all_days_data[str(prev_d)]['am_base']} / {st.session_state.all_days_data[str(prev_d)]['pm_base']}")
        st.write(f"临时加药: {res_p} mg")
        if st.button("切换到昨天修改", use_container_width=True):
            move_date(-1)
            st.rerun()

# --- 中间：今天 (编辑区) ---
with col_c:
    st.subheader("⏺️ 今日录入与调整")
    st.info(f"今日基础建议：早 **{am_c}mg** / 晚 **{pm_c}mg**")
    
    # 表头
    h_col1, h_col2, h_col3 = st.columns([1.2, 1, 2])
    h_col1.caption("时间段")
    h_col2.caption("评分")
    h_col3.caption("止痛处理")

    hours = [f"{i:02d}:00-{i+1:02d}:00" for i in range(24)]
    display_hours = hours[8:] + hours[:8] # 早上8点开始
    score_options = ["", "睡觉"] + [str(i) for i in range(11)]
    
    current_records = st.session_state.all_days_data[str(curr_d)]["records"]
    
    # 循环生成每一行的输入框
    for i, hr in enumerate(display_hours):
        r_col1, r_col2, r_col3 = st.columns([1.2, 1, 2])
        r_col1.write(f"**{hr}**")
        
        # 评分选择
        idx_val = score_options.index(str(current_records[i]['score'])) if str(current_records[i]['score']) in score_options else 0
        new_score = r_col2.selectbox("评分", options=score_options, index=idx_val, key=f"sc_{curr_d}_{i}", label_visibility="collapsed")
        
        # 止痛处理输入
        new_treat = r_col3.text_input("处理", value=current_records[i]['treatment'], key=f"tr_{curr_d}_{i}", label_visibility="collapsed", placeholder="如：加吗啡10mg")
        
        # 爆发痛提醒
        if new_score != "" and new_score != "睡觉":
            val = int(new_score)
            if val >= 8: r_col2.markdown("<span style='color:red;font-size:10px;'>⚠ 加20mg</span>", unsafe_allow_html=True)
            elif val >= 4: r_col2.markdown("<span style='color:orange;font-size:10px;'>⚠ 加10mg</span>", unsafe_allow_html=True)

        current_records[i]['score'] = new_score
        current_records[i]['treatment'] = new_treat

    st.session_state.all_days_data[str(curr_d)]["records"] = current_records

# --- 右侧：明天 ---
with col_n:
    st.subheader("➡️ 明天")
    with st.container(border=True):
        st.write(f"日期: {next_d}")
        st.metric("预测早剂量", f"{am_n} mg")
        st.metric("预测晚剂量", f"{pm_n} mg")
        st.caption("基于今日数据自动推算")
        if st.button("切换到明天编辑", use_container_width=True):
            move_date(1)
            st.rerun()

st.divider()
# 汇总导出
if st.button("📥 导出历史记录报表"):
    summary_list = []
    for d_str, d_val in sorted(st.session_state.all_days_data.items()):
        if any(r['score'] != "" for r in d_val['records']):
            res, _, _ = get_day_results(d_val['records'], d_val['am_base'], d_val['pm_base'])
            summary_list.append({
                "日期": d_str,
                "早 08:00": d_val['am_base'],
                "晚 20:00": d_val['pm_base'],
                "临时加药合计": res,
                "总药量": d_val['am_base'] + d_val['pm_base'] + res
            })
    st.table(pd.DataFrame(summary_list))