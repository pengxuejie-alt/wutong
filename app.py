import streamlit as st
import pandas as pd
import math
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="梧桐-疼痛管理", layout="wide", page_icon="🌿")

# --- 核心算法 ---
def round_dose(dose):
    """四舍五入至10的倍数，最小10mg"""
    if dose is None or dose <= 0: return 0
    rounded = math.floor(dose / 10 + 0.5) * 10
    return max(10, int(rounded))

def get_day_results(df, am_base, pm_base):
    """计算加药总量和次日建议，增加防御性检查"""
    # 检查列是否存在，防止旧数据导致 KeyError
    col_name = '追加剂量(mg)'
    if col_name not in df.columns:
        # 如果是旧版数据，尝试找旧列名，否则视为0
        if '加药量(mg)' in df.columns:
            col_name = '加药量(mg)'
        else:
            return 0, round_dose(am_base), round_dose(pm_base)

    # 1. 计算追加用药量
    rescue_total = pd.to_numeric(df[col_name], errors='coerce').fillna(0).sum()
    
    # 2. 提取评分用于减量逻辑
    numeric_scores = []
    for s in df['评分'] if '评分' in df.columns else [""]*24:
        s_str = str(s).strip()
        if s_str in ["睡觉", "", "None", "nan", "未记录"]:
            numeric_scores.append(0)
        else:
            try:
                numeric_scores.append(float(s_str))
            except:
                numeric_scores.append(0)
    
    # 3. 计算次日基数
    curr_am = am_base if am_base else 0
    curr_pm = pm_base if pm_base else 0
    total_today = curr_am + curr_pm + rescue_total
    base_next = total_today / 2
    
    # 4. 减量判定：12h内没有任何评分 >= 1
    def check_halve(scores):
        if not scores: return False
        return all(x < 1 for x in scores)

    next_am = base_next / 2 if check_halve(numeric_scores[0:12]) else base_next
    next_pm = base_next / 2 if check_halve(numeric_scores[12:24]) else base_next
    
    return rescue_total, round_dose(next_am), round_dose(next_pm)

# --- 数据初始化 ---
if 'all_days_data' not in st.session_state:
    st.session_state.all_days_data = {}
if 'target_date' not in st.session_state:
    st.session_state.target_date = datetime.now().date()

# --- 日期准备 ---
curr_d = st.session_state.target_date
prev_d = curr_d - timedelta(days=1)
next_d = curr_d + timedelta(days=1)

hours = [f"{i:02d}:00-{i+1:02d}:00" for i in range(24)]
display_hours = hours[8:] + hours[:8]

# 统一列名定义
REQUIRED_COLUMNS = ["时间段", "评分", "用药种类", "追加剂量(mg)", "备注"]

for d in [prev_d, curr_d, next_d]:
    ds = str(d)
    if ds not in st.session_state.all_days_data:
        st.session_state.all_days_data[ds] = {
            "df": pd.DataFrame({
                "时间段": display_hours,
                "评分": [""] * 24,
                "用药种类": [""] * 24,
                "追加剂量(mg)": [0.0] * 24,
                "备注": [""] * 24
            }),
            "am_base": None,
            "pm_base": None
        }
    else:
        # 数据结构自动补齐/迁移（解决报错的关键）
        existing_df = st.session_state.all_days_data[ds]["df"]
        if "追加剂量(mg)" not in existing_df.columns:
            if "加药量(mg)" in existing_df.columns:
                existing_df = existing_df.rename(columns={"加药量(mg)": "追加剂量(mg)"})
            else:
                existing_df["追加剂量(mg)"] = 0.0
        st.session_state.all_days_data[ds]["df"] = existing_df

# --- 侧边栏 ---
with st.sidebar:
    st.title("🌿 梧桐疼痛管理")
    st.session_state.target_date = st.date_input("📅 日期跳转", value=st.session_state.target_date)
    st.markdown("""
    <div style="font-size: 12px; color: #666; background-color: #f8f9fa; padding: 10px; border-radius: 5px;">
    <b>📋 核心逻辑</b><br>
    - 评分 ≥4: +10mg | ≥8: +20mg<br>
    - 次日建议: 昨日总和 / 2<br>
    - 无痛减半: 12h内评分均 <1
    </div>
    """, unsafe_allow_html=True)
    if st.button("重置系统 (清除报错)"):
        st.session_state.all_days_data = {}
        st.rerun()

# --- 主界面 ---
st.header(f"📅 疼痛记录：{curr_d}")

d_str_c = str(curr_d)
d_str_p = str(prev_d)

# 尝试获取昨天的数据
prev_day_obj = st.session_state.all_days_data.get(d_str_p)
has_prev_data = prev_day_obj and prev_day_obj["am_base"] is not None

if has_prev_data:
    # 自动继承昨天算出的建议
    res_p, am_suggest, pm_suggest = get_day_results(
        prev_day_obj["df"], prev_day_obj["am_base"], prev_day_obj["pm_base"]
    )
    st.session_state.all_days_data[d_str_c]["am_base"] = am_suggest
    st.session_state.all_days_data[d_str_c]["pm_base"] = pm_suggest
    st.success(f"📈 承接昨日建议：早 **{am_suggest}mg** / 晚 **{pm_suggest}mg**")
else:
    # 强制用户输入初始量
    st.warning("⚠️ 初始剂量缺失，请手动输入起始用药量：")
    col_i1, col_i2 = st.columns(2)
    with col_i1:
        val_am = st.number_input("今日早 08:00 基数 (mg)", min_value=0, value=0, step=10, key="manual_am")
        st.session_state.all_days_data[d_str_c]["am_base"] = val_am
    with col_i2:
        val_pm = st.number_input("今日晚 20:00 基数 (mg)", min_value=0, value=0, step=10, key="manual_pm")
        st.session_state.all_days_data[d_str_c]["pm_base"] = val_pm

# --- 24小时录入表 ---
st.subheader("⏺️ 详细体征与用药记录")
edited_df = st.data_editor(
    st.session_state.all_days_data[d_str_c]["df"],
    column_config={
        "时间段": st.column_config.TextColumn(disabled=True),
        "评分": st.column_config.SelectboxColumn("疼痛评分", options=["睡觉", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]),
        "用药种类": st.column_config.SelectboxColumn("药物种类", options=["吗啡", "芬太尼", "其他"]),
        "追加剂量(mg)": st.column_config.NumberColumn("追加剂量(mg)", min_value=0, step=5),
        "备注": st.column_config.TextColumn("详细备注")
    },
    hide_index=True,
    use_container_width=True,
    key=f"editor_v2_{d_str_c}"
)
st.session_state.all_days_data[d_str_c]["df"] = edited_df

# --- 结算与预估 ---
res_c, am_next, pm_next = get_day_results(
    edited_df, 
    st.session_state.all_days_data[d_str_c]["am_base"], 
    st.session_state.all_days_data[d_str_c]["pm_base"]
)

st.divider()
c_res1, c_res2, c_res3 = st.columns(3)
with c_res1:
    st.write(f"今日执行基数: **{st.session_state.all_days_data[d_str_c]['am_base']} / {st.session_state.all_days_data[d_str_c]['pm_base']}**")
with c_res2:
    st.write(f"今日追加总计: **{res_c} mg**")
with c_res3:
    st.write(f"次日预测 (早/晚): **{am_next} / {pm_next} mg**")