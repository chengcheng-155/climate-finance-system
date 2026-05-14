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
# 1. 读取特色产业集群附件
# ==========================================
@st.cache_data
def load_excel_data():
    data_path = "dataapp/气候投融资项目评估指南附件.xlsx"
    if not os.path.exists(data_path):
        data_path = "气候投融资项目评估指南附件.xlsx"
    clusters = []
    try:
        xls = pd.ExcelFile(data_path)
        if '特色产业集群名单' in xls.sheet_names:
            df_clusters = pd.read_excel(xls, sheet_name='特色产业集群名单')
            raw_clusters = df_clusters['产业集群名称'].dropna().astype(str).str.strip().unique().tolist()
            clusters = [c for c in raw_clusters if c]
    except:
        clusters = ['新能源汽车产业集群']
    return ['否'] + clusters


feature_options = load_excel_data()

# ==========================================
# 2. 前端界面：第一阶段 - 基础与政策信息
# ==========================================
st.title("🏢 气候投融资项目 - 企业入库申报")
st.markdown("---")

st.subheader("第一步：基础与政策信息")
project_name = st.text_input("项目全称", placeholder="请输入项目全称")

green_channel = st.selectbox("绿色通道审查标准",
                             ["否",
                              "典型负碳项目",
                              "具有国家级/省部级政府认定支持的项目",
                              "可进行碳交易的项目",
                              "与地方特色产业相融合的低碳项目",
                              "赋能支撑类项目"])

# ==========================================
# 3. 分支逻辑处理
# ==========================================

if green_channel != "否":
    # --- 分支 A：符合绿色通道 ---
    st.markdown("---")
    st.success(f"🌟 **识别到项目符合绿色通道条件：【{green_channel}】**")
    st.info("根据《指南》规定，符合绿色通道标准的项目直接初评为 **深绿级**。您无需填写后续指标，可直接提交。")

    if st.button("🚀 确认为绿色通道并直接提交", use_container_width=True):
        if not project_name:
            st.warning("⚠️ 请填写项目名称！")
        else:
            with st.spinner('正在同步至云端数据库...'):
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    existing_data = conn.read(spreadsheet=SHEET_URL, usecols=list(range(11)), ttl=0)
                    new_row = pd.DataFrame([{
                        '项目ID': str(uuid.uuid4())[:8],
                        '申报日期': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        '项目名称': project_name,
                        '所属行业': "不适用",
                        '项目大类': "绿色通道直通类",
                        '绿色通道': green_channel,
                        '是否特色产业': "否",
                        '实际碳排放强度': np.nan,
                        '气候效益综合分': 100.0,  # 绿色通道默认满分入库
                        '初评等级(绝对)': "深绿级",
                        '一票否决(环保违规)': False
                    }])
                    updated_db = pd.concat([existing_data, new_row], ignore_index=True)
                    conn.update(spreadsheet=SHEET_URL, data=updated_db)
                    st.success(f"✅ **项目【{project_name}】已作为深绿级项目成功入库！**")
                    st.balloons()
                except Exception as e:
                    st.error(f"⚠️ 云端同步失败: {e}")

else:
    # --- 分支 B：不符合绿色通道，进入第二阶段 ---
    st.markdown("---")
    st.subheader("第二步：详细指标评估")
    st.info("您的项目暂不符合绿色通道标准，请填写以下指标，系统将根据量化细则进行综合评分。")

    col1, col2 = st.columns([1.1, 1])

    with col1:
        feature_industry = st.selectbox("1. 产业协同：特色产业集群 (1.05倍加权)", feature_options)

        # 动态展示评估细则面板
        st.markdown("#### 📌 指南定量评估标准参考")
        category_ref = st.radio("选择参考标准：", ["分布式发电", "集中式发电", "其他减缓类"], horizontal=True)

        if category_ref == "分布式发电":
            th_deep, th_mid = 3.0, 1.0
        elif category_ref == "集中式发电":
            th_deep, th_mid = 10.0, 5.0
        else:
            th_deep, th_mid = 0.5, 0.1

        st.success(f"""
        **{category_ref}类标准：**
        - 🟢 **深绿级**：减排量 ≥ {th_deep}万吨 | 下降率 ≥ 4%
        - 🟡 **中绿级**：减排量 ≥ {th_mid}万吨 | 下降率 ≥ 3%
        """)

    with col2:
        category = st.selectbox("2. 减排量项目大类 (正式选择)", ["分布式发电", "集中式发电", "其他减缓类"])
        val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, value=0.0, format="%.4f")
        val_decrease = st.number_input("指标 2：强度下降幅度 (%)", min_value=0.0, value=0.0, format="%.4f")

    # 提交逻辑
    if st.button("🚀 进行量化评估并提交", use_container_width=True):
        if not project_name:
            st.warning("⚠️ 请填写项目名称！")
        elif val_reduction == 0 and val_decrease == 0:
            st.warning("⚠️ 请至少填写一项非零的评估指标！")
        else:
            with st.spinner('计算评分中...'):
                weight = 1.05 if feature_industry != "否" else 1.0
                c_scores = []

                if val_reduction > 0:
                    th_base = 3 if category == "分布式发电" else 10 if category == "集中式发电" else 0.5
                    c_scores.append((val_reduction / th_base) * 100)
                if val_decrease > 0:
                    c_scores.append((val_decrease / 4.0) * 100)

                final_score = round(max(c_scores) * weight, 2)
                final_level = "深绿级" if final_score >= 100 else "中绿级" if final_score >= 60 else "浅绿级"

                # 同步云端
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    existing_data = conn.read(spreadsheet=SHEET_URL, usecols=list(range(11)), ttl=0)
                    new_row = pd.DataFrame([{
                        '项目ID': str(uuid.uuid4())[:8],
                        '申报日期': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        '项目名称': project_name,
                        '所属行业': "不适用",
                        '项目大类': category,
                        '绿色通道': "否",
                        '是否特色产业': feature_industry,
                        '实际碳排放强度': np.nan,
                        '气候效益综合分': final_score,
                        '初评等级(绝对)': final_level,
                        '一票否决(环保违规)': False
                    }])
                    updated_db = pd.concat([existing_data, new_row], ignore_index=True)
                    conn.update(spreadsheet=SHEET_URL, data=updated_db)

                    st.success(f"### 评估完成！初评等级：{final_level}")
                    st.info(f"综合得分：{final_score} 分")
                    st.balloons()
                except Exception as e:
                    st.error(f"⚠️ 云端同步失败: {e}")