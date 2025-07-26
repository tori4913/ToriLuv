import os
import google.generativeai as genai
import yfinance as yf
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import platform
import pandas as pd
from datetime import datetime
from pykrx import stock

# ✅ Gemini API configuration
file_path = 'api_key.txt'  # API 키가 저장된 텍스트 파일 경로

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        API_KEY = f.read().strip()
    print("✅ API_KEY가 성공적으로 불러와졌습니다.")
except FileNotFoundError:
    API_KEY = None
    print(f"❌ 오류: '{file_path}' 파일을 찾을 수 없습니다.")
except Exception as e:
    API_KEY = None
    print(f"❌ 파일을 읽는 중 오류 발생: {e}")

if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
else:
    model = None
    print("❌ 유효한 API_KEY가 없으므로 Gemini 모델이 설정되지 않았습니다!!!!!!!")

# ✅ Matplotlib 한글 폰트 설정
if platform.system() == 'Darwin':
    plt.rcParams['font.family'] = 'AppleGothic'
elif platform.system() == 'Windows':
    plt.rcParams['font.family'] = 'Malgun Gothic'
else:
    try:
        plt.rcParams['font.family'] = 'NanumGothic'
    except:
        plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

# ✅ Company Info from pykrx
TODAY = datetime.today().strftime("%Y%m%d")
tickers = stock.get_market_ticker_list(date=TODAY, market="KOSPI")
COMPANY_INFO = {
    stock.get_market_ticker_name(ticker): {"ticker": f"{ticker}.KS"} for ticker in tickers
}

# ✅ 주가 그래프 생성 함수
def generate_stock_price_graph(ticker, company_name_eng, period="5y"):
    try:
        stock_data = yf.download(ticker, period=period, progress=False)
        if stock_data.empty:
            return None, "❌ 해당 티커에 대한 주가 데이터를 찾을 수 없습니다."

        plt.style.use('seaborn-v0_8-darkgrid')
        plt.figure(figsize=(10, 6))
        plt.plot(stock_data['Close'], label='Close Price', color='skyblue', linewidth=2)
        plt.title(f'{company_name_eng} ({ticker}) Stock Price Trend over {period}', fontsize=16, fontweight='bold')
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
        return None, f"❌ 주가 그래프 생성 오류: {e}"

# ✅ 가격 분포 그래프 + 데이터프레임 반환 함수
def generate_price_distribution_data_and_plot(base_path, company_name_kor):
    excel_path = os.path.join(base_path, company_name_kor, f"{company_name_kor}_report_text.xlsx")
    if not os.path.exists(excel_path):
        return None, None, f"❌ 엑셀 파일({excel_path})을 찾을 수 없습니다."

    try:
        df = pd.read_excel(excel_path)
        if not {'kapital', 'price'}.issubset(df.columns):
            return None, None, "❌ 'kapital' 또는 'price' 컬럼이 존재하지 않습니다."

        df_result = df[['kapital', 'price']].copy()

        plt.figure(figsize=(10, 6))
        sns.swarmplot(y=df['price'], alpha=0.7)
        plt.title('Price Distribution (Swarm Plot)')
        plt.ylabel('Price')
        plt.grid(True, axis='y', linestyle='--', alpha=0.7)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)

        img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return df_result, img_base64, None
    except Exception as e:
        return None, None, f"❌ 가격 분포 그래프 생성 오류: {e}"

# ✅ 전체 분석 실행 함수
def run_analysis_from_user_input(user_input, base_path):
    if not model:
        return {"error": "❌ Gemini 모델이 설정되지 않았습니다. API_KEY를 확인하세요!!"}, None

    company_name_kor = next((name for name in COMPANY_INFO if name in user_input), None)
    if not company_name_kor:
        return {"error": "❌ 질문에서 분석할 기업명을 찾을 수 없습니다."}, None

    company_path = os.path.join(base_path, company_name_kor)
    summary_path = os.path.join(company_path, f"{company_name_kor}_summary.txt")

    if not os.path.exists(summary_path):
        return {"error": f"❌ 요약 파일({company_name_kor}_summary.txt)을 찾을 수 없습니다."}, None

    with open(summary_path, "r", encoding="utf-8") as f:
        summary_text = f.read()

    ticker_symbol = COMPANY_INFO[company_name_kor]["ticker"]
    graph_base64, graph_error = generate_stock_price_graph(ticker_symbol, company_name_kor)
    df_target_prices, dist_graph_base64, dist_graph_error = generate_price_distribution_data_and_plot(base_path, company_name_kor)

    prompt = f"""
당신은 전문 금융 애널리스트 리포트 분석 AI입니다.

[사용자 질문]
{user_input}

[애널리스트 리포트 요약 내용]
{summary_text}

---
🎯 다음 항목을 순서대로 포함해 답변해 주세요.
1. 주요 분석 요약
2. 세부 분석 (요약 내용 기반)
3. 전반적 논조 및 투자 의견
4. 핵심 인용 구절
5. 결론 및 투자자 참고 사항
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
        "target_price_graph_image": dist_graph_base64,
        "target_price_graph_error": dist_graph_error,
        "target_price_dataframe": df_target_prices
    }, None
