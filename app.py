import streamlit as st

# 타이틀
st.title("🧠 감정 분석기 (Demo)")

# 설명
st.markdown("텍스트를 입력하면, 감정 상태를 예측합니다.")

# 사용자 입력
user_input = st.text_area("✏️ 텍스트 입력", placeholder="예: 오늘 날씨가 정말 좋아요!")

# 감정 분석 (단순 예시)
def analyze_sentiment(text):
    if not text:
        return "입력 없음"
    elif "좋아" in text or "행복" in text:
        return "😊 긍정적"
    elif "싫어" in text or "짜증" in text:
        return "😡 부정적"
    else:
        return "😐 중립"

# 버튼 클릭 시 실행
if st.button("분석하기"):
    result = analyze_sentiment(user_input)
    st.success(f"분석 결과: {result}")
