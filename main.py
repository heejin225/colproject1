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


# --- [개선된 부분] 행정동 검색 기능 ---
st.sidebar.divider()
full_dong_list = sorted(merged_df['행정동_코드_명'].unique())

# 1. 텍스트 입력으로 검색어 받기
search_term = st.sidebar.text_input("행정동 검색", placeholder="예: 역삼, 신사, 명동")

# 2. 검색어로 목록 필터링
if search_term:
    filtered_dong_list = [dong for dong in full_dong_list if search_term in dong]
else:
    filtered_dong_list = full_dong_list

# 3. 필터링된 목록을 Selectbox에 표시 (항상 '전체' 옵션 포함)
display_list = ["전체"] + filtered_dong_list
selected_dong = st.sidebar.selectbox(
    "행정동을 선택하세요", 
    display_list,
    help="찾고 싶은 동 이름을 위 검색창에 입력하면 목록이 줄어듭니다."
)
# --- 행정동 검색 기능 끝 ---


# --- UI 분기: 전체 vs 상세 ---
if selected_dong == "전체":
    # --- [NEW] 좌표 데이터 불러오기 ---
coord_df = pd.read_excel("/mnt/data/행정구역별_위경도_좌표.xlsx")
coord_df = coord_df[['행정동_코드_명', 'lat', 'lon']]

# merged_df에 좌표 붙이기
merged_df = pd.merge(merged_df, coord_df, on='행정동_코드_명', how='left')

# 지도 시각화용 데이터 만들기
map_df = merged_df.dropna(subset=['lat', 'lon'])

# --- [NEW] 지도 시각화 ---
import plotly.express as px

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

    st.title("☕ 커피-음료 업종 전체 동향 분석")
    st.subheader(f"📈 전체 행정동 비교 분석 (기준: {format_quarter(selected_quarter)})")
    
    if not merged_df.empty:
        merged_df['점포당_매출액'] = merged_df['당월_매출_금액'] / merged_df['점포_수'].replace(0, 1)
        
        tab1, tab2 = st.tabs(["📊 종합 비교", "🏆 순위 비교"])
        with tab1:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("점포 수 vs 유동인구")
                fig = px.scatter(merged_df, x="총_유동인구_수", y="점포_수", hover_name="행정동_코드_명", size='점포_수', color='점포_수')
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.subheader("점포 수 vs 매출액")
                fig = px.scatter(merged_df, x="점포_수", y="당월_매출_금액", hover_name="행정동_코드_명", size='당월_매출_금액', color='점포당_매출액',
                                 color_continuous_scale='Plasma', labels={"점포당_매출액": "점포당매출액"},
                                 hover_data={'점포당_매출액': ':,.0f'})
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
    # --- 2. 특정 행정동 상세 분석 화면 ---
    st.title(f"🔍 {selected_dong} 상세 분석")
    st.subheader(f"(기준: {format_quarter(selected_quarter)})")
    
    # (이하 상세 분석 코드는 이전과 동일)
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
        pop_data = dong_pop_data[list(pop_cols.keys())].sum().rename(index=pop_cols)
        sales_data = dong_data[list(sales_cols.keys())].rename(index=sales_cols)
        pop_df = pop_data.reset_index(name='유동인구').rename(columns={'index': prefix})
        sales_df = sales_data.reset_index(name='매출액').rename(columns={'index': prefix})
        return pop_df, sales_df
    
    with tab_age:
        pop_cols = {'연령대_10_유동인구_수':'10대', '연령대_20_유동인구_수':'20대', '연령대_30_유동인구_수':'30대', '연령대_40_유동인구_수':'40대', '연령대_50_유동인구_수':'50대', '연령대_60_이상_유동인구_수':'60대+'}
        sales_cols = {'연령대_10_매출_금액':'10대', '연령대_20_매출_금액':'20대', '연령대_30_매출_금액':'30대', '연령대_40_매출_금액':'40대', '연령대_50_매출_금액':'50대', '연령대_60_이상_매출_금액':'60대+'}
        pop_res, sales_res = get_grouped_data('연령대', pop_cols, sales_cols)
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(pop_res, x='연령대', y='유동인구', title='연령대별 유동인구'), use_container_width=True)
        c2.plotly_chart(px.bar(sales_res, x='연령대', y='매출액', title='연령대별 매출액'), use_container_width=True)

    with tab_gender:
        pop_cols = {'남성_유동인구_수': '남성', '여성_유동인구_수': '여성'}
        sales_cols = {'남성_매출_금액': '남성', '여성_매출_금액': '여성'}
        pop_res, sales_res = get_grouped_data('성별', pop_cols, sales_cols)
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.pie(pop_res, names='성별', values='유동인구', title='성별 유동인구', hole=0.4), use_container_width=True)
        c2.plotly_chart(px.pie(sales_res, names='성별', values='매출액', title='성별 매출액', hole=0.4), use_container_width=True)

    with tab_time:
        pop_cols = {'시간대_00_06_유동인구_수':'00-06시', '시간대_06_11_유동인구_수':'06-11시', '시간대_11_14_유동인구_수':'11-14시', '시간대_14_17_유동인구_수':'14-17시', '시간대_17_21_유동인구_수':'17-21시', '시간대_21_24_유동인구_수':'21-24시'}
        sales_cols = {'시간대_00~06_매출_금액':'00-06시', '시간대_06~11_매출_금액':'06-11시', '시간대_11~14_매출_금액':'11-14시', '시간대_14~17_매출_금액':'14-17시', '시간대_17~21_매출_금액':'17-21시', '시간대_21~24_매출_금액':'21-24시'}
        pop_res, sales_res = get_grouped_data('시간대', pop_cols, sales_cols)
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(pop_res, x='시간대', y='유동인구', title='시간대별 유동인구'), use_container_width=True)
        c2.plotly_chart(px.bar(sales_res, x='시간대', y='매출액', title='시간대별 매출액'), use_container_width=True)

    with tab_day:
        pop_cols = {'월요일_유동인구_수':'월', '화요일_유동인구_수':'화', '수요일_유동인구_수':'수', '목요일_유동인구_수':'목', '금요일_유동인구_수':'금', '토요일_유동인구_수':'토', '일요일_유동인구_수':'일'}
        sales_cols = {'월요일_매출_금액':'월', '화요일_매출_금액':'화', '수요일_매출_금액':'수', '목요일_매출_금액':'목', '금요일_매출_금액':'금', '토요일_매출_금액':'토', '일요일_매출_금액':'일'}
        pop_res, sales_res = get_grouped_data('요일', pop_cols, sales_cols)
        day_order = ['월', '화', '수', '목', '금', '토', '일']
        for df in [pop_res, sales_res]:
            df['요일'] = pd.Categorical(df['요일'], categories=day_order, ordered=True)
            df.sort_values('요일', inplace=True)
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.bar(pop_res, x='요일', y='유동인구', title='요일별 유동인구'), use_container_width=True)
        c2.plotly_chart(px.bar(sales_res, x='요일', y='매출액', title='요일별 매출액'), use_container_width=True)
