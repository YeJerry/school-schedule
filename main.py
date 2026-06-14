import streamlit as st
import pandas as pd
import io
import random

st.set_page_config(page_title="學校全自動排課系統 Pro", layout="centered")
st.title("📱 學校自動排課系統 (單日單科上限版)")

# ----------------- 系統基本時段設定 -----------------
st.sidebar.header("⚙️ 系統基本時段設定")
days = ["週一", "週二", "週三", "週四", "週五"]
total_periods = st.sidebar.slider("請設定學校每天總共有幾節課？", min_value=5, max_value=9, value=7)
periods = [f"第{i}節" for i in range(1, total_periods + 1)]

valid_pairs = []
for i in range(1, total_periods):
    if i == 4: continue
    valid_pairs.append((f"第{i}節", f"第{i+1}節"))

# 初始化 Session State
if 'teachers_data' not in st.session_state:
    st.session_state.teachers_data = pd.DataFrame(columns=["任教班級", "老師姓名", "科目", "每週堂數", "需要連排(對/錯)", "課程屬性", "所屬領域"])
if 'blocked_times' not in st.session_state:
    st.session_state.blocked_times = {} 
if 'domain_blocked_times' not in st.session_state: 
    st.session_state.domain_blocked_times = {} 
if 'fixed_lessons_by_grade' not in st.session_state:
    st.session_state.fixed_lessons_by_grade = {}

# 取得目前上傳資料中的科目與領域清單
existing_subjects = []
existing_domains = []
if not st.session_state.teachers_data.empty:
    existing_subjects = sorted(list(set(st.session_state.teachers_data["科目"].dropna().astype(str))))
    if "所屬領域" in st.session_state.teachers_data.columns:
        existing_domains = sorted(list(set(st.session_state.teachers_data["所屬領域"].dropna().astype(str))))
    else:
        existing_domains = existing_subjects

# 💥 修改功能：側邊欄改為讓行政人員勾選「一天最多只能有1節」的科目
st.sidebar.markdown("---")
st.sidebar.header("🚫 單日上限 1 節科目設定")
st.sidebar.write("請勾選希望各班【一天最多只能排1節，絕對不重複】的科目（建議勾選國/英/數等主科）：")
max_one_per_day_subjects = []
for sub in existing_subjects:
    # 預設勾選國文、英文、數學，組長可在網頁畫面上自行加勾或取消
    is_default = sub in ["數學", "英文", "國文"]
    if st.sidebar.checkbox(f"🛑 【{sub}】一天最多1節", value=is_default):
        max_one_per_day_subjects.append(sub)

# 操作分頁
main_tabs = st.tabs(["📥 1. 匯入資料", "🚫 2. 各項排課限制設定", "🚀 3. 智慧排課與匯出"])

# --- 頁面 1：匯入資料 ---
with main_tabs[0]:
    st.subheader("📁 上傳全校排課資料")
    uploaded_file = st.file_uploader("📤 選擇 Excel 檔案", type=["xlsx"])
    if uploaded_file is not None:
        st.session_state.teachers_data = pd.read_excel(uploaded_file)
        if "所屬領域" not in st.session_state.teachers_data.columns:
            st.session_state.teachers_data["所屬領域"] = st.session_state.teachers_data["科目"]
        st.success("資料載入成功！")
    
    if not st.session_state.teachers_data.empty:
        st.markdown("**目前資料庫概況：**")
        st.dataframe(st.session_state.teachers_data, use_container_width=True)

