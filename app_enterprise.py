import streamlit as st
import pandas as pd
import numpy as np
import os
import uuid
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 0. 全局页面配置 (必须放在脚本最开头)
# ==========================================
st.set_page_config(page_title="气候投融资综合服务平台", page_icon="🌍", layout="wide")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1i1wzfAKODzm2BzhCE9T7JMEeOagtdXxVfTr5r3GvniA/edit"


# ==========================================
# 1. 共享的数据读取与后台函数
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


# ✨ 核心功能：使用相对路径，兼容本地与云端的全国三级行政区划数据加载
@st.cache_data
def get_region_data():
    # 获取当前代码文件所在的目录路径
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 动态组装出数据文件的绝对/相对路径
    path_xlsx = os.path.join(current_dir, "ok_data_level3.xlsx")
    path_csv = os.path.join(current_dir, "ok_data_level3.csv")

    # 针对某些云平台（如 Streamlit Cloud）直接读取根目录的兼容处理
    if not os.path.exists(path_xlsx) and os.path.exists("ok_data_level3.xlsx"):
        path_xlsx = "ok_data_level3.xlsx"
    if not os.path.exists(path_csv) and os.path.exists("ok_data_level3.csv"):
        path_csv = "ok_data_level3.csv"

    df = None
    # 优先读取您上传的 xlsx 文件
    if os.path.exists(path_xlsx):
        df = pd.read_excel(path_xlsx)
    elif os.path.exists(path_csv):
        df = pd.read_csv(path_csv)
    else:
        return {"暂无数据 (请检查文件是否在同一目录)": {"暂无数据": ["暂无数据"]}}

    try:
        region_tree = {}

        # 1. 按照层级拆分数据
        provinces = df[df['deep'] == 0]
        cities = df[df['deep'] == 1]
        districts = df[df['deep'] == 2]

        # 2. 建立 ID 到 完整名称的映射
        prov_map = dict(zip(provinces['id'], provinces['ext_name']))
        city_map = dict(zip(cities['id'], cities['ext_name']))
        city_to_prov = dict(zip(cities['id'], cities['pid']))

        # 3. 初始化 省 -> 市
        for prov_id, prov_name in prov_map.items():
            region_tree[prov_name] = {}

        for city_id, city_name in city_map.items():
            prov_id = city_to_prov.get(city_id)
            if prov_id in prov_map:
                prov_name = prov_map[prov_id]
                region_tree[prov_name][city_name] = []

        # 4. 挂载 区县 -> 市
        for _, row in districts.iterrows():
            dist_name = row['ext_name']
            city_id = row['pid']

            prov_id = city_to_prov.get(city_id)
            if prov_id in prov_map and city_id in city_map:
                prov_name = prov_map[prov_id]
                city_name = city_map[city_id]
                region_tree[prov_name][city_name].append(dist_name)

        return region_tree
    except Exception as e:
        return {"数据解析失败": {str(e): ["请检查表格格式"]}}


# 实例化地区字典
region_data = get_region_data()


def save_to_database(project_name, location, industry_type, project_status, project_year, investment,
                     green_channel, feature_industry, val_reduction, eff_str, final_level):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        existing_data = conn.read(spreadsheet=SHEET_URL, ttl=0)

        new_row = pd.DataFrame([{
            '项目ID': str(uuid.uuid4())[:8],
            '申报日期': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            '项目名称': project_name,
            '项目所在地': location,
            '行业类型': industry_type,
            '建设状态': project_status,
            '投产年份': project_year,
            '项目投资额(万元)': investment,
            '绿色通道': green_channel,
            '是否特色产业': feature_industry,
            '年碳减排量(万吨)': val_reduction,
            '气候投资效率': eff_str,
            '初评等级(绝对)': final_level,
            '一票否决(环保违规)': False
        }])

        updated_db = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_db)
        return True, ""
    except Exception as e:
        return False, str(e)


