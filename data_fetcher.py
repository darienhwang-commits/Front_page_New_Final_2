"""
데이터 수집 모듈
한국은행 OPEN API 및 FinanceDataReader 활용
"""
import requests
import pandas as pd
import FinanceDataReader as fdr
import yfinance as yf
import os
import calendar
import streamlit as st

@st.cache_data(ttl=3600)
def get_leading_index(start_date: str, end_date: str) -> pd.DataFrame:
    """
    한국은행 선행지수 순환변동치 데이터 수집 함수
    """
    api_key = os.environ.get("ECOS_API_KEY")
    if not api_key:
        return pd.DataFrame(columns=["date", "value"])

    url = f"https://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/1000/901Y067/M/{start_date}/{end_date}/I16E"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if "RESULT" in data:
            code = data["RESULT"].get("CODE", "")
            message = data["RESULT"].get("MESSAGE", "알 수 없는 오류")
            raise ValueError(f"ECOS API 오류 [{code}]: {message}")

        rows = data.get("StatisticSearch", {}).get("row", [])
        if not rows:
            return pd.DataFrame(columns=["date", "value"])

        df = pd.DataFrame(rows)
        df = df[['TIME', 'DATA_VALUE']].rename(columns={'TIME': 'date', 'DATA_VALUE': 'value'})
        df['date'] = pd.to_datetime(df['date'], format='%Y%m')
        df['value'] = df['value'].astype(float)

        return df

    except ValueError:
        raise
    except Exception as e:
        print(f"API 요청 중 에러 발생: {e}")
        return pd.DataFrame(columns=["date", "value"])

@st.cache_data(ttl=3600)
def get_dollar_index(start_date: str, end_date: str) -> pd.DataFrame:
    """
    달러 인덱스 데이터 수집 함수
    """
    start_dt = pd.to_datetime(start_date, format="%Y%m")

    end_year, end_month = int(end_date[:4]), int(end_date[4:])
    last_day = calendar.monthrange(end_year, end_month)[1]
    end_dt = pd.to_datetime(f"{end_year}{end_month:02d}{last_day}", format="%Y%m%d")

    try:
        df = fdr.DataReader('DX-Y.NYB', start_dt, end_dt)
        if df.empty:
            raise ValueError("FDR returned empty DataFrame")
    except Exception as e:
        print(f"FDR failed: {e}. Fallback to yfinance.")
        try:
            df = yf.download('DX-Y.NYB', start=start_dt, end=end_dt)
            if df.empty:
                raise ValueError("yfinance returned empty DataFrame")
        except Exception as e2:
            print(f"yfinance failed: {e2}")
            return pd.DataFrame(columns=["date", "dollar_index"])

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    df = df[['Close']].rename(columns={'Close': 'dollar_index'})
    df.index.name = 'date'
    df = df.resample("ME").last().reset_index()

    return df

@st.cache_data(ttl=3600)
def get_kospi(start_date: str, end_date: str) -> pd.DataFrame:
    """
    코스피 지수 데이터 수집 함수
    """
    start_dt = pd.to_datetime(start_date, format="%Y%m")

    end_year, end_month = int(end_date[:4]), int(end_date[4:])
    last_day = calendar.monthrange(end_year, end_month)[1]
    end_dt = pd.to_datetime(f"{end_year}{end_month:02d}{last_day}", format="%Y%m%d")

    try:
        df = fdr.DataReader('KS11', start_dt, end_dt)
        if df.empty:
            raise ValueError("FDR returned empty DataFrame")
    except Exception as e:
        print(f"FDR failed for KOSPI: {e}. Fallback to yfinance.")
        try:
            df = yf.download('^KS11', start=start_dt, end=end_dt)
            if df.empty:
                raise ValueError("yfinance returned empty DataFrame")
        except Exception as e2:
            print(f"yfinance failed for KOSPI: {e2}")
            return pd.DataFrame(columns=["date", "kospi"])

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    df = df[['Close']].rename(columns={'Close': 'kospi'})
    df.index.name = 'date'
    df = df.resample("ME").last().reset_index()

    return df

def get_combined_data(start_date: str, end_date: str) -> pd.DataFrame:
    """
    선행지수와 달러인덱스 데이터를 병합하는 함수
    """
    df_leading = get_leading_index(start_date, end_date)
    df_dollar = get_dollar_index(start_date, end_date)

    if df_leading.empty and df_dollar.empty:
        return pd.DataFrame()

    if not df_leading.empty:
        df_leading['date'] = df_leading['date'] + pd.offsets.MonthEnd(0)

    if df_leading.empty:
        return df_dollar.ffill()
    elif df_dollar.empty:
        return df_leading.ffill()

    df_combined = pd.merge(df_leading, df_dollar, on='date', how='outer')
    df_combined = df_combined.sort_values('date')
    df_combined = df_combined.ffill()

    return df_combined
