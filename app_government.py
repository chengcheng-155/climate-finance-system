import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 0. 页面与状态配置
# ==========================================
st.set_page_config(page_title="政府管理端 | 气候投融资", page_icon="🏛️", layout="wide")
st.title("🏛️ 气候投融资 - 动态管理")

# ⚠️ 请将此处替换为您自己的 Google Sheets 表格链接（需与企业端一致）
SHEET_URL = "https://docs.google.com/spreadsheets/d/1i1wzfAKODzm2BzhCE9T7JMEeOagtdXxVfTr5r3GvniA/edit?gid=0#gid=0"

# ==========================================
# 1. 建立 Google Sheets 数据库连接
# ==========================================
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # ttl=0 强制实时拉取最新数据，防止显示缓存的旧数据
    db = conn.read(spreadsheet=SHEET_URL, usecols=list(range(11)), ttl=0)
    db_connected = True
except Exception as e:
    st.error(f"⚠️ 无法连接到云端数据库，请检查 Secrets 配置。错误详情：{e}")
    db_connected = False

if db_connected:
    if db.empty or len(db) == 0:
        st.warning("📭 目前云端项目库为空，请等待企业端提交项目。")
    else:
        # 清洗数据，强制转换“一票否决”为布尔类型
        db['一票否决(环保违规)'] = db['一票否决(环保违规)'].fillna(False).astype(bool)

        # ==========================================
        # 2. 一票否决与退出机制
        # ==========================================
        st.subheader("🛑 存量项目全生命周期管理 (一票否决/直接移除)")
        st.markdown("勾选右侧选框，系统将直接从动态评级池中移除涉嫌数据造假、环保违规的项目。")

        # 使用 Data Editor 供管理员操作
        edited_db = st.data_editor(
            db[['项目ID', '项目名称', '所属行业', '气候效益综合分', '一票否决(环保违规)']],
            column_config={"一票否决(环保违规)": st.column_config.CheckboxColumn("发现违规直接移除", default=False)},
            disabled=["项目ID", "项目名称", "所属行业", "气候效益综合分"],
            hide_index=True,
            key="gov_editor",
            use_container_width=True
        )

        # 监听编辑操作，若勾选有变化，写回谷歌表格
        if not edited_db['一票否决(环保违规)'].equals(db['一票否决(环保违规)']):
            db['一票否决(环保违规)'] = edited_db['一票否决(环保违规)']
            with st.spinner("正在将移除指令同步至云端数据库..."):
                conn.update(spreadsheet=SHEET_URL, data=db)
            st.success("✅ 移除状态已同步至云端！")

        st.markdown("---")

        # ==========================================
        # 3. 筛选有效项目进行同行业动态重排
        # ==========================================
        valid_df = db[db['一票否决(环保违规)'] == False].copy()

        if len(valid_df) > 0:
            st.subheader("📈 年度同行业动态评级榜单")
            st.markdown("系统按行业分组，利用连续分自动强制排名：**Top 30% 深绿，30-60% 中绿，末尾 1% 淘汰**。")

            # 确保分数是数字类型以进行运算
            valid_df['气候效益综合分'] = pd.to_numeric(valid_df['气候效益综合分'], errors='coerce').fillna(0)

            # 核心算法：同行业百分位排名
            valid_df['行业内排位(%)'] = valid_df.groupby('所属行业')['气候效益综合分'].rank(pct=True, ascending=True)

            conditions = [
                (valid_df['行业内排位(%)'] >= 0.70),  # 前30% (70-100分位)
                (valid_df['行业内排位(%)'] >= 0.40) & (valid_df['行业内排位(%)'] < 0.70),  # 30-60%
                (valid_df['行业内排位(%)'] <= 0.01)  # 末尾1%
            ]
            choices = ['🟢 动态深绿', '🟡 动态中绿', '🔴 拟淘汰名单']
            valid_df['年度动态评级'] = np.select(conditions, choices, default='⚪ 动态浅绿')

            # 优化展示
            display_df = valid_df.sort_values(by=['所属行业', '气候效益综合分'], ascending=[True, False])
            display_df['行业击败率'] = (display_df['行业内排位(%)'] * 100).apply(lambda x: f"击败同行 {x:.1f}%")

            st.dataframe(
                display_df[['项目名称', '所属行业', '气候效益综合分', '初评等级(绝对)', '年度动态评级', '行业击败率']],
                use_container_width=True,
                hide_index=True
            )

            # ==========================================
            # 4. 末位淘汰督办预警
            # ==========================================
            elimination_df = valid_df[valid_df['年度动态评级'] == '🔴 拟淘汰名单']
            if not elimination_df.empty:
                st.error("#### ⚠️ 末位淘汰督办预警")
                st.markdown("以下项目因效益垫底触发 **1% 淘汰红线**，请依法下发整改/申诉通知：")
                st.dataframe(elimination_df[['项目名称', '所属行业', '气候效益综合分', '行业击败率']], hide_index=True)