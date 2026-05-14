"""
Streamlit 메인 앱 파일
한국은행 선행지수 순환변동치 + 달러인덱스 대시보드
260514.1458
"""
import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
from datetime import datetime, date
from data_fetcher import get_combined_data, get_kospi

# 로컬: .env 파일에서 로드
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Streamlit Cloud: st.secrets에서 환경변수로 주입
try:
    if "ECOS_API_KEY" in st.secrets:
        os.environ["ECOS_API_KEY"] = st.secrets["ECOS_API_KEY"]
except Exception:
    pass

def main():
    st.set_page_config(page_title="경제 지표 대시보드", layout="wide")

    if not os.environ.get("ECOS_API_KEY"):
        st.error("⚠️ 한국은행 ECOS API 키가 설정되지 않았습니다.")
        st.info("로컬: `.env` 파일에 `ECOS_API_KEY=...` 입력\nStreamlit Cloud: 앱 설정 > Secrets에 입력")
        st.stop()
        
    st.title("한국은행 선행지수 순환변동치 & 달러인덱스 대시보드")
    
    # 1. 사이드바 설정 (기간 선택 등)
    if "start_date" not in st.session_state:
        st.session_state["start_date"] = date(2000, 1, 1)
    if "end_date" not in st.session_state:
        st.session_state["end_date"] = datetime.now().date()

    def set_preset(months=0, years=0, all_time=False):
        end_d = datetime.now().date()
        if all_time:
            start_d = date(2000, 1, 1)
        else:
            start_d = (pd.to_datetime(end_d) - pd.DateOffset(months=months, years=years)).date()
        st.session_state["start_date"] = start_d
        st.session_state["end_date"] = end_d

    with st.sidebar:
        st.title("🔍 기간 설정")
        
        st.write("프리셋")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("3개월"): set_preset(months=3)
            if st.button("3년"): set_preset(years=3)
        with col2:
            if st.button("6개월"): set_preset(months=6)
            if st.button("5년"): set_preset(years=5)
        with col3:
            if st.button("1년"): set_preset(years=1)
            if st.button("전체"): set_preset(all_time=True)
            
        st.markdown("---")
        
        start_date_input = st.date_input("시작일", value=st.session_state["start_date"])
        end_date_input = st.date_input("종료일", value=st.session_state["end_date"])
        
        if st.button("📊 조회하기"):
            if start_date_input > end_date_input:
                st.error("시작일은 종료일보다 이전이어야 합니다.")
            else:
                st.session_state["start_date"] = start_date_input
                st.session_state["end_date"] = end_date_input

        if st.button("🔄 캐시 초기화"):
            st.cache_data.clear()
            st.success("캐시가 초기화되었습니다.")

    # 2 & 3. 데이터 수집 및 병합
    start_str = st.session_state["start_date"].strftime("%Y%m")
    end_str = st.session_state["end_date"].strftime("%Y%m")
    
    with st.spinner("데이터를 불러오는 중입니다..."):
        try:
            df = get_combined_data(start_str, end_str)
        except Exception as e:
            st.error(f"데이터 로드 실패: {e}")
            return

    if df.empty:
        st.warning("⚠️ 선택하신 기간에 해당하는 데이터가 없습니다.")
        return

    # 최신 데이터 추출 (마지막 유효한 데이터 기준)
    df_valid = df.dropna(subset=['value', 'dollar_index'])
    if df_valid.empty:
        df_valid = df
        
    latest_row = df_valid.iloc[-1]
    prev_row = df_valid.iloc[-2] if len(df_valid) >= 2 else latest_row
    
    lead_latest = latest_row['value']
    lead_prev = prev_row['value']
    lead_diff = lead_latest - lead_prev
    
    dollar_latest = latest_row['dollar_index']
    dollar_prev = prev_row['dollar_index']
    dollar_diff = dollar_latest - dollar_prev
    
    ref_date = latest_row['date'].strftime("%Y-%m")
    
    # 4. 상단 메트릭 카드 3개
    st.subheader("주요 지표 요약")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="선행지수 순환변동치", value=f"{lead_latest:.2f}", delta=f"{lead_diff:.2f}")
    with col2:
        st.metric(label="달러 인덱스", value=f"{dollar_latest:.2f}", delta=f"{dollar_diff:.2f}")
    with col3:
        st.metric(label="데이터 기준일", value=ref_date, delta=None)
        
    st.markdown("---")
    
    # 5. 메인 차트 (Plotly make_subplots)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 왼쪽 Y축: 선행지수 순환변동치 (파란 실선)
    fig.add_trace(
        go.Scatter(
            x=df['date'], 
            y=df['value'], 
            name="선행지수 순환변동치", 
            line=dict(color="blue", width=2),
            mode="lines"
        ),
        secondary_y=False,
    )
    
    # 오른쪽 Y축: 달러인덱스 (빨간 점선)
    fig.add_trace(
        go.Scatter(
            x=df['date'], 
            y=df['dollar_index'], 
            name="달러인덱스", 
            line=dict(color="red", width=2, dash="dash"),
            mode="lines"
        ),
        secondary_y=True,
    )
    
    # 선행지수 100 기준 수평 점선 추가
    fig.add_hline(
        y=100, 
        line_dash="dot", 
        line_color="gray", 
        annotation_text="선행지수 기준선 (100)", 
        secondary_y=False
    )
    
    # 레이아웃 설정 (plotly_white 템플릿, hover 툴팁)
    fig.update_layout(
        title="선행지수 순환변동치 및 달러인덱스 추이",
        template="plotly_white",
        hovermode="x unified",
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=1.02, 
            xanchor="right", 
            x=1
        ),
        height=600
    )
    
    # Y축 타이틀 설정
    fig.update_yaxes(title_text="선행지수 순환변동치 (pt)", secondary_y=False)
    fig.update_yaxes(title_text="달러인덱스 (pt)", secondary_y=True)
    
    st.plotly_chart(fig, use_container_width=True)

    # 6. 코스피 지수 차트
    st.markdown("---")
    st.subheader("코스피 지수 (KOSPI)")

    with st.spinner("코스피 데이터를 불러오는 중..."):
        df_kospi = get_kospi(start_str, end_str)

    if not df_kospi.empty:
        # 코스피 메트릭
        kospi_valid = df_kospi.dropna(subset=['kospi'])
        if len(kospi_valid) >= 2:
            kospi_latest = kospi_valid.iloc[-1]['kospi']
            kospi_prev   = kospi_valid.iloc[-2]['kospi']
            kospi_diff   = kospi_latest - kospi_prev
            kospi_date   = kospi_valid.iloc[-1]['date'].strftime("%Y-%m")
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="코스피 지수", value=f"{kospi_latest:,.2f}", delta=f"{kospi_diff:,.2f}")
            with col2:
                st.metric(label="데이터 기준일", value=kospi_date)

        fig_kospi = go.Figure()
        fig_kospi.add_trace(
            go.Scatter(
                x=df_kospi['date'],
                y=df_kospi['kospi'],
                name="코스피",
                line=dict(color="#e377c2", width=2),
                fill='tozeroy',
                fillcolor='rgba(227,119,194,0.08)',
                mode="lines",
            )
        )
        fig_kospi.update_layout(
            title="코스피 지수 추이",
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=400,
        )
        fig_kospi.update_yaxes(title_text="코스피 (pt)")
        st.plotly_chart(fig_kospi, use_container_width=True)
    else:
        st.warning("코스피 데이터를 불러오지 못했습니다.")

    # 7. 상관관계 분석
    st.markdown("---")
    st.subheader("선행지수 순환변동치 ↔ 코스피 상관관계 분석")

    df_corr_base = pd.merge(
        df[['date', 'value']].dropna(),
        df_kospi[['date', 'kospi']].dropna(),
        on='date', how='inner'
    ).sort_values('date').reset_index(drop=True)

    if len(df_corr_base) < 10:
        st.warning("상관관계 분석을 위한 데이터가 부족합니다. 기간을 늘려주세요.")
    else:
        from scipy import stats

        r_sync, p_sync = stats.pearsonr(df_corr_base['value'], df_corr_base['kospi'])

        # 시차별 상관계수: 선행지수 t → 코스피 t+lag
        lag_results = []
        for lag in range(0, 13):
            kospi_future = df_corr_base['kospi'].shift(-lag)
            valid = df_corr_base['value'][kospi_future.notna()]
            kospi_v = kospi_future[kospi_future.notna()]
            if len(valid) >= 5:
                r_l, p_l = stats.pearsonr(valid, kospi_v)
                lag_results.append({'시차(개월)': lag, '상관계수(r)': round(r_l, 4), 'p-value': round(p_l, 4)})

        df_lag = pd.DataFrame(lag_results)
        best_lag = int(df_lag.loc[df_lag['상관계수(r)'].abs().idxmax(), '시차(개월)'])
        best_r   = float(df_lag.loc[df_lag['상관계수(r)'].abs().idxmax(), '상관계수(r)'])

        # 요약 메트릭
        col1, col2, col3 = st.columns(3)
        with col1:
            direction = "양(+)" if r_sync > 0 else "음(-)"
            st.metric("동시 상관계수 (r)", f"{r_sync:.4f}",
                      delta=f"p={p_sync:.4f}" if p_sync >= 0.001 else "p<0.001")
            st.caption(f"{direction} 상관관계")
        with col2:
            st.metric("최적 선행 시차", f"{best_lag}개월",
                      delta=f"r={best_r:.4f}")
            st.caption("선행지수가 코스피를 가장 잘 예측하는 시차")
        with col3:
            st.metric("분석 기간 데이터", f"{len(df_corr_base)}개월")
            st.caption(f"{df_corr_base['date'].min().strftime('%Y-%m')} ~ {df_corr_base['date'].max().strftime('%Y-%m')}")

        st.markdown("<br>", unsafe_allow_html=True)

        col_left, col_right = st.columns([1, 1])

        # 시차별 상관계수 막대 차트
        with col_left:
            st.markdown("**시차별 상관계수** (선행지수 → N개월 후 코스피)")
            colors = ['#1f77b4' if i == best_lag else
                      ('#2ca02c' if v > 0 else '#d62728')
                      for i, v in zip(df_lag['시차(개월)'], df_lag['상관계수(r)'])]
            fig_lag = go.Figure(go.Bar(
                x=df_lag['시차(개월)'],
                y=df_lag['상관계수(r)'],
                marker_color=colors,
                text=df_lag['상관계수(r)'].apply(lambda x: f"{x:.3f}"),
                textposition='outside',
            ))
            fig_lag.update_layout(
                template="plotly_white",
                height=350,
                xaxis_title="선행 시차 (개월)",
                yaxis_title="상관계수 (r)",
                yaxis=dict(range=[-1, 1]),
                showlegend=False,
            )
            fig_lag.add_hline(y=0, line_color="gray", line_width=1)
            st.plotly_chart(fig_lag, use_container_width=True)

        # 산점도
        with col_right:
            st.markdown(f"**산점도** (선행지수 vs {best_lag}개월 후 코스피)")
            kospi_shifted = df_corr_base['kospi'].shift(-best_lag)
            mask = kospi_shifted.notna()
            x_scatter = df_corr_base['value'][mask]
            y_scatter = kospi_shifted[mask]
            slope, intercept, *_ = stats.linregress(x_scatter, y_scatter)
            x_line = pd.Series([x_scatter.min(), x_scatter.max()])
            y_line = slope * x_line + intercept

            fig_scatter = go.Figure()
            fig_scatter.add_trace(go.Scatter(
                x=x_scatter, y=y_scatter,
                mode='markers',
                marker=dict(color='#1f77b4', opacity=0.5, size=6),
                name='데이터',
                hovertemplate="선행지수: %{x:.2f}<br>코스피: %{y:,.0f}<extra></extra>",
            ))
            fig_scatter.add_trace(go.Scatter(
                x=x_line, y=y_line,
                mode='lines',
                line=dict(color='#d62728', width=2, dash='dash'),
                name='추세선',
            ))
            fig_scatter.update_layout(
                template="plotly_white",
                height=350,
                xaxis_title="선행지수 순환변동치",
                yaxis_title=f"코스피 ({best_lag}개월 후)",
                showlegend=False,
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        # 롤링 12개월 상관계수 추이
        st.markdown("**롤링 12개월 상관계수 추이**")
        rolling_corr = (
            df_corr_base.set_index('date')['value']
            .rolling(12)
            .corr(df_corr_base.set_index('date')['kospi'])
            .reset_index()
        )
        rolling_corr.columns = ['date', 'rolling_r']
        fig_roll = go.Figure()
        fig_roll.add_hrect(y0=0.7, y1=1.0, fillcolor="rgba(44,160,44,0.07)", line_width=0, annotation_text="강한 양의 상관", annotation_position="top left")
        fig_roll.add_hrect(y0=-1.0, y1=-0.7, fillcolor="rgba(214,39,40,0.07)", line_width=0, annotation_text="강한 음의 상관", annotation_position="bottom left")
        fig_roll.add_trace(go.Scatter(
            x=rolling_corr['date'],
            y=rolling_corr['rolling_r'],
            mode='lines',
            line=dict(color='#ff7f0e', width=2),
            fill='tozeroy',
            fillcolor='rgba(255,127,14,0.08)',
            name='롤링 상관계수',
        ))
        fig_roll.add_hline(y=0, line_color="gray", line_width=1, line_dash="dot")
        fig_roll.update_layout(
            template="plotly_white",
            hovermode="x unified",
            height=320,
            yaxis=dict(title="상관계수 (r)", range=[-1, 1]),
        )
        st.plotly_chart(fig_roll, use_container_width=True)
        st.caption("※ 롤링 상관계수는 최근 12개월 데이터 기준. p-value 기준 통계적 유의수준 0.05 미만을 유의한 상관관계로 판단.")

    # 8. CSV 다운로드 및 출처
    st.markdown("<br>", unsafe_allow_html=True)
    csv_data = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 데이터 CSV 다운로드",
        data=csv_data,
        file_name="economic_indicators.csv",
        mime="text/csv",
    )
    st.caption("데이터 출처: 한국은행 경제통계시스템(ECOS) / 달러인덱스(Yahoo Finance)")

if __name__ == "__main__":
    main()
