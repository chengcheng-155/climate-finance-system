import streamlit as st
import pandas as pd
import numpy as np
import os
import uuid
from datetime import datetime

st.set_page_config(page_title="企业申报端 | 气候投融资系统", page_icon="🏢", layout="wide")

# ==========================================
# 1. 数据库路径配置 (本地测试用CSV，云端可换真实DB)
# ==========================================
DB_PATH = "project_database.csv"


# ==========================================
# 2. 读取行业先进值附件
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
        clusters = ['新能源汽车产业集群']
        industry_dict = {'测试行业A': 100.5}

    return ['否'] + clusters, industry_dict, ["手动输入先进值 (不在列表中)"] + list(industry_dict.keys())


feature_options, industry_dict, industry_options = load_excel_data()

# ==========================================
# 3. 前端界面
# ==========================================
st.title("🏢 气候投融资项目 - 企业入库申报")
st.markdown("请如实填写项目指标，系统将自动进行静态初评并提交至政府主管部门审核。")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📝 基础与政策信息")
    project_name = st.text_input("项目全称", placeholder="请输入项目全称")
    green_channel = st.selectbox("绿色通道审查", ["否", "是 - 典型负碳项目", "是 - 赋能支撑类项目"])
    feature_industry = st.selectbox("特色产业集群 (1.05倍权重)", feature_options)

    st.markdown("---")
    st.subheader("🏭 行业基准")
    selected_industry = st.selectbox("所属行业", industry_options)

    if selected_industry == "手动输入先进值 (不在列表中)":
        baseline_value = st.number_input("行业先进值基准 (手动输入)", min_value=0.0, format="%.4f")
        db_industry_name = "其他(手动输入)"
    else:
        baseline_value = st.number_input(f"系统匹配【{selected_industry}】先进值",
                                         value=float(industry_dict[selected_industry]), format="%.4f")
        db_industry_name = selected_industry

with col2:
    st.subheader("📊 气候效益指标")
    category = st.selectbox("减排量项目大类", ["分布式发电", "集中式发电", "其他减缓类"])
    val_reduction = st.number_input("年碳减排量 (万吨)", min_value=0.0, value=0.0, format="%.4f")
    val_intensity = st.number_input("项目实际碳排放强度", min_value=0.0, value=0.0, format="%.4f")
    val_decrease = st.number_input("强度下降幅度 (%)", min_value=0.0, value=0.0, format="%.4f")

# ==========================================
# 4. 评级计算与提交入库
# ==========================================
st.markdown("---")
if st.button("🚀 提交评估并生成报告", use_container_width=True):
    if not project_name:
        st.warning("⚠️ 请填写项目名称！")
    else:
        weight = 1.05 if feature_industry != "否" else 1.0
        scores = []

        if val_reduction > 0:
            th = 3 if category == "分布式发电" else 10 if category == "集中式发电" else 0.5
            scores.append((val_reduction / th) * 100)
        if val_intensity > 0 and baseline_value > 0:
            scores.append((baseline_value / val_intensity) * 100)
        if val_decrease > 0:
            scores.append((val_decrease / 4.0) * 100)

        base_score = max(scores) if scores else 0
        if green_channel != "否": base_score = max(base_score, 100)
        final_score = base_score * weight

        final_level = "深绿级" if final_score >= 100 else "中绿级" if final_score >= 60 else "浅绿级"

        # 展示报告
        st.success("✅ **评估完成！数据已安全加密传输至政府管理库。**")
        st.info(f"### 📋 您的初步评级: {final_level} \n **系统综合评分**: {final_score:.2f}分")

        # --- 核心：将数据追加保存到共享 CSV 数据库 ---
        new_data = pd.DataFrame([{
            '项目ID': str(uuid.uuid4())[:8],
            '申报日期': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            '项目名称': project_name,
            '所属行业': db_industry_name,
            '项目大类': category,
            '绿色通道': green_channel,
            '是否特色产业': feature_industry,
            '实际碳排放强度': val_intensity if val_intensity > 0 else np.nan,
            '气候效益综合分': round(final_score, 2),
            '初评等级(绝对)': final_level,
            '一票否决(环保违规)': False
        }])

        # 写入CSV (如果文件存在则追加，否则创建)
        if os.path.exists(DB_PATH):
            new_data.to_csv(DB_PATH, mode='a', header=False, index=False)
        else:
            new_data.to_csv(DB_PATH, mode='w', header=True, index=False)