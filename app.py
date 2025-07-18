import os
import pdfplumber
import google.generativeai as genai
import yfinance as yf
import matplotlib.pyplot as plt
import io
import base64
import platform
import re
import numpy as np
import pandas as pd
from datetime import datetime
from pykrx import stock


# ✅ Gemini API configuration
genai.configure(api_key='AIzaSyA4vIEpJTIPtrzuC2JfRD-bM6_HbCOdE8k') # 여기에 실제 API 키 입력
model = genai.GenerativeModel("gemini-2.5-flash")

# ✅ Matplotlib 한글 폰트 설정 (그래프 라벨은 영어로 하므로, 폰트 깨짐 문제는 없을 것이나, 시스템 폰트 호환성 위함)
if platform.system() == 'Darwin': # Mac OS
    plt.rcParams['font.family'] = 'AppleGothic' # 한글 폰트 (UI는 한글, 그래프는 영어)
    plt.rcParams['axes.unicode_minus'] = False # 음수 부호 깨짐 방지
elif platform.system() == 'Windows': # Windows OS
    plt.rcParams['font.family'] = 'Malgun Gothic' # 한글 폰트 (UI는 한글, 그래프는 영어)
    plt.rcParams['axes.unicode_minus'] = False # 음수 부호 깨짐 방지
else: # Linux 등
    # 시스템에 나눔고딕 폰트 설치 필요 (예: sudo apt-get install fonts-nanum-extra)
    try:
        plt.rcParams['font.family'] = 'NanumGothic'
        plt.rcParams['axes.unicode_minus'] = False
    except:
        # Fallback to a generic font if NanumGothic is not found
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['axes.unicode_minus'] = False


####


# 기준 날짜 (평일)
date = "2024-12-30"

# KOSPI 상장 종목 티커 리스트
tickers = stock.get_market_ticker_list(date=date, market="KOSPI")

# 기업명 그대로 사용하는 딕셔너리 생성
COMPANY_INFO = {
    stock.get_market_ticker_name(ticker): {"ticker": f"{ticker}.KS"}
    for ticker in tickers
}



# ✅ PDF 첫 페이지에서 텍스트 추출
def extract_first_page_text(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) > 0:
                text = pdf.pages[0].extract_text()
                # Attempt to extract date from filename for better context
                # Example filename: '20231026_삼성전자_리포트.pdf' or '20240101_Report.pdf'
                filename = os.path.basename(pdf_path)
                date_match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
                report_date = date_match.group(0) if date_match else "N/A"
                
                # Prepend date to text for potential LLM context, but mainly for target price extraction
                return f"[{report_date}] {text.strip()}" if text else ""
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return ""
    return ""

# ✅ 주가 추세 그래프 생성 및 Base64 인코딩
def generate_stock_price_graph(ticker, period="5y"):
    try:
        stock_data = yf.download(ticker, period=period, progress=False)
        if stock_data.empty:
            return None, "❌ 해당 티커에 대한 주가 데이터를 찾을 수 없습니다."

        plt.style.use('seaborn-v0_8-darkgrid')
        plt.figure(figsize=(10, 6))
        plt.plot(stock_data['Close'], label='Close Price', color='skyblue', linewidth=2)
        plt.title(f'Stock Price Trend ({ticker})', fontsize=16, fontweight='bold')
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Close Price (KRW)', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend(fontsize=10)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)

        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return img_base64, None
    except Exception as e:
        return None, f"❌ 주가 그래프를 생성하는 중 오류가 발생했습니다: {e}"