@st.cache_data(ttl=10)  # 缓存10秒，兼顾实时刷新与金融端性能
def load_project_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=SHEET_URL)
        if not df.empty:
            df = df.dropna(subset=['项目ID'])
            if '一票否决(环保违规)' in df.columns:
                df = df[df['一票否决(环保违规)'] != True]
            df['年碳减排量(万吨)'] = pd.to_numeric(df['年碳减排量(万吨)'], errors='coerce').fillna(0)
            df['项目投资额(万元)'] = pd.to_numeric(df['项目投资额(万元)'], errors='coerce').fillna(0)
        return df, True
    except Exception as e:
        return pd.DataFrame(), str(e)


# ==========================================
# 2. 左侧引导栏 (Sidebar Navigation)
# ==========================================
st.sidebar.title("🧭 气候投融资系统")
st.sidebar.markdown("---")
st.sidebar.subheader("请选择访问入口：")
app_mode = st.sidebar.radio(
    "系统导航",
    ["生态环境部门 (入口A)", "金融机构筛选 (入口B)"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.caption("👨‍💻 系统架构：多云部署与数据加密互通。")
st.sidebar.caption("⚖️ 权限声明：请根据您的实际管理权限选择对应入口。")

# ==========================================
# ==========================================
# 🟩 模块 A：生态环境部门端 (项目入库)
# ==========================================
# ==========================================
if app_mode == "生态环境部门 (入口A)":
    st.title("🏢 气候投融资项目 - 入库筛查 (生态环境部门端)")
    st.markdown("填写项目信息，系统将基于《气候投融资项目库分级评估指南》进行初评。")
    st.markdown("---")

    st.subheader("🛑 负面清单审查")
    st.caption("说明：请核实项目是否存在以下情形。满足以下任一情形，项目直接终止入库资格。")

    col_n1, col_n2 = st.columns(2)
    with col_n1:
        n1 = st.checkbox("新建煤电机组（含扩容）")
        n2 = st.checkbox("现有煤电机组延寿改造（延期超过5年）")
        n3 = st.checkbox("煤化工新增产能")
    with col_n2:
        n4 = st.checkbox("新增石油勘探开发")
        n5 = st.checkbox("高耗能产业（电解铝、平板玻璃、水泥熟料）新增产能")
        n6 = st.checkbox("主要功能为化石能源运输的基础设施")

    if any([n1, n2, n3, n4, n5, n6]):
        st.error("🚫 **触发负面清单**：该项目属于明确限制类/淘汰类产业，不符合气候投融资入库标准，流程已终止。")
        st.stop()

    st.markdown("---")
    st.subheader("📝 基础信息")
    st.caption("💡 环节说明：界定项目基本身份与核心参数，并核验是否具备政策支持的“免评直通车”资格。")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        project_name = st.text_input("项目全称", placeholder="请输入项目全称")

        # ✨ 入口A：三级联动菜单 (必须全选完整)
        st.markdown("<p style='font-size: 14px; margin-bottom: 0px;'>项目所在地 (省/市/区县)</p>",
                    unsafe_allow_html=True)
        col_prov, col_city, col_dist = st.columns(3)

        with col_prov:
            prov = st.selectbox("省份", ["请选择..."] + list(region_data.keys()), label_visibility="collapsed")

        with col_city:
            city_options = ["请选择..."] + list(
                region_data[prov].keys()) if prov != "请选择..." and prov in region_data else ["请选择..."]
            city = st.selectbox("城市", city_options, label_visibility="collapsed")

        with col_dist:
            dist_options = ["请选择..."] + region_data[prov][city] if city != "请选择..." and city in region_data.get(
                prov, {}) else ["请选择..."]
            dist = st.selectbox("区县", dist_options, label_visibility="collapsed")

        # 必须选择完整的三级地址才能组装
        if prov != "请选择..." and city != "请选择..." and dist != "请选择...":
            location = f"{prov}{city}{dist}"
        else:
            location = ""

        industry_type = st.selectbox("行业类型",
                                     ["集中式可再生能源发电", "分布式可再生能源发电", "储能与智能电网",
                                      "工业节能减排", "建筑节能与绿色建筑", "交通低碳化",
                                      "其他碳汇类", "废弃物处理与非二氧化碳温室气体控制"])

    with col_b2:
        project_status = st.radio("项目建设状态", ["规划", "在建", "已建成运营"], horizontal=True)
        project_year = st.number_input("预计/实际投产年份", min_value=2000, max_value=2050, value=2024, step=1)
        investment = st.number_input("项目投资额 (万元)", min_value=0.0, step=10.0, format="%.2f")

    green_channel = st.selectbox("绿色通道审查标准",
                                 ["请选择...", "否", "典型负碳项目", "具有国家级/省部级政府认定支持的项目",
                                  "可进行碳交易的项目", "与地方特色产业相融合的低碳项目", "数字化赋能与支撑平台类项目"])
    st.caption("说明：满足以上任意一项条件即可直通‘深绿级’，各选项政策效力完全等同。")

    show_advanced = False
    force_deep_green = False

    if green_channel == "请选择...":
        st.info("💡 请完整填写基础信息，并选择是否符合绿色通道审查标准。")
        st.stop()
    elif green_channel != "否":
        force_deep_green = True
        st.success(f"🎉 **该项目符合【{green_channel}】标准，已直接获得深绿级入库资格。您可直接拉至底部点击提交。**")
        show_advanced = False
    else:
        show_advanced = True
        force_deep_green = False

    feature_industry = "否"
    val_reduction = 0.0
    val_decrease = 0.0

    if show_advanced:
        st.markdown("---")
        st.subheader("📍 进阶量化评估")
        st.caption("💡 环节说明：补充量化减排指标，系统将根据所选的 8 大行业分类自动匹配气候效益评级。")

        col1, col2 = st.columns([1, 1.1])

        with col1:
            st.markdown("##### 🏭 产业协同")
            feature_industry = st.selectbox("特色产业集群 (若符合，评估门槛将下调 5%)", feature_options)
            st.caption("说明：匹配以上任一特色产业集群，即可享受量化评估门槛下调 5% 的政策倾斜。")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("##### 📊 核心评估指标填写")
            st.info("💡 系统将根据上方填写的“投资额”与此处的“年减排量”自动核算气候投资效率。")
            val_reduction = st.number_input("指标 1：年碳减排量 (万吨)", min_value=0.0, format="%.4f")
            val_decrease = st.number_input("指标 2：强度下降幅度 (%)", min_value=0.0, format="%.4f")

        with col2:
            st.markdown("##### 📌 定量评估细则参考")
            adj_ratio = 0.95 if feature_industry != "否" else 1.0

            if industry_type == "集中式可再生能源发电":
                th_deep, th_mid, th_light = 10.0, 5.0, 0.0
            elif industry_type == "分布式可再生能源发电":
                th_deep, th_mid, th_light = 3.0, 1.0, 0.0
            elif industry_type == "工业节能减排":
                th_deep, th_mid, th_light = 5.0, 1.0, 0.1
            elif industry_type == "建筑节能与绿色建筑":
                th_deep, th_mid, th_light = 0.3, 0.05, 0.01
            else:  # 储能与智能电网、交通低碳化、其他碳汇类、废弃物处理
                th_deep, th_mid, th_light = 1.0, 0.3, 0.05

            th_deep_adj = th_deep * adj_ratio
            th_mid_adj = th_mid * adj_ratio
            th_light_adj = th_light * adj_ratio
            pct_deep_adj = 4.0 * adj_ratio
            pct_mid_adj = 3.0 * adj_ratio

            light_text = f"**{th_light_adj:.4g}** 万吨 ≤ 年减排量 < **{th_mid_adj:.4g}** 万吨" if th_light_adj > 0 else f"年减排量 < **{th_mid_adj:.4g}** 万吨"

            st.success(f"""
               📌 **《指南》项目定量评估细则参考 (对应【{industry_type}】)**:
               {'(✨ **已触发特色产业，各项达标门槛下调 5%**)' if adj_ratio < 1.0 else ''}

               **1. 年碳减排规模效益**:
               - 🟢 **深绿级**：年减排量 ≥ **{th_deep_adj:.4g}** 万吨
               - 🟡 **中绿级**：**{th_mid_adj:.4g}** 万吨 ≤ 年减排量 < **{th_deep_adj:.4g}** 万吨
               - ⚪ **浅绿级**：{light_text}
               {f"*( ⚠️ 注：若年减排量低于 **{th_light_adj:.4g}** 万吨，则不符合入库标准 )*" if th_light_adj > 0 else ""}

               **2. 碳排放强度下降幅度** (若适用):
               - 🟢 **深绿级**：下降幅度 ≥ **{pct_deep_adj:.4g}%**
               - 🟡 **中绿级**：**{pct_mid_adj:.4g}%** ≤ 下降幅度 < **{pct_deep_adj:.4g}%**
               - ⚪ **浅绿级**：下降幅度 < **{pct_mid_adj:.4g}%**
               """)

    st.markdown("---")
    st.caption("💡 确认以上信息无误后，点击下方按钮生成初评报告并存入项目库。")
    submit_btn = st.button("🚀 提交评估并生成入库报告", use_container_width=True)

    if submit_btn:
        if not project_name:
            st.warning("⚠️ 请填写项目名称！")
        elif not location:
            st.warning("⚠️ 请完整选择项目所在地的【省份 - 城市 - 区县】！")
        elif not force_deep_green and val_reduction == 0 and val_decrease == 0:
            st.warning("⚠️ 由于不符合绿色通道，您必须至少填写一项量化减排指标才能提交！")
        else:
            with st.spinner('正在比对评估标准、测算投资效率并同步数据...'):
                adj_ratio = 0.95 if feature_industry != "否" else 1.0

                if industry_type == "集中式可再生能源发电":
                    th_deep, th_mid, th_light = 10.0, 5.0, 0.0
                elif industry_type == "分布式可再生能源发电":
                    th_deep, th_mid, th_light = 3.0, 1.0, 0.0
                elif industry_type == "工业节能减排":
                    th_deep, th_mid, th_light = 5.0, 1.0, 0.1
                elif industry_type == "建筑节能与绿色建筑":
                    th_deep, th_mid, th_light = 0.3, 0.05, 0.01
                else:
                    th_deep, th_mid, th_light = 1.0, 0.3, 0.05

                th_deep_adj, th_mid_adj, th_light_adj = th_deep * adj_ratio, th_mid * adj_ratio, th_light * adj_ratio
                pct_deep_adj, pct_mid_adj = 4.0 * adj_ratio, 3.0 * adj_ratio

                level_val1 = -1
                if val_reduction > 0:
                    if val_reduction >= th_deep_adj:
                        level_val1 = 2
                    elif val_reduction >= th_mid_adj:
                        level_val1 = 1
                    elif val_reduction >= th_light_adj:
                        level_val1 = 0

                level_val2 = -1
                if val_decrease > 0:
                    if val_decrease >= pct_deep_adj:
                        level_val2 = 2
                    elif val_decrease >= pct_mid_adj:
                        level_val2 = 1
                    else:
                        level_val2 = 0

                max_level = 2 if force_deep_green else max(level_val1, level_val2)

                if max_level == -1:
                    st.error(
                        f"⚠️ **入库拦截**：该项目填报的量化指标未达到最低入库下限标准（下限要求：{th_light_adj:.4g} 万吨），无法入库！")
                else:
                    final_level = "深绿级" if max_level == 2 else ("中绿级" if max_level == 1 else "浅绿级")

                    if val_reduction > 0:
                        efficiency = investment / val_reduction
                        eff_str = f"{efficiency:.2f} 万元/万吨"
                    else:
                        eff_str = "暂无减排数据，无法测算"

                    success, error_msg = save_to_database(
                        project_name, location, industry_type, project_status, project_year, investment,
                        green_channel, feature_industry, val_reduction, eff_str, final_level
                    )

                    if success:
                        st.success("✅ **数据审查与评级完成！评估结果如下：**")
                        st.subheader("🏆 气候投融资项目 - 入库评级结论")
                        if final_level == "深绿级":
                            st.success(f"📌 此项目最终评级为：【{final_level}】")
                        elif final_level == "中绿级":
                            st.info(f"📌 此项目最终评级为：【{final_level}】")
                        else:
                            st.warning(f"📌 此项目最终评级为：【{final_level}】")

                        st.write(f"▶ **项目名称**：{project_name}")
                        st.write(f"▶ **项目所在地**：{location}")
                        st.write(f"▶ **年减排量**：{val_reduction:.4f} 万吨")
                        st.write(f"▶ **气候投资效率**：{eff_str}")
                        st.balloons()
                    else:
                        st.error(f"❌ **云端同步失败！请检查您的网络代理设置。详细报错：** {error_msg}")


# ==========================================
# ==========================================
# 🏦 模块 B：金融机构筛选端 (已入库项目)
# ==========================================
# ==========================================
elif app_mode == "金融机构筛选 (入口B)":
    st.title("🏦 气候投融资项目 - 金融机构项目筛选")
    st.markdown("对接绿色信贷、绿色债券与气候基金。从生态环境部门初筛的入库项目中，寻找符合贵机构投资标准的优质标的。")
    st.markdown("---")

    df, success_or_error = load_project_data()

    if not success_or_error is True:
        st.error(f"❌ 无法连接到云端项目库，请检查网络或密钥配置。详细报错：{success_or_error}")
        st.stop()

    if df.empty:
        st.warning("📭 目前项目库为空，请等待生态环境部门审核项目入库。")
        st.stop()

    with st.expander("🔍 展开/收起 筛选条件面板 (多条件组合)", expanded=True):
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("##### 🏅 评级与状态")
            level_filter = st.radio("项目等级筛选", ["深绿级", "中绿级", "浅绿级"], horizontal=True)
            status_filter = st.radio("项目状态", ["规划", "在建", "已建成运营"], horizontal=True)

        with col2:
            st.markdown("##### 🏭 行业与区域")
            industry_options = [
                "集中式可再生能源发电", "分布式可再生能源发电", "储能与智能电网",
                "工业节能减排", "建筑节能与绿色建筑", "交通低碳化",
                "其他碳汇类", "废弃物处理与非二氧化碳温室气体控制",
                "数字化赋能与支撑平台类项目"
            ]
            industry_filter = st.multiselect("行业类型", industry_options)

            # ✨ 入口B：三级联动菜单 (带有“不限”筛选功能的嵌套列)
            st.markdown("<p style='font-size: 14px; margin-bottom: 0px;'>地区 (省/市/区县)</p>", unsafe_allow_html=True)
            col_b_prov, col_b_city, col_b_dist = st.columns(3)
            with col_b_prov:
                b_prov = st.selectbox("省份", ["不限"] + list(region_data.keys()), key="b_prov",
                                      label_visibility="collapsed")
            with col_b_city:
                b_city_options = ["不限"] + list(
                    region_data[b_prov].keys()) if b_prov != "不限" and b_prov in region_data else ["不限"]
                b_city = st.selectbox("城市", b_city_options, key="b_city", label_visibility="collapsed")
            with col_b_dist:
                b_dist_options = ["不限"] + region_data[b_prov][
                    b_city] if b_city != "不限" and b_city in region_data.get(b_prov, {}) else ["不限"]
                b_dist = st.selectbox("区县", b_dist_options, key="b_dist", label_visibility="collapsed")

        with col3:
            st.markdown("##### 🍃 减排与规模")
            min_reduction = st.number_input("年碳减排量 (≥ 吨/年)", min_value=0.0, value=0.0, step=1000.0)
            st.caption("提示：此处输入单位为吨，系统将换算匹配入库万吨数据")
            invest_text = st.text_input("项目规模（投资额）：", placeholder="请输入门槛金额(万元)")

        with col4:
            st.markdown("##### 🔖 交易追踪")
            reg_filter = st.radio("是否完成碳市场注册 (CCER/VCS)", ["不限", "已注册", "拟注册"], horizontal=True)
            st.info("💡 提示：系统基于入库时的绿色通道标签匹配注册意向。")

    # 执行过滤逻辑
    filtered_df = df.copy()

    # 1. 过滤级别
    filtered_df = filtered_df[filtered_df['初评等级(绝对)'] == level_filter]

    # 2. 过滤状态
    if '建设状态' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['建设状态'] == status_filter]

    # 3. 过滤行业
    if industry_filter:
        ind_mask = filtered_df['行业类型'].isin(industry_filter)
        if "数字化赋能与支撑平台类项目" in industry_filter:
            green_mask = filtered_df['绿色通道'].str.contains("数字化赋能", na=False)
            filtered_df = filtered_df[ind_mask | green_mask]
        else:
            filtered_df = filtered_df[ind_mask]

    # 4. ✨ 过滤地区 (基于三级联动的灵活组装字符串匹配)
    loc_search = ""
    if b_prov != "不限": loc_search += b_prov
    if b_city != "不限": loc_search += b_city
    if b_dist != "不限": loc_search += b_dist

    if loc_search:
        filtered_df = filtered_df[filtered_df['项目所在地'].str.contains(loc_search, na=False)]

    # 5. 过滤减排量
    filtered_df = filtered_df[filtered_df['年碳减排量(万吨)'] >= (min_reduction / 10000.0)]

    # 6. 过滤投资额
    if invest_text.strip():
        try:
            min_invest_val = float(invest_text.strip())
            filtered_df = filtered_df[filtered_df['项目投资额(万元)'] >= min_invest_val]
        except ValueError:
            st.error("⚠️ 项目规模（投资额）格式不正确，请输入有效的数字！")

    # 7. 过滤碳市场
    if reg_filter != "不限" and '绿色通道' in filtered_df.columns:
        if reg_filter == "已注册":
            filtered_df = filtered_df[filtered_df['绿色通道'].str.contains("可进行碳交易的项目", na=False)]
        elif reg_filter == "拟注册":
            filtered_df = filtered_df[filtered_df['绿色通道'].str.contains("碳交易|与地方特色", na=False)]

    st.markdown("### 📊 筛选结果列表 (含数据管理)")

    if not filtered_df.empty:
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric(label="🎯 命中项目总数", value=f"{len(filtered_df)} 个")
        kpi2.metric(label="💰 撬动总投资额估算", value=f"{filtered_df['项目投资额(万元)'].sum():,.0f} 万元")
        kpi3.metric(label="🌍 年总减排量贡献", value=f"{filtered_df['年碳减排量(万吨)'].sum():,.2f} 万吨")
    else:
        st.warning("🙈 未找到符合上述组合条件的项目，请尝试放宽筛选条件。")

    display_columns = {
        '项目ID': '项目ID',
        '项目名称': '项目名称',
        '初评等级(绝对)': '等级',
        '行业类型': '行业',
        '项目所在地': '地区',
        '年碳减排量(万吨)': '年减排量(万吨)',
        '项目投资额(万元)': '投资额(万元)',
        '气候投资效率': '气候投资效率'
    }

    cols_to_show = [col for col in display_columns.keys() if col in filtered_df.columns]
    display_df = filtered_df[cols_to_show].rename(columns=display_columns)

    if not display_df.empty:
        display_df['勾选删除'] = False

        edited_df = st.data_editor(
            display_df,
            column_config={
                "项目ID": None,
                "勾选删除": st.column_config.CheckboxColumn("🗑️ 勾选删除", default=False)
            },
            disabled=[col for col in display_df.columns if col != '勾选删除'],
            use_container_width=True,
            hide_index=True,
            height=400
        )

        rows_to_delete = edited_df[edited_df['勾选删除'] == True]

        if not rows_to_delete.empty:
            st.warning(f"⚠️ 您已勾选了 {len(rows_to_delete)} 个项目，此操作将从云端彻底抹除项目数据。")
            if st.button("🚨 确认删除勾选项"):
                ids_to_delete = rows_to_delete['项目ID'].tolist()

                with st.spinner('正在从云端数据库中同步删除...'):
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    raw_data = conn.read(spreadsheet=SHEET_URL, ttl=0)

                    updated_data = raw_data[~raw_data['项目ID'].isin(ids_to_delete)]
                    conn.update(spreadsheet=SHEET_URL, data=updated_data)

                    st.success("✅ 所选项目已成功从数据库移除！")

                    load_project_data.clear()
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        col_dl1, col_dl2 = st.columns([1, 4])
        with col_dl1:
            csv_df = display_df.drop(columns=['项目ID', '勾选删除'], errors='ignore')
            csv_data = csv_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 导出筛选名单 (CSV)",
                data=csv_data,
                file_name=f"气候投融资筛选库_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                use_container_width=True
            )