# --- 頁面 2：排課限制設定 ---
with main_tabs[1]:
    class_list = sorted(list(set(st.session_state.teachers_data["任教班級"].dropna().astype(str)))) if not st.session_state.teachers_data.empty else []
    teacher_list = sorted(list(set(st.session_state.teachers_data["老師姓名"].dropna().astype(str)))) if not st.session_state.teachers_data.empty else []
    
    # 📌 2-1. 依年級設定固定課程
    st.subheader("📌 2-1. 依年級設定固定課程 (如班會、社團)")
    col_f0, col_f1, col_f2, col_f3 = st.columns(4)
    with col_f0: fixed_grade = st.text_input("年級識別字", placeholder="如：一 或 七")
    with col_f1: fixed_day = st.selectbox("選擇星期", days, key="f_day")
    with col_f2: fixed_period = st.selectbox("選擇節次", periods, key="f_per")
    with col_f3: fixed_name = st.text_input("課程名稱", placeholder="例如：社團課")
    
    if st.button("➕ 新增/更新該年級固定課程", use_container_width=True):
        if fixed_grade and fixed_name:
            if fixed_grade not in st.session_state.fixed_lessons_by_grade:
                st.session_state.fixed_lessons_by_grade[fixed_grade] = {}
            st.session_state.fixed_lessons_by_grade[fixed_grade][f"{fixed_day}_{fixed_period}"] = fixed_name
            st.toast(f"已設定【{fixed_grade}】{fixed_day}{fixed_period} 為【{fixed_name}】")
            
    if st.session_state.fixed_lessons_by_grade:
        for g, slots in list(st.session_state.fixed_lessons_by_grade.items()):
            for k, v in list(slots.items()):
                if st.button(f"🗑️ 刪除【{g}】{k.split('_')[0]}{k.split('_')[1]}：{v}", key=f"del_{g}_{k}"):
                    del st.session_state.fixed_lessons_by_grade[g][k]
                    if not st.session_state.fixed_lessons_by_grade[g]: del st.session_state.fixed_lessons_by_grade[g]
                    st.rerun()
                
    st.markdown("---")
    
    # 📌 2-2. 領域共同時間鎖定
    st.subheader("👥 2-2. 領域共同研習不排課設定 (一鍵鎖定整門領域)")
    if existing_domains:
        selected_dom = st.selectbox("選擇要設定共同研習的【所屬領域】", ["請選擇"] + existing_domains)
        if selected_dom != "請選擇":
            if selected_dom not in st.session_state.domain_blocked_times: st.session_state.domain_blocked_times[selected_dom] = []
            dom_day = st.selectbox("選擇領域會議星期幾", days, key="dom_day")
            new_dom_blocks = [b for b in st.session_state.domain_blocked_times[selected_dom] if not b.startswith(dom_day)]
            
            st.write(f"請勾選 **{selected_dom}** 的共同研習時間：")
            for p in periods:
                slot_id = f"{dom_day}_{p}"
                is_checked = slot_id in st.session_state.domain_blocked_times[selected_dom]
                if st.checkbox(f"❌ {p} 領域共同時間 (不排課)", value=is_checked, key=f"dom_{selected_dom}_{slot_id}"):
                    new_dom_blocks.append(slot_id)
            st.session_state.domain_blocked_times[selected_dom] = new_dom_blocks
            
    st.markdown("---")
    
    # 📌 2-3. 個人與班級不排課
    st.subheader("👤 2-3. 個人或班級特殊不排課設定")
    if class_list or teacher_list:
        target = st.selectbox("選擇對象", ["請選擇"] + teacher_list + class_list)
        if target != "請選擇":
            if target not in st.session_state.blocked_times: st.session_state.blocked_times[target] = []
            selected_day = st.selectbox("選擇星期幾", days, key="indiv_day")
            new_blocks = [b for b in st.session_state.blocked_times[target] if not b.startswith(selected_day)]
            for p in periods:
                if st.checkbox(f"❌ {p} 不排課", value=f"{selected_day}_{p}" in st.session_state.blocked_times[target], key=f"m_{target}_{selected_day}_{p}"):
                    new_blocks.append(f"{selected_day}_{p}")
            st.session_state.blocked_times[target] = new_blocks