def generate_target_price_data_and_graph(pdf_texts_list):
    extracted_data = []

    pattern_won = r'(?:목표주가|TP|적정주가|target price)[\s:]*([\d,]+)\s*(?:원|KRW)\b'
    pattern_man = r'(?:목표주가|TP|적정주가|target price)[\s:]*([\d,]+)\s*만(?:원)?\b'
    pattern_no_unit = r'(?:목표주가|TP|적정주가|target price)[\s:]*([\d,]+)\b(?!\s*(?:년|월|일|점|배|시|분|초|억|조))'
    all_patterns = [pattern_won, pattern_man, pattern_no_unit]

    for text_with_date in pdf_texts_list:
        date_match = re.match(r'\[(\d{8})\]', text_with_date)
        report_date = date_match.group(1) if date_match else "N/A"
        clean_text = re.sub(r'^\[\d{8}\]\s*', '', text_with_date)

        for pattern in all_patterns:
            for match in re.finditer(pattern, clean_text, re.IGNORECASE):
                try:
                    price = int(match.group(1).replace(',', ''))
                    if '만' in match.group(0): price *= 10000
                    if 1000 < price < 5_000_000:
                        extracted_data.append({'Date': report_date, 'Target Price (KRW)': price})
                        break
                except ValueError:
                    continue
            if extracted_data and extracted_data[-1]['Date'] == report_date:
                break

    if not extracted_data:
        return pd.DataFrame(columns=['Date', 'Target Price (KRW)']), None, "❌ 리포트에서 유효한 목표주가 데이터를 찾을 수 없습니다."

    df_target_prices = pd.DataFrame(extracted_data)
    df_target_prices['Date'] = pd.to_datetime(df_target_prices['Date'], format="%Y%m%d", errors='coerce')
    df_target_prices.sort_values(by='Date', inplace=True)
    df_target_prices.reset_index(drop=True, inplace=True)

    prices = df_target_prices['Target Price (KRW)']
    std_price = prices.std()
    if std_price > 0:
        z_scores = np.abs((prices - prices.mean()) / std_price)
        df_filtered = df_target_prices[z_scores < 3].copy()
    else:
        df_filtered = df_target_prices.copy()

    if df_filtered.empty:
        df_filtered = df_target_prices
        graph_error_message = "⚠️ 이상치 제거 후 목표주가 데이터가 모두 사라졌습니다. 원본 데이터를 사용합니다."
    else:
        graph_error_message = None

    try:
        plt.style.use('seaborn-v0_8-darkgrid')
        plt.figure(figsize=(12, 4))
        y_coords = np.random.normal(0, 0.15, size=len(df_filtered))
        plt.scatter(df_filtered['Target Price (KRW)'], y_coords,
                    s=100, alpha=0.7, edgecolors='w', linewidths=0.5, label='Target Price')
        plt.title('Stock Price Target Distribution', fontsize=16, fontweight='bold')
        plt.xlabel('Target Price (KRW)', fontsize=12)
        plt.ylabel('')
        plt.yticks([])

        min_p, max_p = df_filtered['Target Price (KRW)'].min(), df_filtered['Target Price (KRW)'].max()
        buffer = (max_p - min_p) * 0.1 if (max_p - min_p) > 0 else 10000
        plt.xlim(min_p - buffer, max_p + buffer)

        plt.legend(fontsize=10)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)

        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return df_filtered, img_base64, graph_error_message
    except Exception as e:
        return df_target_prices, None, f"❌ 목표주가 분포 그래프를 생성하는 중 오류가 발생했습니다: {e}"


