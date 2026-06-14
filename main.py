import streamlit as st
import pandas as pd
import io
import random
import traceback

st.set_page_config(page_title="學校全自動排課系統 雙重護欄版", layout="centered")
st.title("📱 學校自動排課系統 (班級不超2節 ＋ 老師一天最多5節驗證版)")

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

# 側邊欄設定
st.sidebar.markdown("---")
st.sidebar.header("🚫 行政安全限制摘要")
st.sidebar.write("🛡️ 班級端：同班級單日同科目 <= 2節")
st.sidebar.write("👨‍🏫 老師端：同老師單日全校總課量 <= 5節")

max_one_per_day_subjects = []
for sub in existing_subjects:
    is_default = sub in ["數學", "英文", "國文"]
    if st.sidebar.checkbox(f"🛑 【{sub}】優先一天最多1節", value=is_default):
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
    
    st.subheader("👥 2-2. 領域共同研習不排課設定")
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
            try:
                max_attempts = 500  # 限制變多，提高迭代次數上限
                attempt = 0
                success_fully_placed = False
                
                status_text = st.empty()
                
                while attempt < max_attempts:
                    attempt += 1
                    status_text.markdown(f"⏳ 正在進行第 **{attempt}** 次全校洗牌，嚴格驗證【班級同科<=2節】與【老師單日<=5節】...")
                    
                    # 1. 初始化全校課表
                    schedules = {c: pd.DataFrame("", index=periods, columns=days) for c in class_list}
                    attr_schedules = {c: pd.DataFrame("", index=periods, columns=days) for c in class_list}
                    teacher_timetable = {(d, p): [] for d in days for p in periods}
                    teacher_schedules = {t: pd.DataFrame("", index=periods, columns=days) for t in teacher_list}
                    
                    # 用來即時追蹤每個老師每天在全校總共排了幾節課的計數器
                    # 格式: { "張老師": { "週一": 0, "週二": 0, ... } }
                    teacher_daily_count = {t: {d: 0 for d in days} for t in teacher_list}
                    
                    subj_to_domain = {}
                    for _, row in st.session_state.teachers_data.iterrows():
                        s_val = str(row.get("科目", "")).strip()
                        d_val = str(row.get("所屬領域", s_val)).strip()
                        if s_val: subj_to_domain[s_val] = d_val

                    def get_fixed_lesson_for_class(c_name, d, p):
                        for grade_prefix, slots in st.session_state.fixed_lessons_by_grade.items():
                            if c_name.startswith(grade_prefix) and f"{d}_{p}" in slots: return slots[f"{d}_{p}"]
                        return None

                    # 填入年級固定課程
                    for c in class_list:
                        for d in days:
                            for p in periods:
                                fixed_name = get_fixed_lesson_for_class(c, d, p)
                                if fixed_name:
                                    schedules[c].loc[p, d] = f"【{fixed_name}】"
                                    attr_schedules[c].loc[p, d] = "固定"
                    
                    # 2. 建立與隨機洗牌排課池
                    lessons_pool = []
                    total_input_lessons = 0
                    for idx, row in st.session_state.teachers_data.iterrows():
                        c = str(row.get("任教班級", f"未知班級_{idx}")).strip()
                        t = str(row.get("老師姓名", f"未知老師_{idx}")).strip()
                        s = str(row.get("科目", "未知科目")).strip()
                        attr = str(row.get("課程屬性", "考科")).strip()
                        if attr not in ["考科", "藝能科"]: attr = "考科"
                        try:
                            hours_val = str(row.get("每週堂數", "1")).split('.')[0].strip()
                            hours = int(hours_val) if hours_val.isdigit() else 1
                        except:
                            hours = 1
                        total_input_lessons += hours
                        is_double = str(row.get("需要連排(對/錯)", "錯")).strip() == "對"
                        lessons_pool.append({"class": c, "teacher": t, "subject": s, "attr": attr, "hours": hours, "is_double": is_double})
                    
                    random.shuffle(lessons_pool)

                    flat_lessons = []
                    for lesson in lessons_pool:
                        c, t, s, hours, attr, is_double = lesson["class"], lesson["teacher"], lesson["subject"], lesson["hours"], lesson["attr"], lesson["is_double"]
                        for _ in range(hours):
                            flat_lessons.append({"class": c, "teacher": t, "subject": s, "attr": attr, "is_double": is_double})

                    # 核心規則檢查函數
                    def can_place(c, t, s, d, p, attr, is_part_of_double=False, strict_level=1, ignore_domain=False):
                        slot_str = f"{d}_{p}"
                        if attr_schedules[c].loc[p, d] != "": return False 
                        if t in st.session_state.blocked_times and slot_str in st.session_state.blocked_times[t]: return False
                        if c in st.session_state.blocked_times and slot_str in st.session_state.blocked_times[c]: return False
                        if t in teacher_timetable[(d, p)]: return False 
                        
                        required_slots = 2 if is_part_of_double else 1
                        
                        # 👨‍🏫 護欄 A：【老師限制】若放進去，該老師這天在全校總節數會不會破 5 節？
                        current_teacher_lessons = teacher_daily_count.get(t, {}).get(d, 0)
                        if (current_teacher_lessons + required_slots) > 5:
                            return False
                            
                        # 🛡️ 護欄 B：【班級限制】該班級該科目今天已經排的堂數，加總不可破 2 節
                        existing_subject_today = sum(1 for lesson in schedules[c][d].values if s in str(lesson))
                        if (existing_subject_today + required_slots) > 2: 
                            return False

                        if strict_level < 4:
                            if not ignore_domain:
                                dom = subj_to_domain.get(s, s)
                                if dom in st.session_state.domain_blocked_times and slot_str in st.session_state.domain_blocked_times[dom]: return False
                            
                            if s in max_one_per_day_subjects:
                                if strict_level == 1:
                                    if not is_part_of_double and (existing_subject_today + required_slots) > 1: return False
                                    if is_part_of_double and existing_subject_today > 0: return False
                            
                            p_idx = periods.index(p)
                            if not is_part_of_double:
                                if p_idx > 0 and s in str(schedules[c].loc[periods[p_idx-1], d]): return False
                                if p_idx < len(periods) - 1 and s in str(schedules[c].loc[periods[p_idx+1], d]): return False
                            
                            is_morning = p_idx < 4
                            half_day_periods = periods[:4] if is_morning else periods[4:]
                            existing_count = sum(1 for p_name in half_day_periods if attr_schedules[c].loc[p_name, d] == attr)
                            if attr == "考科" and (existing_count + required_slots) > 3: return False
                            if attr == "藝能科" and (existing_count + required_slots) > 2: return False
                        return True

                    unplaced_lessons = []
                    double_groups = {}
                    for lesson in flat_lessons:
                        if lesson["is_double"]:
                            key = (lesson["class"], lesson["teacher"], lesson["subject"], lesson["attr"])
                            double_groups[key] = double_groups.get(key, 0) + 1

                    leftover_singles = []
                    paired_doubles = []
                    for key, count in double_groups.items():
                        pairs = count // 2
                        singles = count % 2
                        for _ in range(pairs):
                            paired_doubles.append({"class": key[0], "teacher": key[1], "subject": key[2], "attr": key[3]})
                        for _ in range(singles):
                            leftover_singles.append({"class": key[0], "teacher": key[1], "subject": key[2], "attr": key[3]})

                    all_singles = [l for l in flat_lessons if not l["is_double"]] + leftover_singles

                    # 輔助分配成功的更新器
                    def book_slot(c, t, s, d, p, p_text, attr, is_double_part=1):
                        schedules[c].loc[p, d] = f"{s}{p_text}\n({t})"
                        attr_schedules[c].loc[p, d] = attr
                        teacher_schedules[t].loc[p, d] = f"{s}{p_text}\n({c})"
                        teacher_timetable[(d, p)].append(t)
                        if t in teacher_daily_count:
                            teacher_daily_count[t][d] += 1

                    # 第一階段：排連堂
                    for lp in paired_doubles:
                        c, t, s, attr = lp["class"], lp["teacher"], lp["subject"], lp["attr"]
                        placed = False
                        for d in days:
                            for p1, p2 in valid_pairs:
                                if can_place(c, t, s, d, p1, attr, is_part_of_double=True, strict_level=1, ignore_domain=False) and \
                                   can_place(c, t, s, d, p2, attr, is_part_of_double=True, strict_level=1, ignore_domain=False):
                                    book_slot(c, t, s, d, p1, "", attr)
                                    book_slot(c, t, s, d, p2, "連", attr)
                                    placed = True
                                    break
                            if placed: break
                        if not placed:
                            all_singles.append({"class": c, "teacher": t, "subject": s, "attr": attr})
                            all_singles.append({"class": c, "teacher": t, "subject": s, "attr": attr})

                    # 理想單堂
                    for lp in all_singles:
                        c, t, s, attr = lp["class"], lp["teacher"], lp["subject"], lp["attr"]
                        placed = False
                        sorted_days = sorted(days, key=lambda day: sum(1 for l in schedules[c][day].values if s in str(l)))
                        for d in sorted_days:
                            for p in periods:
                                if can_place(c, t, s, d, p, attr, is_part_of_double=False, strict_level=1, ignore_domain=False):
                                    book_slot(c, t, s, d, p, "", attr)
                                    placed = True
                                    break
                            if placed: break
                        if not placed: unplaced_lessons.append(lp)

                    # 第二階段
                    stage2_unplaced = []
                    for lp in unplaced_lessons:
                        c, t, s, attr = lp["class"], lp["teacher"], lp["subject"], lp["attr"]
                        placed = False
                        sorted_days = sorted(days, key=lambda day: sum(1 for l in schedules[c][day].values if s in str(l)))
                        for d in sorted_days:
                            for p in periods:
                                if can_place(c, t, s, d, p, attr, is_part_of_double=False, strict_level=2, ignore_domain=False):
                                    book_slot(c, t, s, d, p, "", attr)
                                    placed = True
                                    break
                            if placed: break
                        if not placed: stage2_unplaced.append(lp)

                    # 第三階段
                    stage3_unplaced = []
                    for lp in stage2_unplaced:
                        c, t, s, attr = lp["class"], lp["teacher"], lp["subject"], lp["attr"]
                        placed = False
                        sorted_days = sorted(days, key=lambda day: sum(1 for l in schedules[c][day].values if s in str(l)))
                        for d in sorted_days:
                            for p in periods:
                                if can_place(c, t, s, d, p, attr, is_part_of_double=False, strict_level=2, ignore_domain=True):
                                    book_slot(c, t, s, d, p, "", attr)
                                    placed = True
                                    break
                            if placed: break
                        if not placed: stage3_unplaced.append(lp)

                    # 第四階段
                    final_unplaced = []
                    for lp in stage3_unplaced:
                        c, t, s, attr = lp["class"], lp["teacher"], lp["subject"], lp["attr"]
                        placed = False
                        for d in days:
                            for p in periods:
                                if can_place(c, t, s, d, p, attr, is_part_of_double=False, strict_level=4, ignore_domain=True):
                                    book_slot(c, t, s, d, p, "\n[調整]", attr)
                                    placed = True
                                    break
                            if placed: break
                        if not placed: final_unplaced.append(lp)

                    # 💥💥💥 終極驗證閘門 💥💥
                    if len(final_unplaced) == 0:
                        success_fully_placed = True
                        
                        # 正課全數就位且完全無衝突後，執行「全校班級每日滿堂大體檢」
                        for c in class_list:
                            for d in days:
                                for p in periods:
                                    if attr_schedules[c].loc[p, d] == "":
                                        schedules[c].loc[p, d] = "【自習/班務】"
                                        attr_schedules[c].loc[p, d] = "自習"
                        
                        st.session_state.total_input_lessons = total_input_lessons
                        st.session_state.placed_count = total_input_lessons
                        st.session_state.final_unplaced = []
                        st.session_state.final_schedules = schedules
                        st.session_state.final_teacher_schedules = teacher_schedules
                        break

                status_text.empty()

                if success_fully_placed:
                    st.success(f"🏆 【成功解鎖完美課表】系統在第 {attempt} 次全校迭代重排中，成功滿足「班級同科不超2節」與「老師一天最多5節」的最高行政要求！")
                else:
                    st.error(f"❌ 系統隨機重排了 {max_attempts} 次，在【老師單日上限5節】的全新鋼鐵限制下，正課仍有 {len(final_unplaced)} 節課因時段卡死無法排入。這在數學上代表有些老師的總課堂數（例如一週24節課），除以5天後必然會天天超標或卡死。請放寬某些特殊不排課限制或調整兼代課節數！")
                    st.session_state.total_input_lessons = total_input_lessons
                    st.session_state.placed_count = total_input_lessons - len(final_unplaced)
                    st.session_state.final_unplaced = final_unplaced
                    
            except Exception as e:
                st.error("🚨 排課驗證核心發生異常錯誤！")
                st.code(traceback.format_exc())

        # 唯有 100% 成功才放行下載與查閱
        if 'final_schedules' in st.session_state:
            if len(st.session_state.final_unplaced) > 0:
                st.warning("⚠️ 排課結果未達 100% 完美，下載功能已依行政命令進行扣留。")
                with st.expander("🔍 檢視是哪些正課在重排中因老師單日不超5節限制而卡死？"):
                    st.write(pd.DataFrame(st.session_state.final_unplaced))
            else:
                st.balloons()
                st.markdown("### 📊 100% 行政指標對帳看板")
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                with col_m1: st.metric(label="Excel 學科課節總數", value=f"{st.session_state.total_input_lessons} 節")
                with col_m2: st.metric(label="全校學科排課率", value="100.0 % 🔥")
                with col_m3: st.metric(label="班級單日同科限制", value="符合 (<= 2節) 🛡️")
                with col_m4: st.metric(label="老師單日全校課量", value="符合 (<= 5節) 👨‍🏫")

                st.markdown("### 📅 網頁線上查閱")
                view_mode = st.radio("請選擇查閱模式", ["看班級課表", "看老師個人課表"])
                if view_mode == "看班級課表":
                    view_c = st.selectbox("選擇班級", class_list)
                    st.dataframe(st.session_state.final_schedules[view_c], use_container_width=True)
                else:
                    view_t = st.selectbox("選擇老師", teacher_list)
                    st.dataframe(st.session_state.final_teacher_schedules[view_t], use_container_width=True)
                
                st.markdown("---")
                
                def convert_excel():
                    output_buffer = io.BytesIO()
                    with pd.ExcelWriter(output_buffer) as writer:
                        for c_name, c_table in st.session_state.final_