# --- 頁面 3：智慧排課與雙向匯出 ---
with main_tabs[2]:
    st.subheader("⚡ 執行自動排課")
    if st.session_state.teachers_data.empty:
        st.warning("請先完成資料匯入！")
    else:
        if st.button("🔥 啟動高級領域平衡排課引擎", type="primary", use_container_width=True):
            with st.spinner("嚴格套用單日科目上限防護中..."):
                
                # 初始化課表結構
                schedules = {c: pd.DataFrame("", index=periods, columns=days) for c in class_list}
                attr_schedules = {c: pd.DataFrame("", index=periods, columns=days) for c in class_list}
                teacher_timetable = {(d, p): [] for d in days for p in periods}
                teacher_schedules = {t: pd.DataFrame("", index=periods, columns=days) for t in teacher_list}
                
                # 建立科目與領域的快速查照表
                subj_to_domain = {}
                for _, row in st.session_state.teachers_data.iterrows():
                    subj_to_domain[str(row["科目"])] = str(row["所屬領域"])

                def get_fixed_lesson_for_class(c_name, d, p):
                    for grade_prefix, slots in st.session_state.fixed_lessons_by_grade.items():
                        if c_name.startswith(grade_prefix) and f"{d}_{p}" in slots: return slots[f"{d}_{p}"]
                    return None

                # 優先填入固定課程
                for c in class_list:
                    for d in days:
                        for p in periods:
                            fixed_name = get_fixed_lesson_for_class(c, d, p)
                            if fixed_name:
                                schedules[c].loc[p, d] = f"【{fixed_name}】"
                                attr_schedules[c].loc[p, d] = "固定"
                
                # 建立隨機排課池（增加成功機率）
                lessons_pool = []
                for _, row in st.session_state.teachers_data.iterrows():
                    c, t, s, hours, attr = str(row["任教班級"]), str(row["老師姓名"]), str(row["科目"]), int(row["每週堂數"]), str(row["課程屬性"])
                    is_double = str(row["需要連排(對/錯)"]) == "對"
                    lessons_pool.append({"class": c, "teacher": t, "subject": s, "attr": attr, "hours": hours, "is_double": is_double})
                
                random.shuffle(lessons_pool)

                double_lessons = []
                single_lessons = []
                for lesson in lessons_pool:
                    c, t, s, hours, attr, is_double = lesson["class"], lesson["teacher"], lesson["subject"], lesson["hours"], lesson["attr"], lesson["is_double"]
                    if is_double:
                        for _ in range(hours // 2): double_lessons.append({"class": c, "teacher": t, "subject": s, "attr": attr})
                        if hours % 2 == 1: single_lessons.append({"class": c, "teacher": t, "subject": s, "attr": attr})
                    else:
                        for _ in range(hours): single_lessons.append({"class": c, "teacher": t, "subject": s, "attr": attr})

                # 核心檢查函式
                def can_place(c, t, s, d, p, attr, is_part_of_double=False):
                    slot_str = f"{d}_{p}"
                    if attr_schedules[c].loc[p, d] != "": return False
                    
                    # 大領域時間檢查
                    dom = subj_to_domain.get(s, s)
                    if dom in st.session_state.domain_blocked_times and slot_str in st.session_state.domain_blocked_times[dom]: return False
                    
                    if t in st.session_state.blocked_times and slot_str in st.session_state.blocked_times[t]: return False
                    if c in st.session_state.blocked_times and slot_str in st.session_state.blocked_times[c]: return False
                    if t in teacher_timetable[(d, p)]: return False
                    
                    # 💥 核心修改：計算該科目在這一天已經排了幾節
                    existing_subject_today = sum(1 for lesson in schedules[c][d].values if s in str(lesson))
                    required_slots = 2 if is_part_of_double else 1
                    
                    # 💥 如果這個科目被行政人员勾選為「一天最多一節」
                    if s in max_one_per_day_subjects:
                        # 對於連排課，我們允許它在同一天佔用 2 節（因為它是連排），但如果不是連排課，或者今天已經有課，就嚴格禁止超過 1
                        if not is_part_of_double and (existing_subject_today + required_slots) > 1:
                            return False
                        if is_part_of_double and existing_subject_today > 0:
                            return False
                    else:
                        # 未被勾選的一般科目，套用之前的標準規範：一天最多 2 節
                        if (existing_subject_today + required_slots) > 2:
                            return False
                    
                    p_idx = periods.index(p)
                    # 嚴格阻斷非連排同科目連堂
                    if not is_part_of_double:
                        if p_idx > 0 and s in str(schedules[c].loc[periods[p_idx-1], d]): return False
                        if p_idx < len(periods) - 1 and s in str(schedules[c].loc[periods[p_idx+1], d]): return False

                    # 考科與藝能科半天數量配額控管
                    is_morning = p_idx < 4
                    half_day_periods = periods[:4] if is_morning else periods[4:]
                    existing_count = sum(1 for p_name in half_day_periods if attr_schedules[c].loc[p_name, d] == attr)
                    
                    if attr == "考科" and (existing_count + required_slots) > 3: return False
                    if attr == "藝能科" and (existing_count + required_slots) > 2: return False
                            
                    return True

                # A. 排連排課
                for lesson in double_lessons:
                    c, t, s, attr = lesson["class"], lesson["teacher"], lesson["subject"], lesson["attr"]
                    placed = False
                    for d in days:
                        for p1, p2 in valid_pairs:
                            if can_place(c, t, s, d, p1, attr, is_part_of_double=True) and can_place(c, t, s, d, p2, attr, is_part_of_double=True):
                                schedules[c].loc[p1, d] = f"{s}\n({t})"
                                schedules[c].loc[p2, d] = f"{s}連\n({t})"
                                attr_schedules[c].loc[p1, d] = attr
                                attr_schedules[c].loc[p2, d] = attr
                                teacher_schedules[t].loc[p1, d] = f"{s}\n({c})"
                                teacher_schedules[t].loc[p2, d] = f"{s}連\n({c})"
                                teacher_timetable[(d, p1)].append(t)
                                teacher_timetable[(d, p2)].append(t)
                                placed = True
                                break
                        if placed: break

                # B. 排單堂課
                for lesson in single_lessons:
                    c, t, s, attr = lesson["class"], lesson["teacher"], lesson["subject"], lesson["attr"]
                    placed = False
                    # 優先嘗試排在目前該科堂數為0的日子，促使分散
                    sorted_days = sorted(days, key=lambda day: sum(1 for l in schedules[c][day].values if s in str(l)))
                    for d in sorted_days:
                        for p in periods:
                            if can_place(c, t, s, d, p, attr, is_part_of_double=False):
                                schedules[c].loc[p, d] = f"{s}\n({t})"
                                attr_schedules[c].loc[p, d] = attr
                                teacher_schedules[t].loc[p, d] = f"{s}\n({c})"
                                teacher_timetable[(d, p)].append(t)
                                placed = True
                                break
                        if placed: break

                st.success("🎉 智慧排課完成！已成功對選定科目套用『一天最多1節』的行政規範。")
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
