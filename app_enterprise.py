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
# 1. 基础数据读取
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


# ------------------------------------------
# 核心：云端数据库写入函数（优化版）
# ------------------------------------------
def save_to_gsheets(new_row_df):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # ttl=0 极其重要，确保每次都读取最新表内容再追加，防止数据覆盖
        existing_data = conn.read(spreadsheet=SHEET_URL, ttl=0)

        # 自动处理空表情况
        if existing_data is None or existing_data.empty:
            updated_db = new_row_df
        else:
            updated_db = pd.concat([existing_data, new_row_df], ignore_index=True)

        conn.update(spreadsheet=SHEET_URL, data=updated_db)
        return True, ""
    except Exception as e:
        return False, str(e)


# ==========================================
# 2. 前端界面布局
# ==========================================
st.title("🏢 气候投融资项目 - 企业入库申报")
st.markdown("填写项目信息，系统将基于《气候投融资项目库分级评估指南》进行初评。")
st.markdown("---")

st.subheader("📝 基础与政策信息")
project_name = st.text_input("项目全称", placeholder="请输入项目全称")

green_channel = st.selectbox("绿色通道审查标准",
                             ["请选择...",
                              "否",
                              "典型负碳项目",
                              "具有国家级/省部级政府认定支持的项目",
                              "可进行碳交易的项目",
                              "与地方特色产业相融合的低碳项目",
                              "赋能支撑类项目"])

# ---------------------------------------------------------
# 分支判断
# ---------------------------------------------------------

if green_channel == "请选择...":
    st.info("👆 请先输入项目名称，并选择是否符合绿色通道审查标准。")

elif green_channel != "否":
    # --- 情境 A：符合绿色通道 ---
    st.success(f"🎉 **该项目符合【{green_channel}】标准，触发绿色通道，直接评定为深绿级。**")

    st.markdown("---")
    if st.button("🚀 提交深绿入库申请", use_container_width=True):
        if not project_name:
            st.warning("⚠️ 请填写项目名称！")
        else:
            with st.spinner('正在同步至云端数据库...'):
                new_row = pd.DataFrame([{
                    '项目ID': str(uuid.uuid4())[:8],
                    '申报日期': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    '项目名称': project_name,
                    '所属行业': "不适用",
                    '项目大类': "绿色通道直通",
                    '绿色通道': green_channel,
                    '是否特色产业': "不适用",
                    '实际碳排放强度': np.nan,
                    '气候效益综合分': 100.0,
                    '初评等级(绝对)': "深绿级",
                    '一票否决(环保违规)': False
                }])
                success, err = save_to_gsheets(new_row)
                if success:
                    st.success("✅ **申报成功！数据已实时存入政府管理库。**")
                    st.balloons()
                else:
                    st.error(f"❌ 同步失败：{err}")

else:
    # --- 情境 B：不符合绿色通道 (选了“否”) ---
    st.markdown("---")
    st.subheader("📍 进阶评估信息填写")

    col1, col2 = st.columns([1.1, 1])

    with col1:
        st.markdown("##### 🏭 产业协同")
        feature_industry = st.selectbox("特色产业集群 (享 1.05倍 加权)", feature_options)

        st.markdown("<br>", unsafe_allow_html=True)
        # 参考指南展示
        cat_guide = st.selectbox("减排量项目大类 (参考细则)", ["分布式发电", "集中式发电", "其他减缓类"])
        if cat_guide == "分布式发电":
            th_deep, th_mid = 3.0, 1.0
        elif cat_guide == "集中式发电":
            th_deep, th_mid = 10.0, 5.0
        else:
            th_deep, th_mid = 0.5, 0.1

        st.success(f"""
        📌 **《指南》定量评估参考 ({cat_guide})**:
        - 🟢 **深绿级**：年减排量 ≥ **{th_deep}** 万吨 或 下降幅度 ≥ **4%**
        - 🟡 **中绿级**：减排量 ≥ **{th_mid}** 万吨 或 下降幅度 ≥ **3%**
        """)

    with col2:
        st.markdown("##### 📊 核心指标录入")
        val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, format="%.4f")
        val_decrease = st.number_input("指标 2：强度下降幅度 (%)", min_value=0.0, format="%.4f")
        st.caption("提示：系统将自动提取折算分最高的一项作为定级依据。")

    # 提交评估按钮放置在指标填写区下方
    st.markdown("---")
    if st.button("🚀 计算评分并提交入库", use_container_width=True):
        if not project_name:
            st.warning("⚠️ 请输入项目名称！")
        elif val_reduction == 0 and val_decrease == 0:
            st.warning("⚠️ 请至少填写一项量化指标数据！")
        else:
            with st.spinner('正在计算并提交...'):
                # 计算分数
                weight = 1.05 if feature_industry != "否" else 1.0
                scores = []
                if val_reduction > 0:
                    th_base = 3 if cat_guide == "分布式发电" else 10 if cat_guide == "集中式发电" else 0.5
                    scores.append((val_reduction / th_base) * 100)
                if val_decrease > 0:
                    scores.append((val_decrease / 4.0) * 100)

                final_score = round(max(scores) * weight, 2) if scores else 0
                final_level = "深绿级" if final_score >= 100 else "中绿级" if final_score >= 60 else "浅绿级"

                # 结果展示
                st.info(f"📊 **初评报告**：得分 **{final_score}** | 评级 **{final_level}**")

                # 同步云端
                new_row = pd.DataFrame([{
                    '项目ID': str(uuid.uuid4())[:8],
                    '申报日期': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    '项目名称': project_name,
                    '所属行业': "不适用",
                    '项目大类': cat_guide,
                    '绿色通道': "否",
                    '是否特色产业': feature_industry,
                    '实际碳排放强度': np.nan,
                    '气候效益综合分': final_score,
                    '初评等级(绝对)': final_level,
                    '一票否决(环保违规)': False
                }])

                success, err = save_to_gsheets(new_row)
                if success:
                    st.success("✅ 数据已入库！")
                    st.balloons()
                else:
                    st.error(f"❌ 同步失败：{err}")