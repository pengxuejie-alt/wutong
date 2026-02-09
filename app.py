import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="梧桐-疼痛管理", layout="wide", page_icon="🌿")

# --- 核心算法 ---
def round_dose(dose):
    """四舍五入至10的倍数，最小10mg，0则返回0"""
    if dose is None or dose <= 0: return 0
    rounded = math.floor(float(dose) / 10 + 0.5) * 10
    return max(10, int(rounded))

def get_day_results(records):
    """根据当天记录计算加药总量及次日建议"""
    rescue_total = 0
    scores = []
    
    # 容错处理：如果 records 为空或不是列表，返回全0
    if not isinstance(records, list) or len(records) < 24:
        return 0, 0, 0

    # 获取今日表格中填写的早晚基数 (08:00 index 0, 20:00 index 12)
    am_base = float(records[0].get('base_dose', 0) or 0)
    pm_base = float(records[12].get('base_dose', 0) or 0)
    
    for r in records:
        # 累加追加剂量
        try:
            rescue_total += float(r.get('rescue_dose', 0) or 0)
        except: pass
        
        # 提取评分用于减量判断
        s = str(r.get('score', ""))
        if s in ["睡觉", "", "None", "nan"]:
            scores.append(0)
        else:
            try: scores.append(float(s))
            except: scores.append(0)
            
    # 计算公式：总和 / 2
    base_next_raw = (am_base + pm_base + rescue_total) / 2
    
    # 减量逻辑：12h内没有任何评分 >= 1
    day_halve = all(x < 1 for x in scores[0:12])
    night_halve = all(x < 1 for x in scores[12:24])
    
    next_am = base_next_raw / 2 if day_halve else base_next_raw
    next_pm = base_next_raw / 2 if night_halve else base_next_raw
    
    return rescue_total, round_dose(next_am), round_dose(next_pm)

# --- 状态同步回调 ---
def sync_val(date_str, hour_idx, field):
    widget_key = f"in_{date_str}_{hour_idx}_{field}"
    if widget_key in st.session_state:
        st.session_state.all_days_data[date_str]["records"][hour_idx][field] = st.session_state[widget_key]

# --- 数据初始化与结构修复 ---
if 'all_days_data' not in st.session_state:
    st.session_state.all_days_data = {}
if 'target_date' not in st.session_state:
    st.session_state.target_date = datetime.now().date()

curr_d = st.session_state.target_date
prev_d = curr_d - timedelta(days=1)
d_str_c = str(curr_d)
d_str_p = str(prev_d)

hours_labels = [(f"{(i+8)%24:02d}:00-{(i+9)%24:02d}:00") for i in range(24)]

# 核心修复逻辑：确保数据结构符合最新版
for ds in [d_str_p, d_str_c]:
    if ds not in st.session_state.all_days_data:
        st.session_state.all_days_data[ds] = {
            "records": [{"score": "", "base_dose": 0.0, "type": "", "rescue_dose": 0.0, "memo": ""} for _ in range(24)]
        }
    else:
        # 如果旧数据是 df 格式，转换为 records 列表
        day_obj = st.session_state.all_days_data[ds]
        if "records" not in day_obj:
            new_records = []
            for i in range(24):
                new_records.append({
                    "score": "", "base_dose": 0.0, "type": "", "rescue_dose": 0.0, "memo": ""
                })
            st.session_state.all_days_data[ds]["records"] = new_records

# --- 侧边栏 ---
with st.sidebar:
    st.title("🌿 梧桐疼痛管理")
    st.session_state.target_date = st.date_input("📅 选择日期", value=st.session_state.target_date)
    st.divider()
    if st.button("🚨 强制重置 (清除所有错误)"):
        st.session_state.all_days_data = {}
        st.rerun()

# --- 计算建议 ---
# 从昨日数据推导
res_p, am_suggest, pm_suggest = get_day_results(st.session_state.all_days_data[d_str_p]["records"])

# 自动继承昨日建议（若今日尚未填写）
if st.session_state.all_days_data[d_str_c]["records"][0]["base_dose"] == 0 and am_suggest > 0:
    st.session_state.all_days_data[d_str_c]["records"][0]["base_dose"] = am_suggest
if st.session_state.all_days_data[d_str_c]["records"][12]["base_dose"] == 0 and pm_suggest > 0:
    st.session_state.all_days_data[d_str_c]["records"][12]["base_dose"] = pm_suggest

# --- 主界面 ---
st.header(f"📅 疼痛记录表：{curr_d}")

# 表头
h_c = st.columns([1.2, 1, 1.2, 1, 1, 1.5])
cols_text = ["时间段", "疼痛评分", "缓释基数(mg)", "追加种类", "追加剂量(mg)", "备注"]
for col, text in zip(h_c, cols_text):
    col.caption(text)

score_options = ["", "睡觉"] + [str(i) for i in range(11)]
drug_options = ["", "吗啡", "芬太尼", "其他"]
current_records = st.session_state.all_days_data[d_str_c]["records"]

for i, hr in enumerate(hours_labels):
    r_c = st.columns([1.2, 1, 1.2, 1, 1, 1.5])
    r_c[0].markdown(f"**{hr}**")
    
    # 评分
    s_val = str(current_records[i]["score"])
    r_c[1].selectbox("评", options=score_options, 
                   index=score_options.index(s_val) if s_val in score_options else 0,
                   key=f"in_{d_str_c}_{i}_score", on_change=sync_val, args=(d_str_c, i, "score"),
                   label_visibility="collapsed")
    
    # 基数
    if i == 0 or i == 12:
        r_c[2].number_input("基", min_value=0.0, step=10.0, 
                          value=float(current_records[i]["base_dose"]),
                          key=f"in_{d_str_c}_{i}_base_dose", on_change=sync_val, args=(d_str_c, i, "base_dose"),
                          label_visibility="collapsed")
    else:
        r_c[2].write("")

    # 追加
    t_val = current_records[i]["type"]
    r_c[3].selectbox("种", options=drug_options,
                   index=drug_options.index(t_val) if t_val in drug_options else 0,
                   key=f"in_{d_str_c}_{i}_type", on_change=sync_val, args=(d_str_c, i, "type"),
                   label_visibility="collapsed")
    
    d_val = float(current_records[i]["rescue_dose"])
    r_c[4].number_input("量", min_value=0.0, step=5.0, value=d_val,
                      key=f"in_{d_str_c}_{i}_rescue_dose", on_change=sync_val, args=(d_str_c, i, "rescue_dose"),
                      label_visibility="collapsed")
    
    # 备注
    m_val = current_records[i]["memo"]
    r_c[5].text_input("备", value=m_val,
                    key=f"in_{d_str_c}_{i}_memo", on_change=sync_val, args=(d_str_c, i, "memo"),
                    label_visibility="collapsed")

# --- 结算 ---
st.divider()
res_total, am_next, pm_next = get_day_results(current_records)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("今日追加总计", f"{res_total} mg")
with c2:
    st.success(f"📅 明日建议(早 08:00)：{am_next} mg")
with c3:
    st.success(f"📅 明日建议(晚 20:00)：{pm_next} mg")

if am_suggest > 0:
    st.info(f"💡 已基于昨日数据自动填充今日基数建议：{am_suggest}/{pm_suggest}")