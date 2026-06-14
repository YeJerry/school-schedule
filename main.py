import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="學校全自動排課系統 Pro", layout="centered")
st.title("📱 學校自動排課系統 (年級群組版)")

# ----------------- 系統基本時段設定 -----------------
st.sidebar.header("⚙️ 系統基本時段設定")
days = ["週一", "週二", "週三", "週四", "週五"]
total_periods = st.sidebar.slider("請設定學校每天總共有幾節課？", min_value=5, max_value=9, value=7)
periods = [f"第{i}節" for i in range(1, total_periods + 1)]

# 自動生成連排組合（避開第4節接第5節）
valid_pairs = []
for i in range(1, total_periods):
    if i == 4: continue
    valid_pairs.append((f"第{i}節", f"第{i+1}節"))

# 初始化 Session State
if 'teachers_data' not in st.session_state:
    st.session_state.teachers_data = pd.DataFrame(columns=["任教班級", "老師姓名", "科目", "每週堂數", "需要連排(對/錯)"])
if 'blocked_times' not in st.session_state:
    st.session_state.blocked_times = {} 
if 'subject_blocked_times' not in st.session_state:
    st.session_state.subject_blocked_times = {} 
# 升級：固定課程改為依據「年級關鍵字」儲存 格式: {"高一": {"週五_第5節": "社團"}}
if 'fixed_lessons_by_grade' not in st.session_state:
    st.session_state.fixed_lessons_by_grade = {}

# 操作分頁
main_tabs = st.tabs(["📥 1. 匯入資料", "🚫 2. 各項排課限制設定", "🚀 3. 智慧排課與匯出"])

# --- 頁面 1：匯入資料 ---
with main_tabs[0]:
    st.subheader("📁 上傳全校排課資料")
    uploaded_file = st.file_uploader("📤 選擇 Excel 檔案", type=["xlsx"])
    if uploaded_file is not None:
        st.session_state.teachers_data = pd.read_excel(uploaded_file)
        st.success("資料載入成功！")
    
    if not st.session_state.teachers_data.empty:
        st.markdown("**目前資料庫概況：**")
        st.dataframe(st.session_state.teachers_data, use_container_width=True)

# --- 頁面 2：排課限制設定 ---
with main_tabs[1]:
    class_list = sorted(list(set(st.session_state.teachers_data["任教班級"].dropna().astype(str)))) if not st.session_state.teachers_data.empty else []
    teacher_list = sorted(list(set(st.session_state.teachers_data["老師姓名"].dropna().astype(str)))) if not st.session_state.teachers_data.empty else []
    subject_list = sorted(list(set(st.session_state.teachers_data["科目"].dropna().astype(str)))) if not st.session_state.teachers_data.empty else []
    
    # 💥 升級區塊 A：依年級設定固定課程
    st.subheader("📌 2-1. 依年級設定固定課程 (如班會、社團)")
    st.write("設定後，只要班級名稱**開頭符合**該字眼（例如輸入 `一`，則一忠、一孝都會套用），該時段就會強制排入：")
    
    col_f0, col_f1, col_f2, col_f3 = st.columns(4)
    with col_f0: fixed_grade = st.text_input("年級識別字", placeholder="如：一 或 七 或 高一")
    with col_f1: fixed_day = st.selectbox("選擇星期", days, key="f_day")
    with col_f2: fixed_period = st.selectbox("選擇節次", periods, key="f_per")
    with col_f3: fixed_name = st.text_input("課程名稱", placeholder="例如：社團課")
    
    if st.button("➕ 新增/更新該年級固定課程", use_container_width=True):
        if fixed_grade and fixed_name:
            if fixed_grade not in st.session_state.fixed_lessons_by_grade:
                st.session_state.fixed_lessons_by_grade[fixed_grade] = {}
            slot_key = f"{fixed_day}_{fixed_period}"
            st.session_state.fixed_lessons_by_grade[fixed_grade][slot_key] = fixed_name
            st.toast(f"已設定【{fixed_grade}】年級 {fixed_day}{fixed_period} 為【{fixed_name}】")
        else:
            st.error("請輸入年級識別字與課程名稱！")
            
    if st.session_state.fixed_lessons_by_grade:
        st.markdown("**目前已設定的年級固定課程：**")
        for g, slots in list(st.session_state.fixed_lessons_by_grade.items()):
            for k, v in list(slots.items()):
                d_p = k.split("_")
                if st.button(f"🗑️ 刪除【{g}】{d_p[0]}{d_p[1]}：{v}", key=f"del_{g}_{k}"):
                    del st.session_state.fixed_lessons_by_grade[g][k]
                    if not st.session
