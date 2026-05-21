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


# 移除 final_score 参数，改为直接传入评级
def save_to_database(project_name, category, green_channel, feature_industry, final_level):
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
            '气候效益综合分': "不适用(已取消算分)",  # 保持列结构，填入文字说明
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
    st.success(f"🎉 **该项目符合【{green_channel}】标准，已直接获得深绿级入库资格。**")
    cont_choice = st.radio("❓ 您是否需要继续填写量化指标挑战更高标准？", ["否", "是"], horizontal=True)
    show_advanced = (cont_choice == "是")
else:
    show_advanced = True
    force_deep_green = False

# ==========================================
# 3. 进阶评估界面 (直接对标，无算分机制)
# ==========================================
feature_industry = "否"
category = "绿色通道免评" if force_deep_green else "待分类"
val_reduction = 0.0
val_decrease = 0.0

if show_advanced:
    st.markdown("---")
    st.subheader("📍 进阶评估信息")
    col1, col2 = st.columns([1.1, 1])

    with col2:
        st.markdown("##### 📊 核心评估指标填写")
        st.info("💡 系统采取“就高不就低”原则，会自动选取达标最高的指标作为最终评级。")
        category = st.selectbox("1. 提交指标所属的大类", ["分布式发电", "集中式发电", "其他减缓类"])

    with col1:
        st.markdown("##### 🏭 产业协同与细则参考")
        feature_industry = st.selectbox("特色产业集群 (若符合，评估门槛将下调 5%)", feature_options)

        # ✨ 核心下调逻辑：若为特色产业，门槛变为原来的 0.95 倍（即下调0.05/降低5%）
        adj_ratio = 0.95 if feature_industry != "否" else 1.0

        if category == "分布式发电":
            th_deep, th_mid = 3.0, 1.0
        elif category == "集中式发电":
            th_deep, th_mid = 10.0, 5.0
        else:
            th_deep, th_mid = 0.5, 0.1

        # 应用下调后的阈值
        th_deep_adj = th_deep * adj_ratio
        th_mid_adj = th_mid * adj_ratio
        pct_deep_adj = 4.0 * adj_ratio
        pct_mid_adj = 3.0 * adj_ratio

        st.success(f"""
           📌 **《指南》项目定量评估细则参考 (对应【{category}】类)**:
           {'(✨ **已触发特色产业，各项达标门槛下调 5%**)' if adj_ratio < 1.0 else ''}

           **1. 碳减排规模效益**:
           - 🟢 **深绿级**：年减排量 ≥ **{th_deep_adj:.4g}** 万吨
           - 🟡 **中绿级**：**{th_mid_adj:.4g}** 万吨 ≤ 年减排量 < **{th_deep_adj:.4g}** 万吨
           - ⚪ **浅绿级**：年减排量 < **{th_mid_adj:.4g}** 万吨

           **2. 碳排放强度下降幅度**:
           - 🟢 **深绿级**：下降幅度 ≥ **{pct_deep_adj:.4g}%**
           - 🟡 **中绿级**：**{pct_mid_adj:.4g}%** ≤ 下降幅度 < **{pct_deep_adj:.4g}%**
           - ⚪ **浅绿级**：下降幅度 < **{pct_mid_adj:.4g}%**
           """)

    with col2:
        val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, format="%.4f")
        val_decrease = st.number_input("指标 2：强度下降幅度 (%)", min_value=0.0, format="%.4f")

# ==========================================
# 4. 提交逻辑 (去算分，直接基于门槛定级)
# ==========================================
st.markdown("---")
submit_btn = st.button("🚀 提交评估并同步至云端", use_container_width=True)

if submit_btn:
    if not project_name:
        st.warning("⚠️ 请填写项目名称！")
    elif not force_deep_green and val_reduction == 0 and val_decrease == 0:
        st.warning("⚠️ 由于不符合绿色通道，您必须至少填写一项量化指标才能提交！")
    else:
        with st.spinner('正在比对评估标准并同步数据...'):
            # 计算最新的下调后门槛
            adj_ratio = 0.95 if feature_industry != "否" else 1.0

            th_deep_adj = (3.0 if category == "分布式发电" else 10.0 if category == "集中式发电" else 0.5) * adj_ratio
            th_mid_adj = (1.0 if category == "分布式发电" else 5.0 if category == "集中式发电" else 0.1) * adj_ratio
            pct_deep_adj = 4.0 * adj_ratio
            pct_mid_adj = 3.0 * adj_ratio

            # 初始化等级： 0=浅绿, 1=中绿, 2=深绿
            level_val1 = 0
            if val_reduction > 0:
                if val_reduction >= th_deep_adj:
                    level_val1 = 2
                elif val_reduction >= th_mid_adj:
                    level_val1 = 1

            level_val2 = 0
            if val_decrease > 0:
                if val_decrease >= pct_deep_adj:
                    level_val2 = 2
                elif val_decrease >= pct_mid_adj:
                    level_val2 = 1

            # 就高不就低，取最高等级
            max_level = max(level_val1, level_val2)

            if force_deep_green:
                max_level = 2

            # 转换为文字结果
            if max_level == 2:
                final_level = "深绿级"
            elif max_level == 1:
                final_level = "中绿级"
            else:
                final_level = "浅绿级"

            # 执行云端保存 (已移除 final_score 参数)
            success, error_msg = save_to_database(project_name, category, green_channel, feature_industry, final_level)

            if success:
                st.success("✅ **数据同步成功！评估结果如下：**")
                st.subheader("🏆 气候投融资项目初评报告")
                st.write(f"项目名称：**{project_name}**")
                if final_level == "深绿级":
                    st.success(f"评估等级：{final_level}")
                elif final_level == "中绿级":
                    st.info(f"评估等级：{final_level}")
                else:
                    st.warning(f"评估等级：{final_level}")
                st.balloons()
            else:
                st.error(f"❌ **云端同步失败！请检查您的网络代理设置（SSL错误）。详细报错：** {error_msg}")