import streamlit as st
import pandas as pd
import io
import random
import traceback

st.set_page_config(page_title="學校全自動排課系統 年級限制版", layout="centered")
st.title("📱 學校自動排課系統 (支援 Excel 年級集體限制)")

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
class_list = []
teacher_list = []

if not st.session_state.teachers_data.empty:
    existing_subjects = sorted(list(set(st.session_state.teachers_data["科目"].dropna().astype(str))))
    class_list = sorted(list(set(st.session_state.teachers_data["任教班級"].dropna().astype(str))))
    teacher_list = sorted(list(set(st.session_state.teachers_data["老師姓名"].dropna().astype(str))))
    if "所屬領域" in st.session_state.teachers_data.columns:
        existing_domains = sorted(list(set(st.session_state.teachers_data["所屬領域"].dropna().astype(str))))
    else:
        existing_domains = existing_subjects

# 側邊欄設定
st.sidebar.markdown("---")
st.sidebar.header("🚫 行政安全限制摘要")
st.sidebar.write("🛡️ 班級端：同班級單日同科目 <= 2節")
st.sidebar.write("👨‍🏫 老師端：同老師單日全校總課量 <= 5節")
st.sidebar.write("💡 特色：**Excel 對象名稱可填「七年級」或「7年級」集體禁排**")

max_one_per_day_subjects = []
for sub in existing_subjects:
    is_default = sub in ["數學", "英文", "國文"]
    if st.sidebar.checkbox(f"🛑 【{sub}】優先一天最多1節", value=is_default):
        max_one_per_day_subjects.append(sub)

# 操作分頁
main_tabs = st.tabs(["📥 1. 匯入開課資料", "🚫 2. 各項排課限制設定", "🚀 3. 智慧排課與匯出"])

# --- 頁面 1：匯入開課資料 ---
with main_tabs[0]:
    st.subheader("📁 上傳全校排課資料")
    uploaded_file = st.file_uploader("O 選擇【開課明細】Excel 檔案", type=["xlsx"], key="main_file")
    if uploaded_file is not None:
        st.session_state.teachers_data = pd.read_excel(uploaded_file)
        if "所屬領域" not in st.session_state.teachers_data.columns:
            st.session_state.teachers_data["所屬領域"] = st.session_state.teachers_data["科目"]
        st.success("開課資料載入成功！請點選「2. 各項排課限制設定」進行下一步。")
    
    if not st.session_state.teachers_data.empty:
        st.markdown("**目前資料庫概況：**")
        st.dataframe(st.session_state.teachers_data, use_container_width=True)

