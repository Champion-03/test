import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import plotly.graph_objects as go

# กำหนดตัวแปรสำหรับ Brush Number
brush_numbers = list(range(1, 33))

# ฟังก์ชันคำนวณค่าเฉลี่ยและค่าผลเบี่ยงเบนมาตรฐาน
def calculate_stats(rate_list):
    valid_rates = [rate for rate in rate_list if pd.notna(rate)]  # กรองเฉพาะค่าที่ไม่เป็น NaN
    mean_rate = np.mean(valid_rates)
    std_dev = np.std(valid_rates)
    return mean_rate, std_dev

# ฟังก์ชันตรวจสอบว่า rate อยู่ในขอบเขตที่สมเหตุสมผล
def is_rate_valid(rate, mean_rate, std_dev, threshold=2):
    return (rate >= mean_rate - threshold * std_dev) and (rate <= mean_rate + threshold * std_dev)

# สมมติว่า avg_rate_upper และ avg_rate_lower คือลิสต์ของค่า rate จากหลายๆ ชีต
avg_rate_upper = [0.1, 0.5, 0.2, 0.4, 0.3, 0.6, 1.0, 0.8, 0.9, 0.7, 1.1, 1.2, 0.3, 0.4, 0.5, 0.6, 0.3, 0.2, 0.4, 0.3, 0.8, 0.5, 0.6, 0.4, 0.7, 0.8, 0.9, 1.0, 0.2, 0.4, 0.3, 0.7]  # ตัวอย่างค่า Upper Rates
avg_rate_lower = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9, 0.8, 0.6, 0.7, 0.8, 0.9, 1.0, 0.5, 0.3, 0.4, 0.6, 0.5, 0.7, 0.6, 0.5, 0.4, 0.3, 0.6, 0.5, 0.8, 0.9, 1.1, 0.2, 0.4, 0.3, 0.5]  # ตัวอย่างค่า Lower Rates

# คำนวณค่าเฉลี่ยและค่าผลเบี่ยงเบนมาตรฐาน
mean_rate_upper, std_dev_upper = calculate_stats(avg_rate_upper)
mean_rate_lower, std_dev_lower = calculate_stats(avg_rate_lower)

# กรองค่าผิดปกติจาก avg_rate_upper และ avg_rate_lower
filtered_upper_rates = [rate if is_rate_valid(rate, mean_rate_upper, std_dev_upper) else np.nan for rate in avg_rate_upper]
filtered_lower_rates = [rate if is_rate_valid(rate, mean_rate_lower, std_dev_lower) else np.nan for rate in avg_rate_lower]

# คำนวณค่าเฉลี่ยใหม่หลังจากการกรอง
filtered_avg_upper = np.nanmean(filtered_upper_rates)
filtered_avg_lower = np.nanmean(filtered_lower_rates)

