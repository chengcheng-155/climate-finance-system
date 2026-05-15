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

# ⚠️ 必须修改：请将此处替换为您在 Google Sheets 后台生成的真实 URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1i1wzfAKODzm2BzhCE9T7JMEeOagtdXxVfTr5r3GvniA/edit?gid=0#gid=0"


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
        # 读取现有数据，ttl=0 保证实时性
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
# 2. 前端界面布局
# ==========================================
st.title("🏢 气候投融资项目 - 企业入库申报")
st.markdown("填写项目信息，系统将基于《气候投融资项目库分级评估指南》进行初评。")
st.markdown("---")

# 基础信息模块
st.subheader("📝 基础与政策信息")
project_name = st.text_input("项目全称", placeholder="请输入项目全称")

green_channel = st.selectbox("绿色通道审查标准",
                             ["请选择...", "否", "典型负碳项目", "具有国家级/省部级政府认定支持的项目",
                              "可进行碳交易的项目", "与地方特色产业相融合的低碳项目", "赋能支撑类项目"])

# 变量初始化
show_advanced = False
force_deep_green = False

if green_channel == "请选择...":
    st.info("👆 请先输入项目名称，并选择是否符合绿色通道审查标准。")
    st.stop()

elif green_channel != "否":
    force_deep_green = True
    st.success(f"🎉 **该项目符合【{green_channel}】标准，已具备深绿级（100分）入库资格。**")
    # 绿色通道下的额外询问
    cont_choice = st.radio("❓ 是否需要继续填报其他量化指标（系统将自动记录最高分）？", ["否", "是"], horizontal=True)
    show_advanced = (cont_choice == "是")

else:
    # 选“否”的情况，直接展示
    show_advanced = True
    force_deep_green = False

# ==========================================
# 3. 进阶评估界面（特色产业与定量指标）
# ==========================================
feature_industry = "否"
category = "绿色通道免评" if force_deep_green else "未分类"
val_reduction = 0.0
val_decrease = 0.0

if show_advanced:
    st.markdown("---")
    st.subheader("📍 进阶评估信息")
    col1, col2 = st.columns([1.1, 1])

    with col1:
        st.markdown("##### 🏭 产业协同")
        feature_industry = st.selectbox("特色产业集群 (享受1.05倍加权)", feature_options)

        st.markdown("<br>", unsafe_allow_html=True)
        guide_cat = st.selectbox("减排量项目大类 (用于查看细则参考)", ["分布式发电", "集中式发电", "其他减缓类"])

        # 指南参考保持不变
        if guide_cat == "分布式发电":
            th_deep, th_mid = 3.0, 1.0
        elif guide_cat == "集中式发电":
            th_deep, th_mid = 10.0, 5.0
        else:
            th_deep, th_mid = 0.5, 0.1

        st.success(f"""
        📌 **《指南》定量评估细则参考 ({guide_cat}类)**:
        **1. 碳减排规模效益**:
    - 🟢 **深绿级**：年减排量 ≥ **{th_deep}** 万吨
    - 🟡 **中绿级**：**{th_mid}** 万吨 ≤ 年减排量 < **{th_deep}** 万吨
    - ⚪ **浅绿级**：年减排量 < **{th_mid}** 万吨


    **2. 碳排放强度下降幅度**:
    - 🟢 **深绿级**：下降幅度 ≥ **4%**
    - 🟡 **中绿级**：**3%** ≤ 下降幅度 < **4%**
    - ⚪ **浅绿级**：下降幅度 < **3%**
    """)

    with col2:
        st.markdown("##### 📊 核心评估指标填写")
        st.info("💡 选填指标，系统将自动提取最高分项。")
        category = st.selectbox("1. 提交指标所属的大类", ["分布式发电", "集中式发电", "其他减缓类"],
                                index=["分布式发电", "集中式发电", "其他减缓类"].index(guide_cat))
        val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, format="%.4f")
        val_decrease = st.number_input("指标 2：强度下降幅度 (%)", min_value=0.0, format="%.4f")

# ==========================================
# 4. 统一提交逻辑
# ==========================================
st.markdown("---")
if st.button("🚀 提交评估并同步至云端", use_container_width=True):
    if not project_name:
        st.warning("⚠️ 请填写项目名称！")
    elif not force_deep_green and val_reduction == 0 and val_decrease == 0:
        st.warning("⚠️ 请至少填写一项具体的量化指标！")
    else:
        with st.spinner('正在计算并同步数据...'):
            weight = 1.05 if feature_industry != "否" else 1.0
            scores = []

            # 计算填报指标的分数
            if val_reduction > 0:
                th_base = 3 if category == "分布式发电" else 10 if category == "集中式发电" else 0.5
                scores.append((val_reduction / th_base) * 100)
            if val_decrease > 0:
                scores.append((val_decrease / 4.0) * 100)

            indicator_score = max(scores) if scores else 0

            # 最高分记录机制：对比保底分与指标分
            base_score = indicator_score
            if force_deep_green:
                base_score = max(base_score, 100.0)

            final_score = round(base_score * weight, 2)
            final_level = "深绿级" if final_score >= 100 else "中绿级" if final_score >= 60 else "浅绿级"

            # 写入云端
            success, error_msg = save_to_database(project_name, category, green_channel, feature_industry, final_score,
                                                  final_level)

            if success:
                st.success("✅ **云端同步成功！**")
                st.subheader("🏆 最终初评报告")
                st.write(f"项目名称：**{project_name}**")
                st.write(f"系统最终得分：**{final_score} 分**")
                if final_level == "深绿级":
                    st.success(f"最终等级：{final_level}")
                elif final_level == "中绿级":
                    st.info(f"最终等级：{final_level}")
                else:
                    st.warning(f"最终等级：{final_level}")
                st.balloons()
            else:
                st.error(
                    f"❌ **同步失败！请检查以下事项：**\n1. Secrets 密钥是否配置\n2. 表格是否共享给机器人邮箱\n\n**报错信息：** {error_msg}")