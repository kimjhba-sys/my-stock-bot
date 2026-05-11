import os
import FinanceDataReader as fdr
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta

# 금고(Secrets)에서 정보 가져오기
MY_EMAIL = os.environ.get('MY_EMAIL')
MY_PASSWORD = os.environ.get('MY_PASSWORD')
RECEIVE_EMAIL = os.environ.get('RECEIVE_EMAIL')

def get_market_analysis():
    print("데이터 분석 중...")
    stocks = fdr.StockListing('KRX')
    target_stocks = stocks.dropna(subset=['Marcap']).sort_values('Marcap', ascending=False).head(500)
    results = []
    start_date = (datetime.now() - timedelta(days=450)).strftime('%Y-%m-%d')
    for _, row in target_stocks.iterrows():
        try:
            ticker, name = row['Code'], row['Name']
            df = fdr.DataReader(ticker, start_date)
            if len(df) < 224: continue
            c, v, h, l, o = df['Close'], df['Volume'], df['High'], df['Low'], df['Open']
            ma224 = c.rolling(224).mean().iloc[-1]
            curr_c = c.iloc[-1]
            max_v_idx = v.iloc[-60:].idxmax()
            whale_p = (h.loc[max_v_idx] + l.loc[max_v_idx] + c.loc[max_v_idx]) / 3
            whale_gap = round(((curr_c - whale_p) / whale_p * 100), 1)
            avg_v = v.iloc[-21:-1].mean()
            acc_count = ((v.iloc[-10:] > avg_v * 2.5) & (c.iloc[-10:] > o.iloc[-10:])).sum()
            gap_224 = round(((curr_c - ma224) / ma224 * 100), 1)
            score = 0
            if -3 <= whale_gap <= 5: score += 40
            if 0 <= gap_224 <= 10: score += 35
            elif -5 <= gap_224 < 0: score += 15
            if acc_count >= 1: score += 25
            if score >= 50:
                results.append({'점수': score, '종목명': name, '세력선괴리': whale_gap, '224일선괴리': gap_224, '매집': f"{acc_count}일", '현재가': int(curr_c)})
        except: continue
    return pd.DataFrame(results).sort_values('점수', ascending=False).reset_index(drop=True)

def send_visual_report(df):
    if df.empty: return
    today = datetime.now().strftime('%Y-%m-%d')
    file_name = f"Stock_Report_{today}.xlsx"
    df.to_excel(file_name)
    top_10 = df.head(10)
    table_rows = ""
    for i, row in top_10.iterrows():
        score_style = "color: #d9534f; font-weight: bold;" if row['점수'] >= 90 else ""
        bg_style = "background-color: #fff3cd;" if 0 <= row['224일선괴리'] <= 3 else ""
        table_rows += f"<tr style='{bg_style}'><td style='border:1px solid #ddd; padding:8px; text-align:center;'>{i+1}</td><td style='border:1px solid #ddd; padding:8px; text-align:center;'><b>{row['종목명']}</b></td><td style='border:1px solid #ddd; padding:8px; text-align:center; {score_style}'>{row['점수']}점</td><td style='border:1px solid #ddd; padding:8px; text-align:center;'>{row['세력선괴리']}%</td><td style='border:1px solid #ddd; padding:8px; text-align:center;'>{row['224일선괴리']}%</td><td style='border:1px solid #ddd; padding:8px; text-align:center;'>{row['현재가']:,}원</td></tr>"
    html_content = f"<html><body><h2>🎯 {today} 세력 포착 리포트</h2><table style='border-collapse: collapse; width: 100%; border: 1px solid #ddd;'><thead><tr style='background-color: #f2f2f2;'><th style='border:1px solid #ddd; padding:10px;'>순위</th><th style='border:1px solid #ddd; padding:10px;'>종목명</th><th style='border:1px solid #ddd; padding:10px;'>점수</th><th style='border:1px solid #ddd; padding:10px;'>세력선괴리</th><th style='border:1px solid #ddd; padding:10px;'>224일선괴리</th><th style='border:1px solid #ddd; padding:10px;'>현재가</th></tr></thead><tbody>{table_rows}</tbody></table></body></html>"
    msg = MIMEMultipart()
    msg['Subject'] = f"🚀 [TOP 10] {today} 세력 포착 리포트"
    msg['From'], msg['To'] = MY_EMAIL, RECEIVE_EMAIL
    msg.attach(MIMEText(html_content, 'html'))
    
    # --- 이 부분이 수정된 핵심 부분입니다 ---
    with open(file_name, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())  # 바이너리로 읽기
        encoders.encode_base64(part) # 베이스64 인코딩
        part.add_header('Content-Disposition', f'attachment; filename={file_name}')
        msg.attach(part)
    # ------------------------------------

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(MY_EMAIL, MY_PASSWORD)
        server.send_message(msg)

res = get_market_analysis()
send_visual_report(res)
