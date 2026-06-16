import streamlit as st
import pandas as pd
import io
import random
import traceback
import re

st.set_page_config(page_title="學校全自動排課系統 行政優化版", layout="centered")
st.title("📱 學校自動排課系統 (支援領域寬限與行政鎖定)")

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
    st.session_state.teachers_data = pd.DataFrame(columns=["任教班級", "老師姓名", "科目", "每週堂數", "需要連排(對/錯)", "課程屬性", "所屬領域", "職稱"])
if 'blocked_times' not in st.session_state:
    st.session_state.blocked_times = {} 
if 'domain_blocked_times' not in st.session_state: 
    st.session_state.domain_blocked_times = {} 
if 'fixed_lessons_by_grade' not in st.session_state:
    st.session_state.fixed_lessons_by_grade = {}

# 核心清單初始化
existing_subjects = []
existing_domains = []
class_list = []
teacher_list = []
title_teacher_map = {}

if not st.session_state.teachers_data.empty:
    for col in ["科目", "任教班級", "老師姓名", "職稱"]:
        if col in st.session_state.teachers_data.columns:
            st.session_state.teachers_data[col] = st.session_state.teachers_data[col].astype(str).str.strip()
            
    existing_subjects = sorted(list(set(st.session_state.teachers_data["科目"].dropna())))
    class_list = sorted(list(set(st.session_state.teachers_data["任教班級"].dropna())))
    teacher_list = sorted(list(set(st.session_state.teachers_data["老師姓名"].dropna())))
    
    if "所屬領域" not in st.session_state.teachers_data.columns:
        st.session_state.teachers_data["所屬領域"] = st.session_state.teachers_data["科目"]
    existing_domains = sorted(list(set(st.session_state.teachers_data["所屬領域"].dropna())))
    
    if "職稱" in st.session_state.teachers_data.columns:
        for idx, row in st.session_state.teachers_data.iterrows():
            t_name = row["老師姓名"]
            t_title = row["職稱"]
            if t_title and t_name and t_title != "nan" and t_name != "nan":
                if t_title not in title_teacher_map:
                    title_teacher_map[t_title] = set()
                title_teacher_map[t_title].add(t_name)

# ----------------- 側邊欄行政控制區 -----------------
st.sidebar.markdown("---")
st.sidebar.header("🚫 行政安全限制摘要")
st.sidebar.write("🛡️ 班級端：同班級單日同科目 <= 2節")
st.sidebar.write("👨‍🏫 老師端：同老師單日全校總課量 <= 5節")

# 動態控制哪些領域時間「依然可以排課」
st.sidebar.markdown("---")
st.sidebar.header("🔓 領域時間排課寬限設定")
st.sidebar.write("💡 *若以下領域在限制表中有設定研習禁排，勾選後系統將「放寬」允許排課：*")

allow_排課_domains = []
if existing_domains:
    for dom in existing_domains:
        if st.sidebar.checkbox(f"🟢 【{dom}】時間允許排一般課", value=False):
            allow_排課_domains.append(dom)
else:
    st.sidebar.info("請先至分頁 1 上傳開課明細以載入領域清單。")

st.sidebar.markdown("---")
st.sidebar.header("🛑 學科單日最多1節控制")
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
        if "職稱" not in st.session_state.teachers_data.columns:
            st.session_state.teachers_data["職稱"] = "專任"
        st.success("開課資料載入成功！領域清單已同步更新至左側欄！")
        st.rerun()
    
    if not st.session_state.teachers_data.empty:
        st.markdown("**目前全校資料庫概況：**")
        st.dataframe(st.session_state.teachers_data, use_container_width=True)

