import streamlit as st
import pandas as pd
import numpy as np
import os
import uuid
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 0. 页面与状态配置
# ==========================================
st.set_page_config(page_title="企业申报端 | 气候投融资系统", page_icon="🏢", layout="wide")

# ⚠️ 提示：请确保此处替换为您在 Google Sheets 后台生成的真实 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/您的表格ID/edit"


# ==========================================
# 1. 读取行业先进值附件 (自动适配云端/本地路径)
# ==========================================
@st.cache_data
def load_excel_data():
    data_path = "dataapp/气候投融资项目评估指南附件.xlsx"
    if not os.path.exists(data_path):
        data_path = "气候投融资项目评估指南附件.xlsx"

    clusters = []
    industry_dict = {}

    try:
        xls = pd.ExcelFile(data_path)
        if '特色产业集群名单' in xls.sheet_names:
            df_clusters = pd.read_excel(xls, sheet_name='特色产业集群名单')
            raw_clusters = df_clusters['产业集群名称'].dropna().astype(str).str.strip().unique().tolist()
            clusters = [c for c in raw_clusters if c]

        if '行业碳排放强度先进值' in xls.sheet_names:
            df_ind = pd.read_excel(xls, sheet_name='行业碳排放强度先进值', header=2)
            df_ind = df_ind.dropna(subset=[df_ind.columns[1], df_ind.columns[4]])
            for _, row in df_ind.iterrows():
                try:
                    ind_name = str(row.iloc[1]).strip()
                    ind_val = float(str(row.iloc[4]).strip())
                    if ind_name: industry_dict[ind_name] = ind_val
                except:
                    continue
    except:
        st.sidebar.error("⚠️ 读取附件失败，请确保 Excel 文件在仓库中。")
        clusters = ['新能源汽车产业集群']
        industry_dict = {'测试行业A': 100.5}

    return ['否'] + clusters, industry_dict, ["手动输入先进值 (不在列表中)"] + list(industry_dict.keys())


feature_options, industry_dict, industry_options = load_excel_data()

# ==========================================
# 2. 前端界面布局
# ==========================================
st.title("🏢 气候投融资项目 - 企业入库申报")
st.markdown("填写项目信息，系统将基于《气候投融资项目库分级评估指南》进行初评。")
st.markdown("---")

col1, col2 = st.columns([1.1, 1])

with col2:
    st.subheader("📊 核心评估指标填写")
    st.info("💡 **提示**：选填一项或多项指标。系统将自动选取最强优势指标作为定级依据。")
    # 项目大类选择
    category = st.selectbox("1. 减排量项目大类 (必选)", ["分布式发电", "集中式发电", "其他减缓类"])
    val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, value=0.0, format="%.4f")
    val_intensity = st.number_input("指标 2：项目实际碳排放强度 (比值)", min_value=0.0, value=0.0, format="%.4f")
    val_decrease = st.number_input("指标 3：强度下降幅度 (%)", min_value=0.0, value=0.0, format="%.4f")

