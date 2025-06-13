import streamlit as st
import pandas as pd
import plotly.express as px

# 페이지 레이아웃을 넓게 사용하도록 설정
st.set_page_config(layout="wide")

# --- 데이터 로딩 (캐싱 사용) ---
@st.cache_data
def load_data():
    """점포, 유동인구, 매출 데이터를 로드하고 커피 업종만 필터링합니다."""
    try:
        store_df = pd.read_csv('서울시 상권분석서비스(점포-행정동).csv', encoding='euc-kr')
        pop_df = pd.read_csv('서울시 상권분석서비스(길단위인구-행정동).csv', encoding='euc-kr')
        sales_df = pd.read_csv('서울시 상권분석서비스(추정매출-행정동).csv', encoding='euc-kr')
    except FileNotFoundError as e:
        st.error(f"데이터 파일을 찾을 수 없습니다: {e.filename}. 모든 CSV 파일이 올바른 위치에 있는지 확인해주세요.")
        return None, None, None
    
    coffee_store_df = store_df[store_df["서비스_업종_코드_명"] == "커피-음료"]
    coffee_sales_df = sales_df[sales_df["서비스_업종_코드_명"] == "커피-음료"]
    
    return coffee_store_df, pop_df, coffee_sales_df

coffee_df, pop_df, sales_df = load_data()

if coffee_df is None or pop_df is None or sales_df is None:
    st.stop()

# --- 데이터 전처리 ---
pop_agg_df = pop_df.groupby(['기준_년분기_코드', '행정동_코드', '행정동_코드_명'])['총_유동인구_수'].sum().reset_index()

# --- 사이드바 ---
st.sidebar.title("🔍 분석 조건 설정")

def format_quarter(quarter_code):
    year, quarter = str(quarter_code)[:4], str(quarter_code)[-1]
    return f"{year}년 {quarter}분기"

available_quarters = sorted(coffee_df['기준_년분기_코드'].unique(), reverse=True)
selected_quarter = st.sidebar.selectbox("분기를 선택하세요", available_quarters, format_func=format_quarter)

# --- 분기별 데이터 필터링 및 병합 ---
merge_keys = ['행정동_코드', '행정동_코드_명']
coffee_quarter_df = coffee_df[coffee_df['기준_년분기_코드'] == selected_quarter]
pop_agg_quarter_df = pop_agg_df[pop_agg_df['기준_년분기_코드'] == selected_quarter]
sales_quarter_df = sales_df[sales_df['기준_년분기_코드'] == selected_quarter]
pop_quarter_df = pop_df[pop_df['기준_년분기_코드'] == selected_quarter]

merged_df = pd.merge(coffee_quarter_df, pop_agg_quarter_df, on=merge_keys, how='inner')
merged_df = pd.merge(merged_df, sales_quarter_df, on=merge_keys, how='inner')

# --- 행정동 검색 기능 ---
st.sidebar.divider()
full_dong_list = sorted(merged_df['행정동_코드_명'].unique())

search_term = st.sidebar.text_input("행정동 검색", placeholder="예: 역삼, 신사, 명동")

if search_term:
    filtered_dong_list = [dong for dong in full_dong_list if search_term in dong]
else:
    filtered_dong_list = full_dong_list

display_list = ["전체"] + filtered_dong_list
selected_dong = st.sidebar.selectbox(
    "행정동을 선택하세요", 
    display_list,
    help="찾고 싶은 동 이름을 위 검색창에 입력하면 목록이 줄어듭니다."
)

