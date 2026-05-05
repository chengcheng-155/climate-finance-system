import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="政府管理端 | 气候投融资", page_icon="🏛️", layout="wide")
st.title("🏛️ 气候投融资 - 政府动态管理大屏")

DB_PATH = "project_database.csv"

# 1. 读取共享数据库
if not os.path.exists(DB_PATH):
    st.warning("📭 目前数据库为空，等待企业端提交项目。")
else:
    # 强制将 '一票否决(环保违规)' 列读取为布尔值 (True/False)
    db = pd.read_csv(DB_PATH, dtype={'一票否决(环保违规)': bool})

    # 2. 一票否决与退出机制 (Data Editor)
    st.subheader("🛑 存量项目全生命周期管理 (一票否决/直接移除)")
    st.markdown("勾选右侧选框，系统将直接从动态评级池中移除涉嫌数据造假、环保违规的项目。")

    edited_db = st.data_editor(
        db[['项目ID', '项目名称', '所属行业', '气候效益综合分', '一票否决(环保违规)']],
        column_config={"一票否决(环保违规)": st.column_config.CheckboxColumn("发现违规直接移除", default=False)},
        disabled=["项目ID", "项目名称", "所属行业", "气候效益综合分"],
        hide_index=True,
        key="gov_editor"
    )

    # 将政府在网页上的修改保存回数据库
    if not edited_db.equals(db[['项目ID', '项目名称', '所属行业', '气候效益综合分', '一票否决(环保违规)']]):
        db['一票否决(环保违规)'] = edited_db['一票否决(环保违规)']
        db.to_csv(DB_PATH, index=False)
        st.success("✅ 移除状态已更新！")

    st.markdown("---")

    # 3. 筛选有效项目进行同行业动态重排
    valid_df = db[db['一票否决(环保违规)'] == False].copy()

    if len(valid_df) > 0:
        st.subheader("📈 年度同行业动态评级榜单")
        st.markdown("系统按行业分组，自动强制排名：**Top 30%深绿，30-60%中绿，末尾1%淘汰**。")

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
            use_container_width=True, hide_index=True)

        # 4. 末位淘汰预警
        elimination_df = valid_df[valid_df['年度动态评级'] == '🔴 拟淘汰名单']
        if not elimination_df.empty:
            st.error("#### ⚠️ 末位淘汰督办预警")
            st.markdown("以下项目因效益垫底触发 1% 淘汰红线，请依法下发整改/申诉通知：")
            st.dataframe(elimination_df[['项目名称', '所属行业', '气候效益综合分', '行业击败率']], hide_index=True)

        st.markdown("---")

        # 5. 基准线动态更新
        st.subheader("🔄 行业先进性参考基准 (系统自学习迭代)")
        st.markdown("自动提取当年 **深绿/中绿** 级项目的真实碳排放强度，求平均值作为明年新基准。")

        # 确保实际强度列为数字
        valid_df['实际碳排放强度'] = pd.to_numeric(valid_df['实际碳排放强度'], errors='coerce')
        benchmark_df = valid_df[
            valid_df['年度动态评级'].isin(['🟢 动态深绿', '🟡 动态中绿']) & valid_df['实际碳排放强度'].notna()]

        if len(benchmark_df) > 0:
            new_baseline = benchmark_df.groupby('所属行业')['实际碳排放强度'].mean().reset_index()
            new_baseline.rename(columns={'实际碳排放强度': '下年度建议基准线 (平均强度)'}, inplace=True)
            st.dataframe(new_baseline, use_container_width=True, hide_index=True)
        else:
            st.info("💡 暂无足够填报了“实际碳排放强度”的优质项目来测算明年基准线。")