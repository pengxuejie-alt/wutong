import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="梧桐-疼痛管理", layout="wide", page_icon="🌿")

# --- 核心算法 (使用 LaTeX 规范) ---
def round_dose(dose):
    """四舍五入至 10 的倍数，最小 10mg，若为 0 则返回 0"""
    if dose is None or dose <= 0: return 0
    # $rounded = \lfloor dose / 10 + 0.5 \rfloor * 10$
    rounded = math.floor(float(dose) / 10 + 0.5) * 10
    return max(10, int(rounded))

def get_day_results(records):
    """根据当天记录计算加药总量及次日建议"""
    rescue_total = 0
    scores = []
    
    # 获取今日表格中填写的早晚基数
    am_base = float(records[0].get('base_dose', 0) or 0)
    pm_base = float(records[12].get('base_dose', 0) or 0)
    
    for r in records:
        # 累加追加剂量
        try:
            rescue_total += float(r.get('rescue_dose', 0) or 0)
        except: pass
        
        # 提取评分
        s = str(r.get('score', ""))
        if s in ["睡觉", "", "None", "nan"]:
            scores.append(0)
        else:
            try: scores.append(float(s))
            except: scores.append(0)
            
    # 计算公式：$Base_{next} = (Base_{am} + Base_{pm} + Rescue_{total}) / 2$
    base_next_raw = (am_base + pm_base + rescue_total) / 2
    
    # 减量逻辑：12h内没有任何评分 >= 1
    # 白天 (08:00-20:00), 晚上 (20:00-08:00)
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

# --- 数据初始化 ---
if 'all_days_data' not in st.session_state:
    st.session_state.all_days_data = {}
if 'target_date' not in st.session_state:
    st.session_state.target_date = datetime.now().date()

curr_d = st.session_state.target_date
prev_d = curr_d - timedelta(days=1)
d_str_c = str(curr_d)
d_str_p = str(prev_d)

# 24小时标签（从早8点开始）
hours_labels = [(f"{(i+8)%24:02d}:00-{(i+9)%24:02d}:00") for i in range(24)]

# 初始化今天和昨天的数据结构
for ds in [d_str_p, d_str_c]:
    if ds not in st.session_state.all_days_data:
        st.session_state.all_days_data[ds] = {
            "records": [{"score": "", "base_dose": 0.0, "type": "", "rescue_dose": 0.0, "memo": ""} for _ in range(24)]
        }

# --- 侧边栏 ---
with st.sidebar:
    st.title("🌿 梧桐疼痛管理")
    st.session_state.target_date = st.date_input("📅 日期跳转", value=st.session_state.target_date)
    st.markdown("""
    <div style="font-size: 11px; color: #777; background-color: #f9f9f9; padding: 10px; border-radius: 5px; border: 1px solid #eee;">
    <b>📋 核心逻辑说明</b><br>
    1. <b>基数录入：</b>直接在 08:00 和 20:00 行的“缓释基数”列输入。<br>
    2. <b>次日计算：</b><br>
       - $Base_{建议} = \frac{\text{今日总和}}{2}$<br>
       - 若 12h 内评分均 < 1，该时段建议剂量再减半。<br>
    3. <b>追加规则：</b>评分 ≥4 建议加 10，≥8 建议加 20。<br>
    4. <b>数值修正：</b>最小 10mg，四舍五入。
    </div>
    """, unsafe_allow_html=True)
    if st.button("🔄 清理缓存"):
        st.session_state.all_days_data = {}
        st.rerun()

# --- 计算推导 ---
# 从昨天的数据推导今天的建议
res_p, am_suggest, pm_suggest = get_day_results(st.session_state.all_days_data[d_str_p]["records"])

# 如果今天是第一次填，或者手动想改，表格里的 base_dose 会起作用
# 自动填充逻辑：如果表格里还没填基数，则把昨天的建议填进去
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

# 逐行渲染
for i, hr in enumerate(hours_labels):
    r_c = st.columns([1.2, 1, 1.2, 1, 1, 1.5])
    
    r_c[0].markdown(f"**{hr}**")
    
    # 评分
    s_val = str(current_records[i]["score"])
    r_c[1].selectbox("评", options=score_options, 
                   index=score_options.index(s_val) if s_val in score_options else 0,
                   key=f"in_{d_str_c}_{i}_score", on_change=sync_val, args=(d_str_c, i, "score"),
                   label_visibility="collapsed")
    
    # 缓释基数 (08:00 和 20:00)
    if i == 0 or i == 12:
        r_c[2].number_input("基", min_value=0.0, step=10.0, 
                          value=float(current_records[i]["base_dose"]),
                          key=f"in_{d_str_c}_{i}_base_dose", on_change=sync_val, args=(d_str_c, i, "base_dose"),
                          label_visibility="collapsed")
    else:
        r_c[2].write("")

    # 追加
    t_val = current_records[i]["type"]
    r_c[3].selectbox("种", options=drug_opts if 'drug_opts' in locals() else drug_options,
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

# --- 底部结算 ---
st.divider()
res_total, am_next, pm_next = get_day_results(current_records)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("今日追加总计", f"{res_total} mg")
with c2:
    st.success(f"📅 明日建议(早 08:00)：{am_next} mg")
with c3:
    st.success(f"📅 明日建议(晚 20:00)：{pm_next} mg")

# 如果承接了昨天的建议，给予提示
if am_suggest > 0 or pm_suggest > 0:
    st.info(f"💡 系统已自动将昨日推算的建议量 ({am_suggest}/{pm_suggest}) 填充至今日基数列，您可以根据临床实际进行微调。")