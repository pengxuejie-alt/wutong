import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="梧桐-疼痛管理(临床版)", layout="wide", page_icon="🌿")

# --- 核心算法 ---
def round_dose(dose):
    """四舍五入至10的倍数，最小10mg"""
    if dose <= 0: return 0
    rounded = math.floor(dose / 10 + 0.5) * 10
    return max(10, int(rounded))

def get_day_results(df, am_base, pm_base):
    """计算加药总量和次日建议"""
    # 1. 计算这一天所有的追加用药量
    rescue_total = pd.to_numeric(df['追加剂量(mg)'], errors='coerce').fillna(0).sum()
    
    # 2. 提取评分用于减量逻辑
    numeric_scores = []
    for s in df['评分']:
        s_str = str(s).strip()
        if s_str in ["睡觉", "", "None", "nan"]:
            numeric_scores.append(0)
        else:
            try:
                numeric_scores.append(float(s_str))
            except:
                numeric_scores.append(0)
    
    # 3. 计算次日基数
    total_today = am_base + pm_base + rescue_total
    base_next = total_today / 2
    
    # 4. 减量判定：12h内没有任何评分 >= 1
    def check_halve(scores):
        return all(x < 1 for x in scores)

    next_am = base_next / 2 if check_halve(numeric_scores[0:12]) else base_next
    next_pm = base_next / 2 if check_halve(numeric_scores[12:24]) else base_next
    
    return rescue_total, round_dose(next_am), round_dose(next_pm)

# --- 数据初始化 ---
if 'all_days_data' not in st.session_state:
    st.session_state.all_days_data = {}
if 'target_date' not in st.session_state:
    st.session_state.target_date = datetime.now().date()

# --- 核心逻辑：日期数据准备 ---
curr_d = st.session_state.target_date
prev_d = curr_d - timedelta(days=1)
next_d = curr_d + timedelta(days=1)

hours = [f"{i:02d}:00-{i+1:02d}:00" for i in range(24)]
display_hours = hours[8:] + hours[:8]

for d in [prev_d, curr_d, next_d]:
    ds = str(d)
    if ds not in st.session_state.all_days_data:
        st.session_state.all_days_data[ds] = {
            "df": pd.DataFrame({
                "时间段": display_hours,
                "评分": [""] * 24,
                "药物种类": ["" for _ in range(24)],
                "追加剂量(mg)": [0.0] * 24,
                "备注": [""] * 24
            }),
            "am_base": None, # 设为 None，表示尚未填写
            "pm_base": None
        }

# --- 侧边栏：规则 ---
with st.sidebar:
    st.title("🌿 梧桐疼痛管理")
    st.session_state.target_date = st.date_input("📅 日期跳转", value=st.session_state.target_date)
    st.markdown("""
    <div style="font-size: 12px; color: #666; background-color: #f8f9fa; padding: 10px; border-radius: 5px; border: 1px solid #eee;">
    <b>📋 计算规则</b><br>
    1. <b>总药量：</b>早缓释 + 晚缓释 + 全天追加总剂量。<br>
    2. <b>次日建议：</b>昨日总药量 / 2。<br>
    3. <b>评分 ≥4：</b>推荐追加 10mg 速效。<br>
    4. <b>评分 ≥8：</b>推荐追加 20mg 速效。<br>
    5. <b>无痛减量：</b>12h内评分均 <1，对应半天减半。
    </div>
    """, unsafe_allow_html=True)
    if st.button("重置系统"):
        st.session_state.all_days_data = {}
        st.rerun()

# --- 主界面 ---
st.header(f"📅 疼痛记录：{curr_d}")

# 1. 初始剂量输入 (如果当天没有前序计算值)
d_str_c = str(curr_d)
d_str_p = str(prev_d)

# 尝试从昨天计算今天的剂量
res_p, am_suggest, pm_suggest = get_day_results(
    st.session_state.all_days_data[d_str_p]["df"],
    st.session_state.all_days_data[d_str_p]["am_base"] if st.session_state.all_days_data[d_str_p]["am_base"] else 0,
    st.session_state.all_days_data[d_str_p]["pm_base"] if st.session_state.all_days_data[d_str_p]["pm_base"] else 0
)

# 确定今天的基数
if st.session_state.all_days_data[d_str_p]["am_base"] is not None:
    # 如果昨天有数据，自动继承建议
    st.session_state.all_days_data[d_str_c]["am_base"] = am_suggest
    st.session_state.all_days_data[d_str_c]["pm_base"] = pm_suggest
    st.info(f"💡 根据昨日记录，今日初始剂量建议为：早 **{am_suggest}mg** / 晚 **{pm_suggest}mg**")
else:
    # 否则，要求用户手动输入第一天的剂量
    st.warning("⚠️ 检测到今日为首日或前日无记录，请先输入初始用药量：")
    col_init1, col_init2 = st.columns(2)
    with col_init1:
        st.session_state.all_days_data[d_str_c]["am_base"] = st.number_input("今日早 08:00 初始量 (mg)", min_value=0, value=0, step=10)
    with col_init2:
        st.session_state.all_days_data[d_str_c]["pm_base"] = st.number_input("今日晚 20:00 初始量 (mg)", min_value=0, value=0, step=10)

# 2. 核心编辑表
st.write("---")
col_edit, col_side = st.columns([4, 1])

with col_edit:
    st.subheader("⏺️ 24小时明细录入")
    edited_df = st.data_editor(
        st.session_state.all_days_data[d_str_c]["df"],
        column_config={
            "时间段": st.column_config.TextColumn(disabled=True),
            "评分": st.column_config.SelectboxColumn("疼痛评分", options=["睡觉", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]),
            "药物种类": st.column_config.SelectboxColumn("用药种类", options=["", "吗啡", "芬太尼", "其他"]),
            "追加剂量(mg)": st.column_config.NumberColumn("追加剂量(mg)", min_value=0, step=5),
            "备注": st.column_config.TextColumn("详细备注")
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_{d_str_c}"
    )
    st.session_state.all_days_data[d_str_c]["df"] = edited_df

# 3. 结果显示
res_c, am_n, pm_n = get_day_results(
    st.session_state.all_days_data[d_str_c]["df"],
    st.session_state.all_days_data[d_str_c]["am_base"] if st.session_state.all_days_data[d_str_c]["am_base"] else 0,
    st.session_state.all_days_data[d_str_c]["pm_base"] if st.session_state.all_days_data[d_str_c]["pm_base"] else 0
)

with col_side:
    st.subheader("📊 今日结算")
    with st.container(border=True):
        st.write(f"日期: {curr_d}")
        st.write(f"早/晚基数: {st.session_state.all_days_data[d_str_c]['am_base']}/{st.session_state.all_days_data[d_str_c]['pm_base']}")
        st.write(f"今日追加总计: **{res_c} mg**")
        st.divider()
        st.write("➡️ **次日预估**")
        st.metric("明早 08:00", f"{am_n} mg")
        st.metric("明晚 20:00", f"{pm_n} mg")