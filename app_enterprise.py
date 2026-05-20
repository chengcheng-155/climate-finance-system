import streamlit as st
import pandas as pd
import numpy as np
import os
import uuid
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 【针对 SSL 报错的本地网络修复方案】
# 如果你在本地电脑运行且一直报 SSL 错误，请删除下面两行代码前面的 # 号，
# 并确保端口号（如 7890）与你电脑上的代理软件端口一致。
# os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
# os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

# ==========================================
# 0. 页面与状态配置
# ==========================================
st.set_page_config(page_title="企业申报端 | 气候投融资系统", page_icon="🏢", layout="wide")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1i1wzfAKODzm2BzhCE9T7JMEeOagtdXxVfTr5r3GvniA/edit"

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
# 2. 前端界面布局
# ==========================================
st.title("🏢 气候投融资项目 - 企业入库申报")
st.markdown("填写项目信息，系统将基于《气候投融资项目库分级评估指南》进行初评。")
st.markdown("---")

st.subheader("📝 基础与政策信息")
project_name = st.text_input("项目全称", placeholder="请输入项目全称")

green_channel = st.selectbox("绿色通道审查标准",
                             ["请选择...", "否", "典型负碳项目", "具有国家级/省部级政府认定支持的项目",
                              "可进行碳交易的项目", "与地方特色产业相融合的低碳项目", "赋能支撑类项目"])

show_advanced = False
force_deep_green = False

if green_channel == "请选择...":
    st.info("👆 请先输入项目名称，并选择是否符合绿色通道审查标准。")
    st.stop()
elif green_channel != "否":
    force_deep_green = True
    st.success(f"🎉 **该项目符合【{green_channel}】标准，已直接获得深绿级（100分）入库资格。**")
    cont_choice = st.radio("❓ 您是否需要继续填写其他量化指标（系统将自动对比并记录最高分）？", ["否", "是"], horizontal=True)
    show_advanced = (cont_choice == "是")
else:
    show_advanced = True
    force_deep_green = False

# ==========================================
# 3. 进阶评估界面 (精妙排版：还原设计并保持联动)
# ==========================================
feature_industry = "否"
category = "绿色通道免评" if force_deep_green else "待分类"
val_reduction = 0.0
val_decrease = 0.0

if show_advanced:
    st.markdown("---")
    st.subheader("📍 进阶评估信息")
    col1, col2 = st.columns([1.1, 1])

    # 【核心修改点】：先在右侧（col2）渲染大类选择框，获取企业选的类型
    with col2:
        st.markdown("##### 📊 核心评估指标填写")
        st.info("💡 选填左侧对应大类的指标，系统将自动选取最强优势项作为最终评分。")
        category = st.selectbox("1. 提交指标所属的大类", ["分布式发电", "集中式发电", "其他减缓类"])

    # 然后回到左侧（col1），利用上面获取到的 category 实时计算标准
    with col1:
        st.markdown("##### 🏭 产业协同与细则参考")
        feature_industry = st.selectbox("特色产业集群 (享受1.05倍加权)", feature_options)

        if category == "分布式发电": th_deep, th_mid = 3.0, 1.0
        elif category == "集中式发电": th_deep, th_mid = 10.0, 5.0
        else: th_deep, th_mid = 0.5, 0.1

        st.success(f"""
           📌 **《指南》项目定量评估细则参考 (对应【{category}】类)**:

           **1. 碳减排规模效益**:
           - 🟢 **深绿级**：年减排量 ≥ **{th_deep}** 万吨
           - 🟡 **中绿级**：**{th_mid}** 万吨 ≤ 年减排量 < **{th_deep}** 万吨
           - ⚪ **浅绿级**：年减排量 < **{th_mid}** 万吨

           **2. 碳排放强度下降幅度**:
           - 🟢 **深绿级**：下降幅度 ≥ **4%**
           - 🟡 **中绿级**：**3%** ≤ 下降幅度 < **4%**
           - ⚪ **浅绿级**：下降幅度 < **3%**
           """)

    # 最后再回到右侧（col2），补齐剩下的输入框
    with col2:
        val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, format="%.4f")
        val_decrease = st.number_input("指标 2：强度下降幅度 (%)", min_value=0.0, format="%.4f")

# ==========================================
# 4. 提交逻辑
# ==========================================
st.markdown("---")
submit_btn = st.button("🚀 提交评估并同步至云端", use_container_width=True)

if submit_btn:
    if not project_name:
        st.warning("⚠️ 请填写项目名称！")
    elif not force_deep_green and val_reduction == 0 and val_decrease == 0:
        st.warning("⚠️ 由于不符合绿色通道，您必须至少填写一项量化指标才能提交！")
    else:
        with st.spinner('正在连接云端数据库并计算评分...'):
            weight = 1.05 if feature_industry != "否" else 1.0
            scores = []

            if val_reduction > 0:
                th_base = 3 if category == "分布式发电" else 10 if category == "集中式发电" else 0.5
                scores.append((val_reduction / th_base) * 100)
            if val_decrease > 0:
                scores.append((val_decrease / 4.0) * 100)

            indicator_score = max(scores) if scores else 0
            base_score = indicator_score
            if force_deep_green:
                base_score = max(base_score, 100.0)

            final_score = round(base_score * weight, 2)
            final_level = "深绿级" if final_score >= 100 else "中绿级" if final_score >= 60 else "浅绿级"

            success, error_msg = save_to_database(project_name, category, green_channel, feature_industry, final_score, final_level)

            if success:
                st.success("✅ **数据同步成功！评估结果如下：**")
                st.subheader("🏆 气候投融资项目初评报告")
                st.write(f"项目名称：**{project_name}**")
                st.write(f"最终综合得分：**{final_score} 分**")
                if final_level == "深绿级": st.success(f"评估等级：{final_level}")
                elif final_level == "中绿级": st.info(f"评估等级：{final_level}")
                else: st.warning(f"评估等级：{final_level}")
                st.balloons()
            else:
                st.error(f"❌ **云端同步失败！请检查您的网络代理设置（SSL错误）。详细报错：** {error_msg}")