import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="梧桐-疼痛管理(Excel增强版)", layout="wide", page_icon="🌿")

# --- 自定义 CSS 样式 ---
st.markdown("""
    <style>
    .rule-box { font-size: 12px; color: #666; background-color: #f0f2f6; padding: 10px; border-radius: 5px; line-height: 1.5; }
    [data-testid="stMetricValue"] { font-size: 24px; }
    </style>
""", unsafe_allow_html=True)

# --- 核心算法 ---
def round_dose(dose):
    if dose <= 0: return 0
    # 实现 25 -> 30 逻辑，且最小为 10mg
    rounded = math.floor(dose / 10 + 0.5) * 10
    return max(10, int(rounded))

def get_day_results(df, am_base, pm_base):
    """计算当天的加药总量和次日早晚的基数建议"""
    rescue_total = 0
    numeric_scores = []
    
    # 遍历 DataFrame 处理评分
    for s in df['评分']:
        s_str = str(s).strip()
        if s_str == "睡觉" or s_str == "" or s is None or s_str == "nan":
            numeric_scores.append(None)
        else:
            try:
                val = float(s_str)
                numeric_scores.append(val)
                # 增加用药逻辑：>=8 加20mg，>=4 加10mg
                if val >= 8: rescue_total += 20
                elif val >= 4: rescue_total += 10
            except:
                numeric_scores.append(None)
    
    total_today = am_base + pm_base + rescue_total
    base_next = total_today / 2
    
    # 减量逻辑（12小时判断）
    # 白天：08:00 - 20:00 (索引 0-11)
    # 晚上：20:00 - 08:00 (索引 12-23)
    day_slice = numeric_scores[0:12]
    night_slice = numeric_scores[12:24]
    
    # 只有明确填写了 0 且整个区间没有非0记录时才触发减量
    def check_halve(scores):
        has_zero = any(x == 0 for x in scores if x is not None)
        has_pain = any(x > 0 for x in scores if x is not None)
        return has_zero and not has_pain

    next_am = base_next / 2 if check_halve(day_slice) else base_next
    next_pm = base_next / 2 if check_halve(night_slice) else base_next
    
    return rescue_total, round_dose(next_am), round_dose(next_pm)

# --- 数据初始化 ---
if 'all_days_data' not in st.session_state:
    st.session_state.all_days_data = {}
if 'target_date' not in st.session_state:
    st.session_state.target_date = datetime.now().date()

# --- 日期控制函数 ---
def set_date(new_date):
    st.session_state.target_date = new_date

# --- 处理日期关联 ---
curr_d = st.session_state.target_date
prev_d = curr_d - timedelta(days=1)
next_d = curr_d + timedelta(days=1)

