import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="梧桐-疼痛管理(批量版)", layout="wide", page_icon="🌿")

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

# --- 初始化 ---
if 'all_days_data' not in st.session_state:
    st.session_state.all_days_data = {}
if 'target_date' not in st.session_state:
    st.session_state.target_date = datetime.now().date()

# --- 数据更新回调 ---
def sync_data(d_str, index, field):
    key = f"{field}_{d_str}_{index}"
    st.session_state.all_days_data[d_str]["records"][index][field] = st.session_state[key]

def bulk_apply(d_str, target_val, hours_to_apply):
    if not hours_to_apply:
        return
    for i in hours_to_apply:
        st.session_state.all_days_data[d_str]["records"][i]["score"] = target_val
        # 刷新对应的 widget key
        st.session_state[f"score_{d_str}_{i}"] = target_val

# --- 日期逻辑 ---
curr_d = st.session_state.target_date
prev_d = curr_d - timedelta(days=1)
next_d = curr_d + timedelta(days=1)
d_str_c = str(curr_d)

for d in [prev_d, curr_d, next_d]:
    ds = str(d)
    if ds not in st.session_state.all_days_data:
        st.session_state.all_days_data[ds] = {
            "records": [{"score": "", "treatment": ""} for _ in range(24)],
            "am_base": 30, "pm_base": 30
        }

# --- 侧边栏 ---
with st.sidebar:
    st.title("🌿 梧桐疼痛管理")
    st.session_state.target_date = st.date_input("📅 选择日期", value=st.session_state.target_date)
    st.divider()
    st.info("批量输入说明：\n1. 在上方勾选小时\n2. 选择分值\n3. 点击批量填充")

# --- 主界面 ---
st.header(f"📅 疼痛日记：{curr_d}")

# --- 顶部：批量录入控制台 ---
with st.expander("🚀 快捷批量录入工具", expanded=True):
    hours_labels = [f"{i:02d}:00-{i+1:02d}:00" for i in range(24)]
    disp_hrs = hours_labels[8:] + hours_labels[:8]
    
    c_bulk1, c_bulk2 = st.columns([3, 1])
    with c_bulk1:
        selected_hours_idx = st.multiselect(
            "第一步：勾选需要录入的小时 (可多选)",
            options=range(24),
            format_func=lambda x: disp_hrs[x],
            help="提示：您可以直接选择连续的时段，如睡觉时间"
        )
        if st.button("全选白班 (08-20)"):
            st.session_state.bulk_hrs = list(range(12))
        if st.button("全选夜班 (20-08)"):
            st.session_state.bulk_hrs = list(range(12, 24))
            
    with c_bulk2:
        val_to_fill = st.selectbox("第二步：选择分值", options=["0", "睡觉", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
        if st.button("🔥 执行批量填充", type="primary"):
            bulk_apply(d_str_c, val_to_fill, selected_hours_idx)
            st.rerun()

st.divider()

# --- 三日联动展示 ---
col_y, col_c, col_n = st.columns([1, 2.5, 1])

# 准备药量基数
_, am_from_p, pm_from_p = get_day_results(
    st.session_state.all_days_data[str(prev_d)]["records"], 
    st.session_state.all_days_data[str(prev_d)]["am_base"], 
    st.session_state.all_days_data[str(prev_d)]["pm_base"]
)
st.session_state.all_days_data[d_str_c]["am_base"] = am_from_p
st.session_state.all_days_data[d_str_c]["pm_base"] = pm_from_p

# 渲染编辑区
with col_c:
    st.subheader("⏺️ 详细记录 (可手动微调)")
    st.caption(f"基础量：早{am_from_p} / 晚{pm_from_p}")
    
    score_options = ["", "睡觉"] + [str(i) for i in range(11)]
    records = st.session_state.all_days_data[d_str_c]["records"]
    
    for i, hr in enumerate(disp_hrs):
        r1, r2, r3 = st.columns([1.2, 1, 2])
        r1.write(f"**{hr}**")
        
        s_key = f"score_{d_str_c}_{i}"
        cur_s = str(records[i]['score'])
        
        r2.selectbox(
            "评分", options=score_options, 
            index=score_options.index(cur_s) if cur_s in score_options else 0,
            key=s_key, on_change=sync_data, args=(d_str_c, i, "score"),
            label_visibility="collapsed"
        )
        
        t_key = f"treatment_{d_str_c}_{i}"
        r3.text_input(
            "处理", value=records[i]['treatment'],
            key=t_key, on_change=sync_data, args=(d_str_c, i, "treatment"),
            label_visibility="collapsed", placeholder="备注..."
        )

# 左右面板显示
res_c, am_n, pm_n = get_day_results(records, am_from_p, pm_from_p)

with col_y:
    st.subheader(f"⬅️ {prev_d}")
    if st.button("⬅️ 跳转昨日"):
        st.session_state.target_date -= timedelta(days=1)
        st.rerun()
    st.metric("昨日加药", f"{get_day_results(st.session_state.all_days_data[str(prev_d)]['records'], 0, 0)[0]} mg")

with col_n:
    st.subheader(f"➡️ {next_d}")
    if st.button("➡️ 跳转明日"):
        st.session_state.target_date += timedelta(days=1)
        st.rerun()
    st.metric("预测次日早", f"{am_n} mg")
    st.metric("预测次日晚", f"{pm_n} mg")