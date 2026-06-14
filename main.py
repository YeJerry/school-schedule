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
                    if not st.session_state.fixed_lessons_by_grade[g]:
                        del st.session_state.fixed_lessons_by_grade[g]
                    st.rerun()
                
    st.markdown("---")
    
    # 區塊 B：領域共同時間鎖定
    st.subheader("👥 2-2. 領域/科目共同不排課設定")
    if subject_list:
        selected_subj = st.selectbox("選擇要設定領域會議的【科目】", ["請選擇"] + subject_list)
        if selected_subj != "請選擇":
            if selected_subj not in st.session_state.subject_blocked_times:
                st.session_state.subject_blocked_times[selected_subj] = []
            
            subj_day = st.selectbox("選擇領域會議星期幾", days, key="subj_day")
            new_subj_blocks = [b for b in st.session_state.subject_blocked_times[selected_subj] if not b.startswith(subj_day)]
            
            st.write(f"請勾選 **{selected_subj}科** 領域會議（不排課）的時段：")
            for p in periods:
                slot_id = f"{subj_day}_{p}"
                is_blocked = slot_id in st.session_state.subject_blocked_times[selected_subj]
                if st.checkbox(f"❌ {p} 領域時間", value=is_blocked, key=f"subj_{selected_subj}_{slot_id}"):
                    new_subj_blocks.append(slot_id)
            st.session_state.subject_blocked_times[selected_subj] = new_subj_blocks
    else: st.info("請先至步驟 1 上傳資料。")
        
    st.markdown("---")
    
    # 區塊 C：個人與班級不排課
    st.subheader("👤 2-3. 個人或班級特殊不排課設定")
    if class_list or teacher_list:
        target = st.selectbox("選擇對象（特定老師或個別班級）", ["請選擇"] + teacher_list + class_list)
        if target != "請選擇":
            if target not in st.session_state.blocked_times:
                st.session_state.blocked_times[target] = []
            
            selected_day = st.selectbox("選擇星期幾", days, key="indiv_day")
            new_blocks = [b for b in st.session_state.blocked_times[target] if not b.startswith(selected_day)]
            
            st.write(f"請點選 **{target}** 的【個別不可排課】時段：")
            for p in periods:
                slot_id = f"{selected_day}_{p}"
                is_blocked = slot_id in st.session_state.blocked_times[target]
                if st.checkbox(f"❌ {p} 不排課", value=is_blocked, key=f"m_{target}_{slot_id}"):
                    new_blocks.append(slot_id)
            st.session_state.blocked_times[target] = new_blocks