# 初始化 24 小时结构
hours = [f"{i:02d}:00-{i+1:02d}:00" for i in range(24)]
display_hours = hours[8:] + hours[:8] # 从早 08:00 开始

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
    # 日历跳转
    selected_calendar_date = st.date_input("📅 跳转日期", value=st.session_state.target_date)
    if selected_calendar_date != st.session_state.target_date:
        set_date(selected_calendar_date)
        st.rerun()
    
    st.subheader("📋 用药规则")
    st.markdown(f"""
    <div class="rule-box">
    <b>1. 基础剂量：</b><br>
    次日早晚基数 = 昨日总剂量(早+晚+临时) / 2。<br><br>
    <b>2. 增加(爆发痛)：</b><br>
    - 评分 <b>≥ 4</b>: 当小时 +10mg<br>
    - 评分 <b>≥ 8</b>: 当小时 +20mg<br><br>
    <b>3. 减少(无痛)：</b><br>
    - 12h内(早8-晚8或晚8-早8)全部记录为 0 时，对应半天减半。<br>
    - “睡觉”或“留空”视为维持，不减药。<br><br>
    <b>4. 修正：</b><br>
    最小 10mg，四舍五入至 10 的倍数。
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    if st.button("🗑️ 清空所有记录"):
        st.session_state.all_days_data = {}
        st.rerun()

# --- 计算链条 ---
# 昨天影响今天
res_p, am_c, pm_c = get_day_results(st.session_state.all_days_data[str(prev_d)]["df"], 
                                     st.session_state.all_days_data[str(prev_d)]["am_base"], 
                                     st.session_state.all_days_data[str(prev_d)]["pm_base"])
st.session_state.all_days_data[str(curr_d)]["am_base"] = am_c
st.session_state.all_days_data[str(curr_d)]["pm_base"] = pm_c

# 今天编辑的数据
curr_df = st.session_state.all_days_data[str(curr_d)]["df"]

# --- 主界面 ---
st.header(f"📅 疼痛管理：{curr_d}")

col_l, col_m, col_r = st.columns([1, 2.5, 1])

# 1. 昨日卡片
with col_l:
    st.subheader("⬅️ 昨日概览")
    with st.container(border=True):
        st.write(f"日期: **{prev_d}**")
        st.metric("执行剂量", f"{st.session_state.all_days_data[str(prev_d)]['am_base']} / {st.session_state.all_days_data[str(prev_d)]['pm_base']}")
        st.write(f"加药量: **{res_p} mg**")
        st.button("↩️ 切换至昨日", on_click=set_date, args=(prev_d,), use_container_width=True)

# 2. 今日 Excel 编辑区
with col_m:
    st.subheader("⏺️ 今日编辑区")
    st.info(f"今日基础：早 **{am_c}mg** / 晚 **{pm_c}mg**")

    # 批量工具
    with st.expander("⚡ Excel 批量填充工具"):
        f_c1, f_c2, f_c3 = st.columns([1, 1, 1])
        q_val = f_c1.selectbox("选值", options=["睡觉", "0", "1", "2", "3", "5", "8", "10"])
        q_range = f_c2.selectbox("区间", options=["全天", "白天(08-20)", "晚上(20-08)"])
        if f_c3.button("执行填充", use_container_width=True):
            if q_range == "全天": idxs = range(24)
            elif q_range == "白天(08-20)": idxs = range(12)
            else: idxs = range(12, 24)
            for i in idxs:
                st.session_state.all_days_data[str(curr_d)]["df"].at[i, "评分"] = q_val
            st.rerun()

    # Data Editor
    edited_df = st.data_editor(
        curr_df,
        column_config={
            "时间段": st.column_config.TextColumn(disabled=True),
            "评分": st.column_config.SelectboxColumn("评分", options=["睡觉", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]),
            "止痛处理": st.column_config.TextColumn("止痛处理", placeholder="如：速效吗啡10mg")
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_{curr_d}"
    )
    # 实时保存回 session
    st.session_state.all_days_data[str(curr_d)]["df"] = edited_df

# 3. 明日预测
res_c, am_n, pm_n = get_day_results(edited_df, am_c, pm_c)

with col_r:
    st.subheader("➡️ 明日预判")
    with st.container(border=True):
        st.write(f"日期: **{next_d}**")
        st.metric("预测早剂量", f"{am_n} mg")
        st.metric("预测晚剂量", f"{pm_n} mg")
        st.write(f"今日加药总计: **{res_c} mg**")
        st.button("➡️ 切换至明日", on_click=set_date, args=(next_d,), use_container_width=True)

st.divider()
if st.button("📥 导出历史记录报表"):
    summary = []
    for d_str, val in sorted(st.session_state.all_days_data.items()):
        if not val['df']['评分'].astype(str).eq("").all():
            r, _, _ = get_day_results(val['df'], val['am_base'], val['pm_base'])
            summary.append({"日期": d_str, "早": val['am_base'], "晚": val['pm_base'], "加药": r, "总计": val['am_base']+val['pm_base']+r})
    st.table(pd.DataFrame(summary))