# ✅ 메인 분석 함수
def run_analysis_from_user_input(user_input, base_path):
    company_name_kor = None
    user_query = None

    # Identify company name (Korean) from user input
    for name_kor in COMPANY_INFO.keys():
        if name_kor in user_input:
            company_name_kor = name_kor
            user_query_parts = user_input.replace(name_kor, "").strip()
            if "에 대한" in user_query_parts:
                user_query = user_query_parts.split("에 대한", 1)[1].strip()
            else:
                user_query = user_query_parts.strip()
            break

    if not company_name_kor:
        return {"error": "❌ 질문에서 분석할 기업을 찾을 수 없거나, 지원되지 않는 기업입니다. 예: '삼성전자에 대한 최근 투자 의견은 어때?'"}, None

    # 주가 그래프 생성
    ticker_symbol = COMPANY_INFO[company_name_kor]["ticker"]
    graph_base64 = None
    graph_error = None
    if ticker_symbol:
        graph_base64, graph_error = generate_stock_price_graph(ticker_symbol, period="5y")
    else:
        graph_error = f"❌ '{company_name_kor}'에 대한 티커 정보를 찾을 수 없습니다. 주가 그래프를 생성할 수 없습니다."

    # PDF 분석 로직
    pdf_analysis_result = ""
    df_target_prices_data = pd.DataFrame(columns=['Date', 'Target Price (KRW)'])
    target_price_graph_base64 = None
    target_price_graph_error = None

    company_path = os.path.join(base_path, company_name_kor)
    pdf_folder = os.path.join(company_path, "pdf")

    if not os.path.isdir(pdf_folder):
        pdf_analysis_result = f"❌ '{company_name_kor}' 폴더를 찾을 수 없습니다. PDF 분석을 수행할 수 없습니다."
    else:
        pdf_files = [os.path.join(pdf_folder, f) for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
        texts = [extract_first_page_text(path) for path in pdf_files if extract_first_page_text(path)]

        if not texts:
            pdf_analysis_result = f"❌ '{company_name_kor}'의 PDF에서 유효한 텍스트를 찾지 못했습니다. PDF 분석을 수행할 수 없습니다."
        else:
            combined_text = "\n\n".join(texts)
            df_target_prices_data, target_price_graph_base64, target_price_graph_error = generate_target_price_data_and_graph(texts)

            prompt = f"""
당신은 전문 금융 애널리스트 리포트 분석 AI입니다.

당신의 역할은 다음과 같습니다:
1. 사용자의 질문을 이해하고, 주어진 애널리스트 리포트 텍스트를 기반으로 **명확하고 구조화된 답변**을 생성합니다.
2. 리포트에서 언급된 **수치, 데이터, 추세, 문구** 등을 적극적으로 활용하여 **논리적이고 구체적인 설명**을 제공합니다.
3. 리포트의 **전체적인 톤(긍정/부정/혼재)을 파악**하여 분석에 반영하고, 필요시 **투자 의견 및 목표주가 관련 정보**도 포함합니다.
4. 응답은 **전문가적 문체**로 명확하고 간결하게 작성되어야 하며, 중복되거나 불확실한 표현은 피합니다.
5. 실제 보고서 기반임을 강조하며, 가능한 경우 **보고서 문장에서 발췌한 인용(“”)**을 포함해 주세요.

질문 예시:
- 삼성전자에 대한 최근 리포트의 투자 의견과 목표주가 변동은 어떤가요?
- NAVER의 리스크 요인은 어떤 것들이 언급되었나요?
- 현대차에 대한 긍정적 평가의 근거는 무엇인가요?

---

[사용자 질문]
{company_name_kor}에 대한 질문: "{user_query}"

[애널리스트 리포트 내용]
{combined_text}

---

🎯 **다음 섹션별로 답변을 구조화하여 제공해주세요.**

### 1. 주요 분석 요약
### 2. 세부 분석 (리포트 내용 기반)
### 3. 전반적 논조 및 투자 의견
### 4. 핵심 인용 구절
### 5. 결론 및 투자자 참고 사항
"""
            try:
                response = model.generate_content(prompt)
                pdf_analysis_result = response.text.strip()
            except Exception as e:
                pdf_analysis_result = f"❌ Gemini 오류: {e}"

    return {
        "pdf_analysis": pdf_analysis_result,
        "graph_image": graph_base64,
        "graph_error": graph_error,
        "target_price_graph_image": target_price_graph_base64,
        "target_price_graph_error": target_price_graph_error,
        "target_price_dataframe": df_target_prices_data
    }, None