# --- 頁面 3：智慧排課與雙向匯出 ---
with main_tabs[2]:
    st.subheader("⚡ 執行自動排課")
    if st.session_state.teachers_data.empty:
        st.warning("請先完成資料匯入！")
    else:
        if st.button("🔥 啟動高級排課引擎", type="primary", use_container_width=True):
            with st.spinner("智慧排課進行中（正在嚴格控管非連排不連堂與分年級固定課）..."):
                schedules = {c: pd.DataFrame("", index=periods, columns=days) for c in class_list}
                teacher_timetable = {(d, p): [] for d in days for p in periods}
                teacher_schedules = {t: pd.DataFrame("", index=periods, columns=days) for t in teacher_list}
                
                # 輔助函式：找出班級適用哪一個年級的固定課程
                def get_fixed_lesson_for_class(c_name, d, p):
                    slot_key = f"{d}_{p}"
                    for grade_prefix, slots in st.session_state.fixed_lessons_by_grade.items():
                        if c_name.startswith(grade_prefix): # 如果班級開頭符合年級識別字
                            if slot_key in slots:
                                return slots[slot_key]
                    return None

                # 【核心步驟 1】：優先將各年級「固定課程」填入對應班級的課表
                for c in class_list:
                    for d in days:
                        for p in periods:
                            fixed_name = get_fixed_lesson_for_class(c, d, p)
                            if fixed_name:
                                schedules[c].loc[p, d] = f"【{fixed_name}】"
                
                # 分類排課池 (連排與單堂)
                double_lessons = []
                single_lessons = []
                for _, row in st.session_state.teachers_data.iterrows():
                    c, t, s, hours = str(row["任教班級"]), str(row["老師姓名"]), str(row["科目"]), int(row["每週堂數"])
                    if str(row["需要連排(對/錯)"]) == "對":
                        for _ in range(hours // 2): double_lessons.append({"class": c, "teacher": t, "subject": s})
                        if hours % 2 == 1: single_lessons.append({"class": c, "teacher": t, "subject": s})
                    else:
                        for _ in range(hours): single_lessons.append({"class": c, "teacher": t, "subject": s})
                
                # 核心檢查函式
                def can_place(c, t, s, d, p, is_part_of_double=False):
                    slot_str = f"{d}_{p}"
                    # 1. 檢查是否已被固定課程佔用
                    if get_fixed_lesson_for_class(c, d, p) is not None: return False
                    # 2. 檢查領域與個人限制
                    if s in st.session_state.subject_blocked_times and slot_str in st.session_state.subject_blocked_times[s]: return False
                    if t in st.session_state.blocked_times and slot_str in st.session_state.blocked_times[t]: return False
                    if c in st.session_state.blocked_times and slot_str in st.session_state.blocked_times[c]: return False
                    # 3. 檢查基本衝堂
                    if schedules[c].loc[p, d] != "" or t in teacher_timetable[(d, p)]: return False
                    # 4. 檢查每日堂數上限
                    if sum(1 for lesson in schedules[c][d].values if s in str(lesson)) >= 2: return False
                    
                    # 💥 關鍵修改：非連排課程，絕對不可連堂！
                    # 如果這是一堂「單堂課」，檢查它跟「上一節」或「下一節」是不是同一門科目
                    if not is_part_of_double:
                        p_idx = periods.index(p)
                        if p_idx > 0: # 檢查前一節
                            if s in str(schedules[c].loc[periods[p_idx-1], d]): return False
                        if p_idx < len(periods) - 1: # 檢查後一節
                            if s in str(schedules[c].loc[periods[p_idx+1], d]): return False
                            
                    return True

                # A. 排連排課
                for lesson in double_lessons:
                    c, t, s = lesson["class"], lesson["teacher"], lesson["subject"]
                    placed = False
                    for d in days:
                        for p1, p2 in valid_pairs:
                            if can_place(c, t, s, d, p1, is_part_of_double=True) and can_place(c, t, s, d, p2, is_part_of_double=True):
                                if sum(1 for l in schedules[c][d].values if s in str(l)) == 0:
                                    schedules[c].loc[p1, d] = f"{s}\n({t})"
                                    schedules[c].loc[p2, d] = f"{s}連\n({t})"
                                    teacher_schedules[t].loc[p1, d] = f"{s}\n({c})"
                                    teacher_schedules[t].loc[p2, d] = f"{s}連\n({c})"
                                    teacher_timetable[(d, p1)].append(t)
                                    teacher_timetable[(d, p2)].append(t)
                                    placed = True
                                    break
                        if placed: break

                # B. 排單堂課 (嚴格防連堂)
                for lesson in single_lessons:
                    c, t, s = lesson["class"], lesson["teacher"], lesson["subject"]
                    placed = False
                    for d in days:
                        for p in periods:
                            if can_place(c, t, s, d, p, is_part_of_double=False):
                                schedules[c].loc[p, d] = f"{s}\n({t})"
                                teacher_schedules[t].loc[p, d] = f"{s}\n({c})"
                                teacher_timetable[(d, p)].append(t)
                                placed = True
                                break
                        if placed: break

                st.success("🎉 智慧排課完成！已成功阻斷非連排課程連堂，並完成年級固定課分流。")
                st.session_state.final_schedules = schedules
                st.session_state.final_teacher_schedules = teacher_schedules

        # 顯示與匯出結果
        if 'final_schedules' in st.session_state:
            st.markdown("### 📅 網頁線上查閱")
            view_mode = st.radio("請選擇查閱模式", ["看班級課表", "看老師個人課表"])
            if view_mode == "看班級課表":
                view_c = st.selectbox("選擇班級", class_list)
                st.dataframe(st.session_state.final_schedules[view_c], use_container_width=True)
            else:
                view_t = st.selectbox("選擇老師", teacher_list)
                st.dataframe(st.session_state.final_teacher_schedules[view_t], use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for c_name, c_table in st.session_state.final_schedules.items():
                    c_table.to_excel(writer, sheet_name=f"{c_name}_課表")
                for t_name, t_table in st.session_state.final_teacher_schedules.items():
                    t_table.to_excel(writer, sheet_name=f"{t_name}_課表")
            
            st.markdown("---")
            st.download_button(
                label="📥 匯出全校總課表 (Excel)",
                data=output.getvalue(),
                file_name="全校功課表總匯出結果.xlsx",
                mime="application/vnd.ms-excel",
                type="primary",
                use_container_width=True
            )