# --- UI 분기: 전체 vs 상세 ---
if selected_dong == "전체":
    st.title("☕ 커피-음료 업종 전체 동향 분석")
    st.subheader(f"📈 전체 행정동 비교 분석 (기준: {format_quarter(selected_quarter)})")
    
    # --- 좌표 데이터 불러오기 ---
    coord_df = pd.read_excel("/mnt/data/행정구역별_위경도_좌표.xlsx")
    coord_df = coord_df[['행정동_코드_명', 'lat', 'lon']]

    # merged_df에 좌표 붙이기
    merged_df = pd.merge(merged_df, coord_df, on='행정동_코드_명', how='left')

    # --- 점포당 매출액 계산 (지도 시각화 전에 필수!) ---
    merged_df['점포당_매출액'] = merged_df['당월_매출_금액'] / merged_df['점포_수'].replace(0, 1)

    # 지도 시각화용 데이터 만들기
    map_df = merged_df.dropna(subset=['lat', 'lon'])

    # --- 지도 시각화 ---
    st.subheader("🗺️ 행정동별 커피 업종 매출 지도")

    fig = px.scatter_mapbox(
        map_df,
        lat="lat",
        lon="lon",
        size="당월_매출_금액",  # 버블 크기
        color="점포당_매출액",  # 색상
        color_continuous_scale="Viridis",
        size_max=30,
        zoom=10,
        mapbox_style="carto-positron",
        hover_name="행정동_코드_명",
        hover_data={
            "점포_수": True,
            "당월_매출_금액": True,
            "점포당_매출액": True,
            "lat": False,
            "lon": False
        },
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- 종합 비교 및 순위 비교 ---
    if not merged_df.empty:
        tab1, tab2 = st.tabs(["📊 종합 비교", "🏆 순위 비교"])

        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("점포 수 vs 유동인구")
                fig = px.scatter(
                    merged_df, x="총_유동인구_수", y="점포_수", 
                    hover_name="행정동_코드_명", size='점포_수', color='점포_수'
                )
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.subheader("점포 수 vs 매출액")
                fig = px.scatter(
                    merged_df, x="점포_수", y="당월_매출_금액", 
                    hover_name="행정동_코드_명", size='당월_매출_금액', color='점포당_매출액',
                    color_continuous_scale='Plasma', labels={"점포당_매출액": "점포당매출액"},
                    hover_data={'점포당_매출액': ':,.0f'}
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.subheader("점포 수 상위")
                df_sorted = merged_df.sort_values("점포_수", ascending=False).head(15)
                st.dataframe(df_sorted[['행정동_코드_명', '점포_수']], use_container_width=True)
            with col2:
                st.subheader("매출액 상위")
                df_sorted = merged_df.sort_values("당월_매출_금액", ascending=False).head(15)
                st.dataframe(df_sorted[['행정동_코드_명', '당월_매출_금액']], use_container_width=True)
            with col3:
                st.subheader("점포당 매출액 상위")
                df_sorted = merged_df.sort_values("점포당_매출액", ascending=False).head(15)
                st.dataframe(df_sorted[['행정동_코드_명', '점포당_매출액']], use_container_width=True)
    else:
        st.warning("선택하신 분기에 해당하는 데이터가 없습니다.")

else:
    # --- 특정 행정동 상세 분석 화면 ---
    st.title(f"🔍 {selected_dong} 상세 분석")
    st.subheader(f"(기준: {format_quarter(selected_quarter)})")
    
    dong_data = merged_df[merged_df['행정동_코드_명'] == selected_dong].iloc[0]
    dong_pop_data = pop_quarter_df[pop_quarter_df['행정동_코드_명'] == selected_dong]

    st.subheader("⭐ 주요 지표")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("☕ 점포 수", f"{int(dong_data['점포_수'])}개")
    col2.metric("🚶 총 유동인구", f"{int(dong_data['총_유동인구_수']):,}명")
    col3.metric("💰 총 매출액", f"{dong_data['당월_매출_금액']:,.0f} 원")
    sales_per_store = dong_data['당월_매출_금액'] / dong_data['점포_수'] if dong_data['점포_수'] > 0 else 0
    col4.metric("🏪 점포당 매출액", f"{sales_per_store:,.0f} 원")
    st.divider()

    st.subheader("📊 유동인구 vs 매출 비교 분석")
    tab_age, tab_gender, tab_time, tab_day = st.tabs(["연령대별", "성별", "시간대별", "요일별"])
    
    def get_grouped_data(prefix, pop_cols, sales_cols):
        pop_data = dong_pop_data[list(pop_cols.keys())].sum().rename(index=