# เชื่อมต่อกับ Google Sheets
service_account_info = {
    # ข้อมูลบัญชีบริการของคุณ
}
creds = Credentials.from_service_account_info(service_account_info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
sheet_url = "https://docs.google.com/spreadsheets/d/1SOkIH9jchaJi_0eck5UeyUR8sTn2arndQofmXv5pTdQ"  # URL ของ Google Sheets

# ดึงข้อมูลจาก Google Sheets
xls = pd.ExcelFile(sheet_url)
sheet_names = [ws.title for ws in gc.open_by_url(sheet_url).worksheets() if ws.title.lower().startswith("sheet")]

# คำนวณและกรองค่า `rate` จากแต่ละชีต
upper_rates, lower_rates = {n: {} for n in brush_numbers}, {n: {} for n in brush_numbers}

for sheet in sheet_names:
    df_raw = xls.parse(sheet, header=None)
    try:
        hours = float(df_raw.iloc[0, 7])
    except:
        continue
    df = xls.parse(sheet, skiprows=1, header=None)

    lower_df_sheet = df.iloc[:, 0:3]
    lower_df_sheet.columns = ["No_Lower", "Lower_Previous", "Lower_Current"]
    lower_df_sheet = lower_df_sheet.dropna().apply(pd.to_numeric, errors='coerce')

    upper_df_sheet = df.iloc[:, 4:6]
    upper_df_sheet.columns = ["Upper_Current", "Upper_Previous"]
    upper_df_sheet = upper_df_sheet.dropna().apply(pd.to_numeric, errors='coerce')

    for n in brush_numbers:
        u_row = upper_df_sheet[upper_df_sheet["No_Upper"] == n]
        if not u_row.empty:
            diff = u_row.iloc[0]["Upper_Current"] - u_row.iloc[0]["Upper_Previous"]
            rate = diff / hours if hours > 0 else np.nan
            if is_rate_valid(rate, mean_rate_upper, std_dev_upper):
                upper_rates[n][f"Upper_{sheet}"] = rate
            else:
                upper_rates[n][f"Upper_{sheet}"] = np.nan

        l_row = lower_df_sheet[lower_df_sheet["No_Lower"] == n]
        if not l_row.empty:
            diff = l_row.iloc[0]["Lower_Previous"] - l_row.iloc[0]["Lower_Current"]
            rate = diff / hours if hours > 0 else np.nan
            if is_rate_valid(rate, mean_rate_lower, std_dev_lower):
                lower_rates[n][f"Lower_{sheet}"] = rate
            else:
                lower_rates[n][f"Lower_{sheet}"] = np.nan

# สร้าง DataFrame จากค่าที่กรองแล้ว
upper_df = pd.DataFrame.from_dict(upper_rates, orient='index').fillna(0)
lower_df = pd.DataFrame.from_dict(lower_rates, orient='index').fillna(0)

# คำนวณค่าเฉลี่ย
upper_df["Avg Rate (Upper)"] = upper_df.apply(lambda row: np.nanmean(row[row > 0]), axis=1)
lower_df["Avg Rate (Lower)"] = lower_df.apply(lambda row: np.nanmean(row[row > 0]), axis=1)

# แสดงผลการคำนวณ
st.subheader("📋 ตาราง Avg Rate - Upper")
def style_upper(val):
    return 'color: red; font-weight: bold' if isinstance(val, float) and val > 0 else ''
st.dataframe(upper_df.style.applymap(style_upper, subset=["Avg Rate (Upper)"]).format("{:.6f}"), use_container_width=True)

st.subheader("📋 ตาราง Avg Rate - Lower")
def style_lower(val):
    return 'color: red; font-weight: bold' if isinstance(val, float) and val > 0 else ''
st.dataframe(lower_df.style.applymap(style_lower, subset=["Avg Rate (Lower)"]).format("{:.6f}"), use_container_width=True)

# แสดงผลกราฟ
st.subheader("📊 กราฟรวม Avg Rate")
fig_combined = go.Figure()
fig_combined.add_trace(go.Scatter(x=brush_numbers, y=filtered_upper_rates, mode='lines+markers+text', name='Upper Avg Rate', line=dict(color='red'), text=[str(i) for i in brush_numbers], textposition='top center'))
fig_combined.add_trace(go.Scatter(x=brush_numbers, y=filtered_lower_rates, mode='lines+markers+text', name='Lower Avg Rate', line=dict(color='deepskyblue'), text=[str(i) for i in brush_numbers], textposition='top center'))
fig_combined.update_layout(xaxis_title='Brush Number', yaxis_title='Wear Rate (mm/hour)', template='plotly_white')
st.plotly_chart(fig_combined, use_container_width=True)

st.subheader("🔺 กราฟ Avg Rate - Upper")
fig_upper = go.Figure()
fig_upper.add_trace(go.Scatter(x=brush_numbers, y=filtered_upper_rates, mode='lines+markers+text', name='Upper Avg Rate', line=dict(color='red'), text=[str(i) for i in brush_numbers], textposition='top center'))
fig_upper.update_layout(xaxis_title='Brush Number', yaxis_title='Wear Rate (mm/hour)', template='plotly_white')
st.plotly_chart(fig_upper, use_container_width=True)

st.subheader("🔻 กราฟ Avg Rate - Lower")
fig_lower = go.Figure()
fig_lower.add_trace(go.Scatter(x=brush_numbers, y=filtered_lower_rates, mode='lines+markers+text', name='Lower Avg Rate', line=dict(color='deepskyblue'), text=[str(i) for i in brush_numbers], textposition='top center'))
fig_lower.update_layout(xaxis_title='Brush Number', yaxis_title='Wear Rate (mm/hour)', template='plotly_white')
st.plotly_chart(fig_lower, use_container_width=True)

