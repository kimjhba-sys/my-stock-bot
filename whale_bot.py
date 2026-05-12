import FinanceDataReader as fdr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
import os

# --- [1. 비밀 금고(GitHub Secrets)에서 정보 가져오기] ---
# 괄호 안은 본인의 이메일 주소가 아니라, GitHub에 등록한 '이름표'를 적는 곳입니다.
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

def get_pro_whale_report():
    target_date = datetime.now().strftime("%Y%m%d")
    start_dt = (datetime.now() - timedelta(days=400)).strftime('%Y-%m-%d')
    
    # 시가총액 상위 200개 종목 스캔
    stocks = fdr.StockListing('KRX').dropna(subset=['Marcap']).sort_values('Marcap', ascending=False).head(200)
    final_results = []

    for _, row in stocks.iterrows():
        try:
            ticker, name = row['Code'], row['Name']
            df = fdr.DataReader(ticker, start_dt)
            if len(df) < 100: continue
            
            c = df['Close']
            delta = c.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df['RSI'] = 100 - (100 / (1 + (gain / loss)))
            df['MA20'] = c.rolling(window=20).mean()
            df['std'] = c.rolling(window=20).std()
            df['BB_low'] = df['MA20'] - (df['std'] * 2)
            
            curr_c, curr_rsi = c.iloc[-1], df['RSI'].iloc[-1]
            curr_bb_low = df['BB_low'].iloc[-1]

            # 세력선 및 손절가 계산
            max_v_idx = df['Volume'].iloc[-60:].idxmax()
            whale_p = (df['High'].loc[max_v_idx] + df['Low'].loc[max_v_idx] + df['Close'].loc[max_v_idx]) / 3
            stop_loss = int(whale_p * 0.95) 
            whale_gap = round(((curr_c - whale_p) / whale_p * 100), 1)

            # 필터: 손절가가 현재가보다 높으면 탈락
            if curr_c <= stop_loss: continue

            score = 50 
            if -2 <= whale_gap <= 3: score += 20
            if curr_rsi <= 35: score += 15
            if curr_c <= curr_bb_low * 1.02: score += 15

            if score >= 65:
                status = "🔥 강세" if curr_rsi >= 65 else "🧊 과매도" if curr_rsi <= 35 else "⚖️ 안정"
                final_results.append({
                    '종목명': name, '점수': score, '상태': status, '현재가': int(curr_c),
                    '🚨손절가': stop_loss, '세력선괴리': whale_gap, 'RSI': round(curr_rsi, 1),
                    '차트': f"https://finance.naver.com/item/fchart.naver?code={ticker}"
                })
        except: continue
    return pd.DataFrame(final_results).sort_values('점수', ascending=False)

def send_email(df):
    if df.empty: 
        print("포착된 종목이 없습니다.")
        return
        
    html = f"""
    <html><body>
        <h2 style='color: #2c3e50;'>🏆 오늘의 세력 분석 리포트</h2>
        <table border='1' style='border-collapse: collapse;'>
            <tr style='background-color: #f2f2f2;'>
                <th>종목명</th><th>점수</th><th>상태</th><th>현재가</th><th>🚨손절가</th><th>괴리율</th><th>링크</th>
            </tr>
    """
    for _, row in df.iterrows():
        html += f"""
            <tr>
                <td>{row['종목명']}</td><td>{row['점수']}점</td><td>{row['상태']}</td>
                <td>{row['현재가']:,}원</td><td style='color:red;'>{row['🚨손절가']:,}원</td>
                <td>{row['세력선괴리']}%</td><td><a href='{row['차트']}'>차트보기</a></td>
            </tr>
        """
    html += "</table></body></html>"
    
    msg = MIMEMultipart()
    msg['Subject'] = f"📊 [VIP 전략] {datetime.now().strftime('%m/%d')} 포착 종목"
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_USER  # 본인(EMAIL_USER)에게 발송하도록 수정함
    msg.attach(MIMEText(html, 'html'))
    
    # --- [2. 메일 발송 실행] ---
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("✅ 메일 발송 성공!")
    except Exception as e:
        print(f"❌ 메일 발송 실패: {e}")
        raise e

# --- [3. 메인 실행 루틴] ---
if __name__ == "__main__":
    report_df = get_pro_whale_report()
    send_email(report_df)
