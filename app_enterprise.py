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

# ⚠️ 请将此处替换为您自己的 Google Sheets 表格链接
SHEET_URL = "https://docs.google.com/spreadsheets/d/1i1wzfAKODzm2BzhCE9T7JMEeOagtdXxVfTr5r3GvniA/edit?gid=0#gid=0"


# ==========================================
# 1. 读取行业先进值附件 (自动适配云端相对路径)
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
        st.sidebar.error("⚠️ 读取本地附件失败，使用测试数据。")
        clusters = ['新能源汽车产业集群']
        industry_dict = {'测试行业A': 100.5}

    return ['否'] + clusters, industry_dict, ["手动输入先进值 (不在列表中)"] + list(industry_dict.keys())


feature_options, industry_dict, industry_options = load_excel_data()

# ==========================================
# 2. 前端界面
# ==========================================
st.title("🏢 气候投融资项目 - 企业入库申报")
st.markdown("填写项目信息，系统将进行智能初评，并将数据安全同步至政府管理云端。")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📝 基础与政策信息")
    project_name = st.text_input("1. 项目名称", placeholder="请输入项目全称")
    green_channel = st.selectbox("2. 绿色通道审查",
                                 ["否", "是 - 典型负碳项目", "是 - 具有国家级/省部级政府认定支持的项目",
                                  "是 - 可进行国内外碳市场交易的项目", "是 - 与地方特色产业相融合的低碳项目",
                                  "是 - 赋能支撑类项目"])
    feature_industry = st.selectbox("3. 产业协同：特色产业集群 (享 1.05倍 权重)", feature_options)

    st.markdown("---")
    st.subheader("🏭 行业基准信息")
    selected_industry = st.selectbox("4. 所属行业", industry_options)

    if selected_industry == "手动输入先进值 (不在列表中)":
        baseline_value = st.number_input("5. 行业先进值基准 (手动输入)", min_value=0.0, format="%.4f")
        db_industry_name = "其他(手动输入)"
    else:
        baseline_value = st.number_input(f"5. 系统匹配【{selected_industry}】先进值",
                                         value=float(industry_dict[selected_industry]), format="%.4f")
        db_industry_name = selected_industry

    if baseline_value > 0:
        st.info(f"📌 **《指南》强度评估绝对阈值参考**：\n"
                f"1. **深绿级**：项目强度 ≤ **{baseline_value:.4f}**\n"
                f"2. **中绿级**：项目强度 介于 **{baseline_value:.4f}** 与 **{baseline_value * 1.25:.4f}** 之间\n"
                f"3. **浅绿级**：项目强度 > **{baseline_value * 1.25:.4f}**")

with col2:
    st.subheader("📊 气候效益指标")
    st.info("💡 **提示**：选填一项或多项指标。系统将自动提取折算分最高的一项作为最终依据。")
    category = st.selectbox("减排量项目大类", ["分布式发电", "集中式发电", "其他减缓类"])
    val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, value=0.0, format="%.4f")
    val_intensity = st.number_input("指标 2：项目实际碳排放强度 (比值)", min_value=0.0, value=0.0, format="%.4f")
    val_decrease = st.number_input("指标 3：强度下降幅度 (%)", min_value=0.0, value=0.0, format="%.4f",
                                   help="例如 4% 请填 4")

# ==========================================
# 3. 连续评分计算与同步至 Google Sheets
# ==========================================
st.markdown("---")
if st.button("🚀 提交评估并同步至云端", use_container_width=True):
    if not project_name:
        st.warning("⚠️ 请填写项目名称！")
    elif val_reduction == 0 and val_intensity == 0 and val_decrease == 0 and green_channel == "否":
        st.warning("⚠️ 至少需要填写一项非零的评估指标数值，或符合绿色通道！")
    else:
        with st.spinner('系统正在运算并连接云端数据库，请稍候...'):
            weight = 1.05 if feature_industry != "否" else 1.0
            continuous_scores = []

            # 1. 减排量折算
            if val_reduction > 0:
                th_deep = 3 if category == "分布式发电" else 10 if category == "集中式发电" else 0.5
                continuous_scores.append((val_reduction / th_deep) * 100)

            # 2. 碳强度折算
            if val_intensity > 0 and baseline_value > 0:
                continuous_scores.append((baseline_value / val_intensity) * 100)

            # 3. 下降幅度折算
            if val_decrease > 0:
                continuous_scores.append((val_decrease / 4.0) * 100)

            base_score = max(continuous_scores) if continuous_scores else 0
            if green_channel != "否":
                base_score = max(base_score, 100)  # 绿色通道保底100分

            final_climate_score = base_score * weight
            final_level = "深绿级" if final_climate_score >= 100 else "中绿级" if final_climate_score >= 60 else "浅绿级"

            # 结果展示
            st.success("✅ **评估完成！数据已安全同步至政府管理端。**")
            st.subheader("🏆 最终初评报告")
            if final_level == "深绿级":
                st.success(f"### 🟢 综合初评：{final_level} \n **气候效益综合分**: {final_climate_score:.1f}分")
            elif final_level == "中绿级":
                st.info(f"### 🟡 综合初评：{final_level} \n **气候效益综合分**: {final_climate_score:.1f}分")
            else:
                st.warning(f"### ⚪ 综合初评：{final_level} \n **气候效益综合分**: {final_climate_score:.1f}分")

            # ----------------------------------------------------
            # 将新数据写入 Google Sheets
            # ----------------------------------------------------
            try:
                # 建立连接
                conn = st.connection("gsheets", type=GSheetsConnection)

                # 读取已有数据 (ttl=0 确保每次读取最新)
                existing_data = conn.read(spreadsheet=SHEET_URL, usecols=list(range(11)), ttl=0)

                # 构造新的一行数据
                new_data = pd.DataFrame([{
                    '项目ID': str(uuid.uuid4())[:8],
                    '申报日期': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    '项目名称': project_name,
                    '所属行业': db_industry_name,
                    '项目大类': category if val_reduction > 0 else "强度评估类",
                    '绿色通道': green_channel,
                    '是否特色产业': feature_industry,
                    '实际碳排放强度': val_intensity if val_intensity > 0 else np.nan,
                    '气候效益综合分': round(final_climate_score, 2),
                    '初评等级(绝对)': final_level,
                    '一票否决(环保违规)': False
                }])

                # 合并并更新表
                updated_data = pd.concat([existing_data, new_data], ignore_index=True)
                conn.update(spreadsheet=SHEET_URL, data=updated_data)

            except Exception as e:
                st.error(f"⚠️ 无法连接到云端数据库，请检查您的 Secrets 配置或网络。错误详情: {e}")