# --- 頁面 2：排課限制設定 ---
with main_tabs[1]:
    st.subheader("📥 2-1. 快速匯入限制條件 Excel")
    st.markdown("💡 *您可以直接上傳排課限制表。對象名稱可填寫特定老師、班級，或是「七年級/八年級/九年級」等整學年集體限制。*")
    
    example_df = pd.DataFrame([
        {"對象分類": "個人/班級", "對象名稱": "七年級", "星期": "週五", "節次": "第5節", "限制原因": "全七年級社團課"},
        {"對象分類": "個人/班級", "對象名稱": "八年級", "星期": "週五", "節次": "第6節", "限制原因": "全八年級聯課活動"},
        {"對象分類": "個人/班級", "對象名稱": "陳大文", "星期": "週二", "節次": "第3節", "限制原因": "老師固定請假"},
        {"對象分類": "領域研習", "對象名稱": "數學", "星期": "週三", "節次": "第5節", "限制原因": "領域會議"}
    ])
    towrite = io.BytesIO()
    example_df.to_excel(towrite, index=False, sheet_name="排課限制範例")
    towrite.seek(0)
    
    st.download_button(
        label="📥 下載「含年級限制功能之 Excel 範例範本」",
        data=towrite.getvalue(),
        file_name="智慧排課限制填寫範本.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    uploaded_rules_file = st.file_uploader("📤 上傳您的【排課限制】Excel 檔案", type=["xlsx"], key="rules_file")
    if uploaded_rules_file is not None:
        try:
            rules_df = pd.read_excel(uploaded_rules_file)
            st.session_state.blocked_times = {}
            st.session_state.domain_blocked_times = {}
            
            success_count = 0
            for _, row in rules_df.iterrows():
                category = str(row.get("對象分類", "")).strip()
                name = str(row.get("對象名稱", "")).strip()
                day = str(row.get("星期", "")).strip()
                period = str(row.get("節次", "")).strip()
                
                if category and name and day and period:
                    slot_str = f"{day}_{period}"
                    if category == "個人/班級":
                        # 💥 智慧識別：如果名字包含年級字眼，直接對應到該年級的所有班級
                        target_classes = []
                        if "七" in name or "7" in name:
                            target_classes = [c for c in class_list if c.startswith("7") or c.startswith("七")]
                        elif "八" in name or "8" in name:
                            target_classes = [c for c in class_list if c.startswith("8") or c.startswith("八")]
                        elif "九" in name or "9" in name:
                            target_classes = [c for c in class_list if c.startswith("9") or c.startswith("九")]
                        
                        # 如果是集體年級，就把該年級每個班級都加進禁排清單
                        if target_classes:
                            for cls in target_classes:
                                if cls not in st.session_state.blocked_times: st.session_state.blocked_times[cls] = []
                                if slot_str not in st.session_state.blocked_times[cls]: st.session_state.blocked_times[cls].append(slot_str)
                            success_count += 1
                        else:
                            # 一般單一老師或單一班級
                            if name not in st.session_state.blocked_times: st.session_state.blocked_times[name] = []
                            if slot_str not in st.session_state.blocked_times[name]: st.session_state.blocked_times[name].append(slot_str)
                            success_count += 1
                            
                    elif category == "領域研習":
                        if name not in st.session_state.domain_blocked_times: st.session_state.domain_blocked_times[name] = []
                        if slot_str not in st.session_state.domain_blocked_times[name]: st.session_state.domain_blocked_times[name].append(slot_str)
                        success_count += 1
            st.success(f"🎉 限制條件匯入完成！成功解析並擴展載入了 {success_count} 筆限制規則！")
        except Exception as ex:
            st.error(f"限制檔案解析失敗，錯誤訊息: {ex}")

    st.markdown("---")
    st.subheader("🔍 2-2. 檢視與微調目前已生效限制")
    col_show1, col_show2 = st.columns(2)
    with col_show1:
        st.write("👥 **目前個人/班級不排課清單 (已自動展開至年級各班)：**")
        if st.session_state.blocked_times: st.json(st.session_state.blocked_times)
        else: st.info("暫無個人或班級限制")
            
    with col_show2:
        st.write("🏢 **目前領域共同研習不排課清單：**")
        if st.session_state.domain_blocked_times: st.json(st.session_state.domain_blocked_times)
        else: st.info("暫無領域限制")

    st.markdown("---")
    st.subheader("📌 2-3. 依年級設定固定課程 (如網頁介面手動輔助設定)")
    
    col_f0, col_f1, col_f2, col_f3 = st.columns(4)
    with col_f0: fixed_grade = st.text_input("年級識別字", placeholder="如：7 或 八")
    with col_f1: fixed_day = st.selectbox("選擇星期", days, key="f_day")
    with col_f2: fixed_period = st.selectbox("選擇節次", periods, key="f_per")
    with col_f3: fixed_name = st.text_input("課程名稱", placeholder="例如：社團課")
    
    if st.button("➕ 新增/更新該年級固定課程", use_container_width=True):
        if fixed_grade and fixed_name:
            if fixed_grade not in st.session_state.fixed_lessons_by_grade: st.session_state.fixed_lessons_by_grade[fixed_grade] = {}
            st.session_state.fixed_lessons_by_grade[fixed_grade][f"{fixed_day}_{fixed_period}"] = fixed_name
            st.toast(f"已設定【{fixed_grade}】{fixed_day}{fixed_period} 為【{fixed_name}】")
            
    if st.session_state.fixed_lessons_by_grade:
        for g, slots in list(st.session_state.fixed_lessons_by_grade.items()):
            for k, v in list(slots.items()):
                if st.button(f"🗑️ 刪除【{g}】{k.split('_')[0]}{k.split('_')[1]}：{v}", key=f"del_{g}_{k}"):
                    del st.session_state.fixed_lessons_by_grade[g][k]
                    if not st.session_state.fixed_lessons_by_grade[g]: del st.session_state.fixed_lessons_by_grade[g]
                    st.rerun()

# --- 頁面 3：智慧排課與雙向匯出 ---
with main_tabs[2]:
    st.subheader("⚡ 執行自動排課")
    if st.session_state.teachers_data.empty:
        st.warning("請先完成資料匯入！")
    else:
        if st.button("🔥 啟動高級階梯權重平衡排課引擎", type="primary", use_container_width=True):
            try:
                max_attempts = 200  
                attempt = 0
                success_fully_placed = False
                
                status_text = st.empty()
                
                while attempt < max_attempts:
                    attempt += 1
                    status_text.markdown(f"⏳ 正在進行第 **{attempt}** 次結構化分流排課...")
                    
                    schedules = {c: pd.DataFrame("", index=periods, columns=days) for c in class_list}
                    attr_schedules = {c: pd.DataFrame("", index=periods, columns=days) for c in class_list}
                    teacher_timetable = {(d, p): [] for d in days for p in periods}
                    teacher_schedules = {t: pd.DataFrame("", index=periods, columns=days) for t in teacher_list}
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

                    for c in class_list:
                        for d in days:
                            for p in periods:
                                fixed_name = get_fixed_lesson_for_class(c, d, p)
                                if fixed_name:
                                    schedules[c].loc[p, d] = f"【{fixed_name}】"
                                    attr_schedules[c].loc[p, d] = "固定"
                    
                    total_input_lessons = 0
                    all_flat_lessons = []
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
                        
                        for _ in range(hours):
                            all_flat_lessons.append({"class": c, "teacher": t, "subject": s, "attr": attr, "is_double": is_double})

                    tier1_doubles = [l for l in all_flat_lessons if l["is_double"]]
                    tier2_main_singles = [l for l in all_flat_lessons if not l["is_double"] and l["attr"] == "考科"]
                    tier3_art_singles = [l for l in all_flat_lessons if not l["is_double"] and l["attr"] == "藝能科"]

                    random.shuffle(tier1_doubles)
                    random.shuffle(tier2_main_singles)
                    random.shuffle(tier3_art_singles)

                    double_groups = {}
                    for lesson in tier1_doubles:
                        key = (lesson["class"], lesson["teacher"], lesson["subject"], lesson["attr"])
                        double_groups[key] = double_groups.get(key, 0) + 1

                    paired_doubles = []
                    leftover_singles_from_double = []
                    for key, count in double_groups.items():
                        pairs = count // 2
                        singles = count % 2
                        for _ in range(pairs):
                            paired_doubles.append({"class": key[0], "teacher": key[1], "subject": key[2], "attr": key[3]})
                        for _ in range(singles):
                            leftover_singles_from_double.append({"class": key[0], "teacher": key[1], "subject": key[2], "attr": key[3]})

                    tier2_main_singles += leftover_singles_from_double
                    random.shuffle(tier2_main_singles)

                    def can_place(c, t, s, d, p, attr, is_part_of_double=False, strict_level=1, ignore_domain=False):
                        slot_str = f"{d}_{p}"
                        if attr_schedules[c].loc[p, d] != "": return False 
                        if t in st.session_state.blocked_times and slot_str in st.session_state.blocked_times[t]: return False
                        if c in st.session_state.blocked_times and slot_str in st.session_state.blocked_times[c]: return False
                        if t in teacher_timetable[(d, p)]: return False 
                        
                        required_slots = 2 if is_part_of_double else 1
                        
                        current_teacher_lessons = teacher_daily_count.get(t, {}).get(d, 0)
                        if (current_teacher_lessons + required_slots) > 5: return False
                            
                        existing_subject_today = sum(1 for lesson in schedules[c][d].values if s in str(lesson))
                        if (existing_subject_today + required_slots) > 2: return False

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

                    def book_slot(c, t, s, d, p, p_text, attr):
                        schedules[c].loc[p, d] = f"{s}{p_text}\n({t})"
                        attr_schedules[c].loc[p, d] = attr
                        teacher_schedules[t].loc[p, d] = f"{s}{p_text}\n({c})"
                        teacher_timetable[(d, p)].append(t)
                        if t in teacher_daily_count:
                            teacher_daily_count[t][d] += 1

                    unplaced_pool = []

                    # 🟦 階段一：連堂課
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
                            unplaced_pool.append({"class": c, "teacher": t, "subject": s, "attr": attr})
                            unplaced_pool.append({"class": c, "teacher": t, "subject": s, "attr": attr})

                    # 🟨 階段二：精華考科單堂
                    for lp in tier2_main_singles:
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
                        if not placed: unplaced_pool.append({"class": c, "teacher": t, "subject": s, "attr": attr})

                    # 🟩 階段三：藝能科
                    for lp in tier3_art_singles:
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
                        if not placed: unplaced_pool.append({"class": c, "teacher": t, "subject": s, "attr": attr})

                    # 🚨 後續寬鬆救援階段
                    stage2_unplaced = []
                    for lp in unplaced_pool:
                        c, t, s, attr = lp["class"], lp["teacher"], lp["subject"], lp["attr"]
                        placed = False
                        for d in days:
                            for p in periods:
                                if can_place(c, t, s, d, p, attr, is_part_of_double=False, strict_level=2, ignore_domain=False):
                                    book_slot(c, t, s, d, p, "", attr)
                                    placed = True
                                    break
                            if placed: break
                        if not placed: stage2_unplaced.append(lp)

                    stage3_unplaced = []
                    for lp in stage2_unplaced:
                        c, t, s, attr = lp["class"], lp["teacher"], lp["subject"], lp["attr"]
                        placed = False
                        for d in days:
                            for p in periods:
                                if can_place(c, t, s, d, p, attr, is_part_of_double=False, strict_level=2, ignore_domain=True):
                                    book_slot(c, t, s, d, p, "", attr)
                                    placed = True
                                    break
                            if placed: break
                        if not placed: stage3_unplaced.append(lp)

                    final_unplaced = []
                    for lp in stage3_unplaced:
                        c, t, s, attr = lp["class"], lp["teacher"], lp["subject"], lp["attr"]
                        placed = False
                        for d in days:
                            for p in periods:
                                if can_place(c, t, s, d, p, attr, is_part_of_double=False, strict_level=4, ignore_domain=True):
                                    book_slot(c, t, s, d, p, "\n[調]", attr)
                                    placed = True
                                    break
                            if placed: break
                        if not placed: final_unplaced.append(lp)

                    if len(final_unplaced) == 0:
                        success_fully_placed = True
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
                    st.success(f"🏆 【策略排課大成功】系統已成功解析年級限制，並在第 {attempt} 次洗牌中解鎖完美課表！")
                else:
                    st.error(f"❌ 迭代 {max_attempts} 次失敗，仍有 {len(final_unplaced)} 節課無法排入。")
                    st.session_state.total_input_lessons = total_input_lessons
                    st.session_state.placed_count = total_input_lessons - len(final_unplaced)
                    st.session_state.final_unplaced = final_unplaced
                    
            except Exception as e:
                st.error("🚨 排課驗證核心發生異常錯誤！")
                st.code(traceback.format_exc())

        if 'final_schedules' in st.session_state:
            if len(st.session_state.final_unplaced) > 0:
                st.warning("⚠️ 排課結果未達 100% 完美，下載功能已進行扣留。")
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
                        for c_name, c_table in st.session_state.final_schedules.items():
                            clean_sheet_name = str(c_name).replace("/", "").replace("\\", "").replace("?", "").replace("*", "")[:20] + "_班"
                            c_table.to_excel(writer, sheet_name=clean_sheet_name)
                        for t_name, t_table in st.session_state.final_teacher_schedules.items():
                            clean_sheet_name = str(t_name).replace("/", "").replace("\\", "").replace("?", "").replace("*", "")[:20] + "_師"
                            t_table.to_excel(writer, sheet_name=clean_sheet_name)
                    output_buffer.seek(0)
                    return output_buffer.getvalue()

                st.download_button(
                    label="📥 匯出全校總課表 (Excel) - 已通過全校雙向護欄驗證",
                    data=convert_excel(), 
                    file_name="全校功課表總匯出結果_分流完美版.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