with col1:
    st.subheader("📝 基础与行业信息")
    project_name = st.text_input("项目全称", placeholder="请输入项目全称")

    # 修改点：更新为用户指定的 5 类绿色通道标准
    green_channel = st.selectbox("绿色通道审查标准",
                                 ["否",
                                  "典型负碳项目",
                                  "具有国家级/省部级政府认定支持的项目",
                                  "可进行碳交易的项目",
                                  "与地方特色产业相融合的低碳项目",
                                  "赋能支撑类项目"])

    feature_industry = st.selectbox("特色产业集群 (1.05倍加权)", feature_options)

    selected_industry = st.selectbox("所属行业", industry_options)
    if selected_industry == "手动输入先进值 (不在列表中)":
        baseline_value = st.number_input("行业先进值基准 (手动输入)", min_value=0.0, format="%.4f")
        db_industry_name = "其他(手动输入)"
    else:
        auto_val = industry_dict.get(selected_industry, 0)
        baseline_value = st.number_input(f"系统匹配【{selected_industry}】先进值", value=float(auto_val), format="%.4f")
        db_industry_name = selected_industry

    # ==========================================
    # 动态展示《指南》三级定量评估细则
    # ==========================================
    st.markdown("---")
    # 计算减排量门槛
    if category == "分布式发电":
        th_deep, th_mid = 3.0, 1.0
    elif category == "集中式发电":
        th_deep, th_mid = 10.0, 5.0
    else:
        th_deep, th_mid = 0.5, 0.1

    st.success(f"""
    📌 **《指南》项目定量评估细则参考 (对应 {category}类)**:

    **1. 碳减排规模效益**:
    - 🟢 **深绿级**：年减排量 ≥ **{th_deep}** 万吨
    - 🟡 **中绿级**：**{th_mid}** 万吨 ≤ 年减排量 < **{th_deep}** 万吨
    - ⚪ **浅绿级**：年减排量 < **{th_mid}** 万吨

    **2. 碳排放强度 (减排技术先进性)**:
    - 🟢 **深绿级**：项目强度 ≤ **{baseline_value:.4f}** (行业先进值)
    - 🟡 **中绿级**：**{baseline_value:.4f}** < 项目强度 ≤ **{baseline_value * 1.25:.4f}** (先进值×1.25)
    - ⚪ **浅绿级**：项目强度 > **{baseline_value * 1.25:.4f}**

    **3. 碳排放强度下降幅度**:
    - 🟢 **深绿级**：下降幅度 ≥ **4%**
    - 🟡 **中绿级**：**3%** ≤ 下降幅度 < **4%**
    - ⚪ **浅绿级**：下降幅度 < **3%**
    """)

# ==========================================
# 3. 计算得分与同步数据
# ==========================================
st.markdown("---")
if st.button("🚀 提交评估并同步至云端", use_container_width=True):
    if not project_name:
        st.warning("⚠️ 请填写项目名称！")
    elif val_reduction == 0 and val_intensity == 0 and val_decrease == 0 and green_channel == "否":
        st.warning("⚠️ 请至少填写一项评估指标或符合绿色通道！")
    else:
        with st.spinner('正在计算评分并连接云端数据库...'):
            weight = 1.05 if feature_industry != "否" else 1.0
            c_scores = []

            if val_reduction > 0:
                th_base = 3 if category == "分布式发电" else 10 if category == "集中式发电" else 0.5
                c_scores.append((val_reduction / th_base) * 100)

            if val_intensity > 0 and baseline_value > 0:
                c_scores.append((baseline_value / val_intensity) * 100)

            if val_decrease > 0:
                c_scores.append((val_decrease / 4.0) * 100)

            base_score = max(c_scores) if c_scores else 0

            # 若符合任意一类绿色通道，直接给予深绿入库分（100分）
            if green_channel != "否":
                base_score = max(base_score, 100)

            final_score = round(base_score * weight, 2)
            final_level = "深绿级" if final_score >= 100 else "中绿级" if final_score >= 60 else "浅绿级"

            st.success("✅ **评估数据已成功同步至政府管理云端数据库。**")
            st.subheader("🏆 最终初评报告")
            st.markdown(f"**项目名称**: {project_name}")
            st.markdown(f"**气候效益综合得分**: `{final_score} 分` (已应用权重加成)")
            if final_level == "深绿级":
                st.success(f"### 综合初评等级：{final_level}")
            elif final_level == "中绿级":
                st.info(f"### 综合初评等级：{final_level}")
            else:
                st.warning(f"### 综合初评等级：{final_level}")

            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                existing_data = conn.read(spreadsheet=SHEET_URL, usecols=list(range(11)), ttl=0)
                new_row = pd.DataFrame([{
                    '项目ID': str(uuid.uuid4())[:8],
                    '申报日期': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    '项目名称': project_name,
                    '所属行业': db_industry_name,
                    '项目大类': category,
                    '绿色通道': green_channel,
                    '是否特色产业': feature_industry,
                    '实际碳排放强度': val_intensity if val_intensity > 0 else np.nan,
                    '气候效益综合分': final_score,
                    '初评等级(绝对)': final_level,
                    '一票否决(环保违规)': False
                }])
                updated_db = pd.concat([existing_data, new_row], ignore_index=True)
                conn.update(spreadsheet=SHEET_URL, data=updated_db)
                st.balloons()
            except Exception as e:
                st.error(f"⚠️ 云端同步失败。错误: {e}")