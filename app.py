import streamlit as st
from Backend import run_analysis_from_user_input
import os

# ✅ app.py 또는 Backend.py 기준의 현재 디렉토리를 기준으로 경로 설정
BASE_PATH = os.path.dirname(os.path.abspath(__file__))  # 현재 파일 기준 절대경로

# 이후에 Backend에서 os.path.join(BASE_PATH, 기업명, 파일명)으로 접근 가능


# ✅ 페이지 구성
st.set_page_config(page_title="기업 리포트 분석 AI", layout="wide")
st.markdown("## 📊 AI 기반 기업 리포트 분석 서비스")
st.caption("금융 애널리스트 리포트와 주가 추이를 기반으로 기업 관련 질문에 대해 LLM이 답변합니다.")

# ✅ 사용자 입력 UI
example_questions = [
    "삼성전자에 대한 최근 투자 의견은?",
    "네이버에 대한 리스크 요인은?",
    "카카오의 목표주가 분포는 어떻게 돼?",
    "LG에너지솔루션에 대한 리포트 분위기는 어때?",
    "현대차의 5년 주가 추이는 어때?",
    "삼성전자의 5년 주가와 리포트 분석 해줘",
    "삼성전자 목표주가 분포는 어때?"
]

col1, col2 = st.columns([3, 1])
with col1:
    user_input = st.text_input("❓ 기업 질문 입력", placeholder="예: 삼성전자에 대한 최근 전망은?")
with col2:
    selected_example = st.selectbox("📌 예시 질문", [""] + example_questions)
    if selected_example and not user_input:
        user_input = selected_example

# ✅ 실행 버튼
if st.button("🔍 분석 실행"):
    if user_input.strip() == "":
        st.warning("⛔ 질문을 입력하거나 예시를 선택해 주세요.")
    else:
        with st.spinner("📚 애널리스트 리포트 및 주가 데이터를 분석 중입니다..."):
            result, _ = run_analysis_from_user_input(user_input, BASE_PATH)

        if result.get("error"):
            st.error(result["error"])
        else:
            st.success("✅ 분석 완료!")

            st.markdown("### 📊 시각화 분석")
            graph_col1, graph_col2 = st.columns(2)

            with graph_col1:
                st.subheader("📈 Stock Price Trend")
                if result.get("graph_image"):
                    st.image(f"data:image/png;base64,{result['graph_image']}", caption="Past 5 Years Stock Price Trend")
                elif result.get("graph_error"):
                    st.warning(result["graph_error"])
                else:
                    st.info("Stock price graph cannot be generated.")

            with graph_col2:
                st.subheader("🎯 Target Price Distribution")
                if result.get("target_price_graph_image"):
                    st.image(f"data:image/png;base64,{result['target_price_graph_image']}", caption="Analyst Target Price Distribution")
                elif result.get("target_price_graph_error"):
                    st.warning(result["target_price_graph_error"])
                else:
                    st.info("Target price data not found.")

            st.markdown("---")
            st.markdown("### 📋 추출된 목표주가 데이터")
            df_target_prices = result.get("target_price_dataframe")
            if df_target_prices is not None and not df_target_prices.empty:
                st.dataframe(df_target_prices, hide_index=True)
            else:
                st.info("리포트에서 상세 목표주가 데이터를 추출할 수 없었습니다.")

            st.markdown("---")
            st.markdown("### 📝 리포트 분석 결과")
            st.markdown(result["pdf_analysis"])