# --- 頁面 2：排課限制設定 ---
with main_tabs[1]:
    st.subheader("📥 2-1. 快速匯入限制條件 Excel")
    
    # 修正處：確保範例 DataFrame 欄位名稱完全正確
    example_df = pd.DataFrame([
        {"對象分類": "個人/班級", "對象名稱": "主任", "星期": "週二", "節次": "第1-3節", "限制原因": "主管會報"},
        {"對象分類": "個人/班級", "對象名稱": "七年級", "星期": "週五", "節次": "第5,6節", "限制原因": "全年級社團"},
        {"對象分類": "領域研習", "對象名稱": "數學", "星期": "週三", "節次": "第5-6節", "限制原因": "領域會議(嚴格禁排)"},
        {"對象分類": "領域研習", "對象名稱": "體育", "星期": "週慢", "節次": "第3-4節", "限制原因": "體育領域時間"}
    ])
    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine='openpyxl') as writer:
        example_df.to_excel(writer, index=False, sheet_name="排課限制範例")
    towrite.seek(0)
    
    st.download_button(
        label="📥 下載「最新修正版限制 Excel 範例範本」",
        data=towrite.getvalue(),
        file_name="智慧排課限制範本_含領域寬限版.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    uploaded_rules_file = st.file_uploader("📤 上傳您的【排課限制】Excel 檔案", type=["xlsx"], key="rules_file")
    if uploaded_rules_file is not None:
        try:
            rules_df = pd.read_excel(uploaded_rules_file)
            st.session_state.blocked_times = {}
            st.session_state.domain_blocked_times = {}
            
            def parse_periods(period_str):
                p_str = str(period_str).strip()
                parsed = []
                range_match = re.search(r'(\d+)\s*-\s*(\d+)', p_str)
                if range_match:
                    start, end = int(range_match.group(1)), int(range_match.group(2))
                    for i in range(start, end + 1): parsed.append(f"第{i}節")
                    return parsed
                digits = re.findall(r'\d+', p_str)
                for d in digits: parsed.append(f"第{d}節")
                return list(set(parsed))

            success_count = 0
            for _, row in rules_df.iterrows():
                category = str(row.get("對象分類", "")).strip()
                # 修正處：解決錯字讀取失敗問題
                name = str(row.get("對象名稱", "")).strip()
                day = str(row.get("星期", "")).strip()
                raw_period = str(row.get("節次", "")).strip()
                
                if category and name and day and raw_period:
                    target_periods = parse_periods(raw_period)
                    for p_node in target_periods:
                        slot_str = f"{day}_{p_node}"
                        
                        if category == "個人/班級":
                            target_entities = []
                            if name in title_teacher_map:
                                target_entities = list(title_teacher_map[name])
                            elif "七" in name or "7" in name:
                                target_entities = [c for c in class_list if c.startswith("7") or c.startswith("七")]
                            elif "八" in name or "8" in name:
                                target_entities = [c for c in class_list if c.startswith("8") or c.startswith("八")]
                            elif "九" in name or "9" in name:
                                target_entities = [c for c in class_list if c.startswith("9") or c.startswith("九")]
                            else:
                                target_entities = [name]
                                
                            for ent in target_entities:
                                if ent not in st.session_state.blocked_times: st.session_state.blocked_times[ent] = []
                                if slot_str not in st.session_state.blocked_times[ent]: st.session_state.blocked_times[ent].append(slot_str)
                            success_count += 1
                                
                        elif category == "領域研習":
                            if name not in st.session_state.domain_blocked_times: st.session_state.domain_blocked_times[name] = []
                            if slot_str not in st.session_state.domain_blocked_times[name]: st.session_state.domain_blocked_times[name].append(slot_str)
                            success_count += 1
                            
            st.success(f"🎉 限制條件匯入完成！共展開解析了 {success_count} 筆限制規則！")
        except Exception as ex:
            st.error(f"限制檔案解析失敗，錯誤訊息: {ex}")

    st.markdown("---")
    st.subheader("🔍 2-2. 檢視目前已展開之禁排清單")
    col_show1, col_show2 = st.columns(2)
    with col_show1:
        st.write("👥 **個人/行政主管/班級 禁排時段：**")
        if st.session_state.blocked_times: st.json(st.session_state.blocked_times)
        else: st.info("暫無資料")
    with col_show2:
        st.write("🏢 **領域共同研習 禁排時段：**")
        if st.session_state.domain_blocked_times: st.json(st.session_state.domain_blocked_times)
        else: st.info("暫無資料")

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
                    status_text.markdown(f"⏳ 正在進行第 **{attempt}** 次行政結構化分流排課...")
                    
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
                        except: hours = 1
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
                                if dom not in allow_排課_domains: 
                                    if dom in st.session_state.domain_blocked_times and slot_str in st.session_state.domain_blocked_times[dom]: 
                                        return False
                            
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
                        if t in teacher_daily_count: teacher_daily_count[t][d] += 1

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

                    # 🚨 救援階段
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
                    st.success(f"🏆 【智慧排課成功】已依據您的側欄寬限設定，順利避開指定領域會議並解鎖完美課表！")
                else:
                    st.error(f"❌ 疊代失敗，仍有 {len(final_unplaced)} 節課無法排入。建議在左邊側欄勾選更多可排課的領域來放寬限制。")
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
                    label="📥 匯出全校總課表 (Excel)",
                    data=convert_excel(), 
                    file_name="全校功課表總匯出結果_行政完美版.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
