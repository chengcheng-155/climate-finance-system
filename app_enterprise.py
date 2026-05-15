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


# 封装写库函数，保持代码整洁
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
# 2. 前端界面布局 (动态渐进式流程)
# ==========================================
st.title("🏢 气候投融资项目 - 企业入库申报")
st.markdown("填写项目信息，系统将基于《气候投融资项目库分级评估指南》进行初评。")
st.markdown("---")

st.subheader("📝 基础与政策信息")
project_name = st.text_input("项目全称", placeholder="请输入项目全称")

# 增加“请选择...”作为默认项，控制下方界面的显示
green_channel = st.selectbox("绿色通道审查标准",
                             ["请选择...",
                              "否",
                              "典型负碳项目",
                              "具有国家级/省部级政府认定支持的项目",
                              "可进行碳交易的项目",
                              "与地方特色产业相融合的低碳项目",
                              "赋能支撑类项目"])

# 状态控制变量
show_advanced = False
is_green_channel = False

# ---------------------------------------------------------
# 动态判定逻辑
# ---------------------------------------------------------
if green_channel == "请选择...":
    st.info("👆 请先输入项目名称，并选择是否符合绿色通道审查标准。")

elif green_channel == "否":
    # 不符合绿色通道：直接不啰嗦，立刻展开进阶指标面板
    show_advanced = True
    is_green_channel = False

else:
    # 符合绿色通道：给予提示并询问是否继续
    is_green_channel = True
    st.success(f"🎉 **该项目符合【{green_channel}】标准，触发绿色通道，保底获得 100 分（深绿级）。**")

    continue_fill = st.radio("您是否需要继续填报进阶量化指标以冲击更高分数？",
                             ("否，直接以 100 分 (深绿级) 提交入库", "是，我要继续填报以获取更高加分"))

    if continue_fill.startswith("是"):
        show_advanced = True
    else:
        # 直接提交绿色通道免评数据
        st.markdown("---")
        if st.button("🚀 提交评估并同步至云端", key="btn_quick", use_container_width=True):
            if not project_name:
                st.warning("⚠️ 请填写项目名称！")
            else:
                with st.spinner('正在同步云端数据库...'):
                    success, error_msg = save_to_database(
                        project_name=project_name,
                        category="绿色通道免评",
                        green_channel=green_channel,
                        feature_industry="否",
                        final_score=100.0,
                        final_level="深绿级"
                    )
                    if success:
                        st.success("✅ **评估数据已成功同步至政府管理云端数据库。**")
                        st.balloons()
                    else:
                        st.error(f"⚠️ 云端同步失败。错误: {error_msg}")

# ---------------------------------------------------------
# 进阶评估信息面板 (受 show_advanced 控制)
# ---------------------------------------------------------
if show_advanced:
    st.markdown("---")
    st.subheader("📍 进阶评估信息")

    col1, col2 = st.columns([1.1, 1])

    with col1:
        st.markdown("##### 🏭 产业协同")
        feature_industry = st.selectbox("特色产业集群 (享受1.05倍加权)", feature_options)

        st.markdown("<br>", unsafe_allow_html=True)
        category_for_guide = st.selectbox("减排量项目大类 (用于查看下方细则参考)",
                                          ["分布式发电", "集中式发电", "其他减缓类"], key="guide_cat")
        if category_for_guide == "分布式发电":
            th_deep, th_mid = 3.0, 1.0
        elif category_for_guide == "集中式发电":
            th_deep, th_mid = 10.0, 5.0
        else:
            th_deep, th_mid = 0.5, 0.1

        st.success(f"""
        📌 **《指南》项目定量评估细则参考 (对应 {category_for_guide}类)**:

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
        st.info("💡 **提示**：选填一项或多项指标。系统将自动选取最强优势指标作为定级依据。")

        category = st.selectbox("1. 减排量项目大类 (必选)", ["分布式发电", "集中式发电", "其他减缓类"],
                                index=["分布式发电", "集中式发电", "其他减缓类"].index(st.session_state.guide_cat))
        val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, value=0.0, format="%.4f")
        val_decrease = st.number_input("指标 2：强度下降幅度 (%)", min_value=0.0, value=0.0, format="%.4f")

    # ---------------------------------------------------------
    # 进阶面板