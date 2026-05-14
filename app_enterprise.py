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
# 2. 界面逻辑：第一阶段 - 基础与政策信息
# ==========================================
st.title("🏢 气候投融资项目 - 企业入库申报")
st.markdown("---")

st.subheader("第一步：基础信息与政策审查")
project_name = st.text_input("项目全称", placeholder="请输入项目全称")

green_channel = st.selectbox("绿色通道审查标准",
                             ["否",
                              "典型负碳项目",
                              "具有国家级/省部级政府认定支持的项目",
                              "可进行碳交易的项目",
                              "与地方特色产业相融合的低碳项目",
                              "赋能支撑类项目"])

# ==========================================
# 3. 条件渲染逻辑
# ==========================================

# 初始化提交所需变量（防止报错）
final_score = 0.0
final_level = "浅绿级"
category = "无"
feature_industry = "否"
val_reduction = 0.0
val_decrease = 0.0

if green_channel != "否":
    # ---- 逻辑 A：符合绿色通道，直接判定 ----
    st.success("✨ **符合绿色通道准入条件！**")
    st.info("您的项目属于绿色通道支持范围，无需填写后续指标，系统将直接以 **深绿级** 进行入库申报。")

    final_score = 100.0
    final_level = "深绿级"

    st.markdown("---")
    submit_btn = st.button("🚀 确认为深绿级并提交入库", use_container_width=True)

else:
    # ---- 逻辑 B：不符合绿色通道，跳转到第二界面 ----
    st.markdown("---")
    st.subheader("第二步：核心评估指标填写")
    st.warning("您的项目不属于绿色通道范围，请继续完善以下指标以进行综合分级评估。")

    col1, col2 = st.columns([1, 1])

    with col1:
        feature_industry = st.selectbox("特色产业集群 (1.05倍加权)", feature_options)
        category = st.selectbox("减排量项目大类 (必选)", ["分布式发电", "集中式发电", "其他减缓类"])

        # 动态展示评估细则
        if category == "分布式发电":
            th_deep, th_mid = 3.0, 1.0
        elif category == "集中式发电":
            th_deep, th_mid = 10.0, 5.0
        else:
            th_deep, th_mid = 0.5, 0.1

        st.success(f"""
        📌 **《指南》定量评估细则参考 ({category})**:
        1. **碳减排量**: 深绿≥{th_deep}万吨 | 中绿≥{th_mid}万吨
        2. **强度下降**: 深绿≥4% | 中绿≥3%
        """)

    with col2:
        val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, format="%.4f")
        val_decrease = st.number_input("指标 2：强度下降幅度 (%)", min_value=0.0, format="%.4f")

    st.markdown("---")
    submit_btn = st.button("📊 提交评估并同步至云端", use_container_width=True)

# ==========================================
# 4. 数据处理与云端同步
# ==========================================
if submit_btn:
    if not project_name:
        st.error("⚠️ 请先填写项目名称！")
    elif green_channel == "否" and val_reduction == 0 and val_decrease == 0:
        st.error("⚠️ 请至少填写一项核心评估指标！")
    else:
        with st.spinner('正在同步数据至云端数据库...'):
            # 计算得分（仅针对非绿色通道项目）
            if green_channel == "否":
                weight = 1.05 if feature_industry != "否" else 1.0
                c_scores = []

                if val_reduction > 0:
                    th_base = 3 if category == "分布式发电" else 10 if category == "集中式发电" else 0.5
                    c_scores.append((val_reduction / th_base) * 100)
                if val_decrease > 0:
                    c_scores.append((val_decrease / 4.0) * 100)

                base_score = max(c_scores) if c_scores else 0
                final_score = round(base_score * weight, 2)
                final_level = "深绿级" if final_score >= 100 else "中绿级" if final_score >= 60 else "浅绿级"

            # 展示结果
            st.success("✅ **申报提交成功！**")
            st.subheader("📋 初评结果回执")
            st.write(f"**项目名称**: {project_name}")
            st.write(f"**最终判定等级**: {final_level}")
            st.write(f"**气候效益分**: {final_score}")

            # 写入 Google Sheets
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                existing_data = conn.read(spreadsheet=SHEET_URL, usecols=list(range(11)), ttl=0)
                new_row = pd.DataFrame([{
                    '项目ID': str(uuid.uuid4())[:8],
                    '申报日期': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    '项目名称': project_name,
                    '所属行业': "不适用",
                    '项目大类': category,
                    '绿色通道': green_channel,
                    '是否特色产业': feature_industry,
                    '实际碳排放强度': np.nan,
                    '气候效益综合分': final_score,
                    '初评等级(绝对)': final_level,
                    '一票否决(环保违规)': False
                }])
                updated_db = pd.concat([existing_data, new_row], ignore_index=True)
                conn.update(spreadsheet=SHEET_URL, data=updated_db)
                st.balloons()
            except Exception as e:
                st.error(f"⚠️ 云端同步失败，请检查密钥。错误: {e}")