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
# 1. 数据读取与数据库封装
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


def save_to_database(project_name, category, green_channel, feature_industry, final_score, final_level):
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
        return True, ""
    except Exception as e:
        return False, str(e)


# ==========================================
# 2. 前端界面布局 (动态渐进式)
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
# 情境 A：等待选择
# ---------------------------------------------------------
if green_channel == "请选择...":
    st.info("👆 请先输入项目名称，并选择是否符合绿色通道审查标准。")

else:
    # ---------------------------------------------------------
    # 动态提示词与确认环节
    # ---------------------------------------------------------
    if green_channel != "否":
        st.success(f"🎉 **该项目符合【{green_channel}】标准，已触发绿色通道，保底获得 深绿级（100分）。**")
        radio_text = "❓ 是否继续填写【定量指标】及【特色产业】信息，以争取更高分进行同行业排名？"
    else:
        st.warning("⚠️ **该项目未触发绿色通道，目前初始评分为 0 分。**")
        radio_text = "❓ 是否继续填写【定量指标】及【特色产业】信息，以获取评级？"

    continue_fill = st.radio(radio_text, ["请选择...", "是，继续填写争取最高分", "否，直接生成当前结果并提交"])

    # ---------------------------------------------------------
    # 情境 B：用户选择【否】，直接出结果
    # ---------------------------------------------------------
    if continue_fill == "否，直接生成当前结果并提交":
        final_score = 100.0 if green_channel != "否" else 0.0
        final_level = "深绿级" if final_score >= 100 else "浅绿级"

        st.markdown("---")
        st.subheader("🏆 最终初评报告")
        st.markdown(f"**项目名称**: {project_name}")
        st.markdown(f"**气候效益综合得分**: `{final_score} 分`")
        if final_level == "深绿级":
            st.success(f"### 综合初评等级：{final_level}")
        else:
            st.warning(f"### 综合初评等级：未通过指标考核 / 浅绿级")

        if st.button("🚀 确认提交并同步至云端", use_container_width=True):
            if not project_name:
                st.warning("⚠️ 请填写项目名称！")
            else:
                with st.spinner('正在同步云端数据库...'):
                    c_type = "绿色通道免评" if green_channel != "否" else "未填报定量指标"
                    success, error_msg = save_to_database(project_name, c_type, green_channel, "否", final_score,
                                                          final_level)
                    if success:
                        st.success("✅ **评估数据已成功同步至政府管理云端数据库。**")
                        st.balloons()
                    else:
                        st.error(f"⚠️ 云端同步失败。错误: {error_msg}")

    # ---------------------------------------------------------
    # 情境 C：用户选择【是】，展开进阶表单
    # ---------------------------------------------------------
    elif continue_fill == "是，继续填写争取最高分":
        st.markdown("---")
        st.subheader("📍 进阶评估信息")

        col1, col2 = st.columns([1.1, 1])

        with col2:
            st.markdown("##### 📊 核心评估指标填写")
            st.info("💡 **提示**：选填一项或多项。系统将比对基础分与指标分，自动取 **最高分** 记录。")

            category = st.selectbox("1. 减排量项目大类 (必选)", ["分布式发电", "集中式发电", "其他减缓类"])
            val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, value=0.0, format="%.4f")
            val_decrease = st.number_input("指标 2：强度下降幅度 (%)", min_value=0.0, value=0.0, format="%.4f")

        with col1:
            st.markdown("##### 🏭 产业协同")
            feature_industry = st.selectbox("特色产业集群 (享受 1.05 倍加权)", feature_options)

            # 定量评估细则参考
            st.markdown("<br>", unsafe_allow_html=True)
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

            **2. 碳排放强度下降幅度**:
            - 🟢 **深绿级**：下降幅度 ≥ **4%**
            - 🟡 **中绿级**：**3%** ≤ 下降幅度 < **4%**
            - ⚪ **浅绿级**：下降幅度 < **3%**
            """)

        st.markdown("---")
        if st.button("🚀 提交评估并同步至云端", use_container_width=True):
            if not project_name:
                st.warning("⚠️ 请填写项目名称！")
            elif val_reduction == 0 and val_decrease == 0 and green_channel == "否":
                st.warning("⚠️ 既然选择了继续填写，请至少填报一项定量指标数据！")
            else:
                with st.spinner('正在计算评分并连接云端数据库...'):
                    weight = 1.05 if feature_industry != "否" else 1.0
                    c_scores = []

                    if val_reduction > 0:
                        th_base = 3 if category == "分布式发电" else 10 if category == "集中式发电" else 0.5
                        c_scores.append((val_reduction / th_base) * 100)

                    if val_decrease > 0:
                        c_scores.append((val_decrease / 4.0) * 100)

                    # 提取填报指标计算出的最高分
                    max_indicator_score = max(c_scores) if c_scores else 0

                    # 取最高分记录机制：指标得分 VS 绿色通道保底分(100分)
                    base_score = max_indicator_score
                    if green_channel != "否":
                        base_score = max(max_indicator_score, 100)

                    final_score = round(base_score * weight, 2)
                    final_level = "深绿级" if final_score >= 100 else "中绿级" if final_score >= 60 else "浅绿级"

                    # 展示本次计算结果
                    st.subheader("🏆 最终初评报告")
                    st.markdown(f"**项目名称**: {project_name}")
                    st.markdown(f"**气候效益综合得分**: `{final_score} 分` (已取最高维度分数并应用加权)")

                    if final_level == "深绿级":
                        st.success(f"### 综合初评等级：{final_level}")
                    elif final_level == "中绿级":
                        st.info(f"### 综合初评等级：{final_level}")
                    else:
                        st.warning(f"### 综合初评等级：{final_level}")

                    # 写入数据库
                    success, error_msg = save_to_database(
                        project_name=project_name,
                        category=category,
                        green_channel=green_channel,
                        feature_industry=feature_industry,
                        final_score=final_score,
                        final_level=final_level
                    )

                    if success:
                        st.success("✅ **评估数据已成功同步至政府管理云端数据库。**")
                        st.balloons()
                    else:
                        st.error(f"⚠️ 云端同步失败。错误: {error_msg}")