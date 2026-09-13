import yfinance as yf
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

def read_stock_codes(filename='input.lst'):
    """
    input.lstファイルから証券コードを読み込む関数
    
    Parameters:
    filename (str): 証券コードが記載されたファイル名
    
    Returns:
    list: 証券コードのリスト
    """
    stock_codes = []
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            for line in file:
                # 改行文字を除去し、空行をスキップ
                code = line.strip()
                if code:
                    stock_codes.append(code)
        print(f"{filename}から{len(stock_codes)}件の証券コードを読み込みました")
        return stock_codes
    except FileNotFoundError:
        print(f"エラー: {filename}ファイルが見つかりません")
        return []
    except Exception as e:
        print(f"ファイル読み込み中にエラーが発生: {e}")
        return []

def calculate_financial_ratios(info, financials, balance_sheet):
    """
    財務比率を計算する関数
    
    Parameters:
    info (dict): 企業の基本情報
    financials (DataFrame): 損益計算書データ
    balance_sheet (DataFrame): 貸借対照表データ
    
    Returns:
    dict: 計算された財務比率と詳細財務データ
    """
    ratios = {
        '自己資本比率': None,
        '営業利益率': None,
        '粗利率': None,
        'ROIC': None,
        '1年前ROIC': None,
        '2年前ROIC': None,
        '3年前ROIC': None,
        '参考ROIC（現預金控除後）': None,
        '法人税合計': None,
        '税引前純利益': None,
        '営業利益': None,
        '株主資本': None,
        '短期有利子負債': None,
        '長期有利子負債': None,
        '現預金等': None
    }
    
    try:
        # ROA (Return on Assets) = 純利益 / 総資産
        # 削除: ROAは出力不要
        
        # ROE (Return on Equity) = 純利益 / 自己資本
        # 削除: ROEは出力不要
        
        # 自己資本比率
        if 'debtToEquity' in info and info['debtToEquity'] is not None:
            # debt-to-equity ratioから自己資本比率を計算
            debt_to_equity = info['debtToEquity']
            equity_ratio = 100 / (1 + debt_to_equity / 100)
            ratios['自己資本比率'] = round(equity_ratio, 2)
        
        # 営業利益率の計算（損益計算書から）
        if financials is not None and not financials.empty:
            # 営業利益と売上高のキーを探す
            operating_income_keys = [
                'Operating Income', 'EBIT', 'Operating Revenue',
                'Gross Profit', 'Total Revenue'
            ]
            revenue_keys = [
                'Total Revenue', 'Revenue', 'Net Sales', 'Sales'
            ]
            
            operating_income = None
            revenue = None
            
            # 営業利益を探す
            for key in operating_income_keys:
                if key in financials.index:
                    operating_income = financials.loc[key].iloc[0] if len(financials.loc[key]) > 0 else None
                    break
            
            # 売上高を探す
            for key in revenue_keys:
                if key in financials.index:
                    revenue = financials.loc[key].iloc[0] if len(financials.loc[key]) > 0 else None
                    break
            
            # 営業利益率を計算
            if operating_income is not None and revenue is not None and revenue != 0:
                ratios['営業利益率'] = round((operating_income / revenue) * 100, 2)
        
        # infoから直接取得できる場合の営業利益率
        if ratios['営業利益率'] is None and 'operatingMargins' in info and info['operatingMargins'] is not None:
            ratios['営業利益率'] = round(info['operatingMargins'] * 100, 2)
        
        # 粗利率の計算 (売上高 - 売上原価) / 売上高 * 100
        if financials is not None and not financials.empty:
            # 売上高の候補キー
            revenue_keys = ['Total Revenue', 'Revenue', 'Net Sales', 'Operating Revenue']
            
            # 売上原価の候補キー
            cogs_keys = ['Cost Of Revenue', 'Cost Of Goods Sold', 'Cost Of Sales', 'Total Costs']
            
            revenue = None
            cogs = None
            
            # 売上高を探す
            for key in revenue_keys:
                if key in financials.index and len(financials.loc[key]) > 0:
                    value = financials.loc[key].iloc[0]
                    if value is not None and not pd.isna(value):
                        revenue = value
                        break
            
            # 売上原価を探す
            for key in cogs_keys:
                if key in financials.index and len(financials.loc[key]) > 0:
                    value = financials.loc[key].iloc[0]
                    if value is not None and not pd.isna(value):
                        cogs = value
                        break
            
            # 粗利率を計算 (売上高 - 売上原価) / 売上高 * 100
            if revenue is not None and cogs is not None and revenue != 0:
                gross_margin = (revenue - cogs) / revenue
                ratios['粗利率'] = round(gross_margin * 100, 2)
        
        # infoから直接取得できる場合の粗利率（フォールバック）
        if ratios['粗利率'] is None and 'grossMargins' in info and info['grossMargins'] is not None:
            ratios['粗利率'] = round(info['grossMargins'] * 100, 2)
        
        # ROIC計算のための各種データ取得
        if financials is not None and not financials.empty and balance_sheet is not None and not balance_sheet.empty:
            # 最新年度、1年前、2年前、3年前、4年前のデータを格納
            roic_years = []
            
            for year_idx in range(5):  # 最新年度(0)、1年前(1)、2年前(2)、3年前(3)、4年前(4)
                year_data = {}
                
                # 1. 法人税合計の取得（複数のキー候補を試行）
                tax_keys = [
                    'Tax Provision', 
                    'Income Tax Expense', 
                    'Tax Effect Of Unusual Items',
                    'Taxes',
                    'Tax Rate For Calcs'
                ]
                for key in tax_keys:
                    if key in financials.index and len(financials.loc[key]) > year_idx:
                        value = financials.loc[key].iloc[year_idx]
                        if value is not None and not pd.isna(value):
                            year_data['法人税合計'] = value
                            break
                
                # 2. 税引前純利益の取得（複数のキー候補を試行）
                pretax_income_keys = [
                    'Pretax Income', 
                    'Income Before Tax', 
                    'Earnings Before Tax',
                    'Pretax Income Loss'
                ]
                for key in pretax_income_keys:
                    if key in financials.index and len(financials.loc[key]) > year_idx:
                        value = financials.loc[key].iloc[year_idx]
                        if value is not None and not pd.isna(value):
                            year_data['税引前純利益'] = value
                            break
                
                # 3. 営業利益の取得
                operating_income_keys = ['Operating Income', 'EBIT']
                for key in operating_income_keys:
                    if key in financials.index and len(financials.loc[key]) > year_idx:
                        year_data['営業利益'] = financials.loc[key].iloc[year_idx]
                        break
                
                # 4. 株主資本の取得（複数のキー候補を試行）
                equity_keys = [
                    'Stockholders Equity', 
                    'Total Stockholder Equity', 
                    'Common Stock Equity',
                    'Total Equity Gross Minority Interest',
                    'Invested Capital'
                ]
                for key in equity_keys:
                    if key in balance_sheet.index and len(balance_sheet.loc[key]) > year_idx:
                        value = balance_sheet.loc[key].iloc[year_idx]
                        if value is not None and not pd.isna(value):
                            year_data['株主資本'] = value
                            break
                
                # 5. 短期有利子負債の取得（デフォルト0、項目が無い場合も0を設定）
                short_debt_keys = ['Current Debt', 'Short Term Debt', 'Current Debt And Capital Lease Obligation']
                year_data['短期有利子負債'] = 0  # 必ずデフォルト値0を設定
                for key in short_debt_keys:
                    if key in balance_sheet.index and len(balance_sheet.loc[key]) > year_idx:
                        debt_value = balance_sheet.loc[key].iloc[year_idx]
                        if debt_value is not None and not pd.isna(debt_value):
                            year_data['短期有利子負債'] = debt_value
                            break
                
                # 6. 長期有利子負債の取得（デフォルト0、項目が無い場合も0を設定）
                long_debt_keys = ['Long Term Debt', 'Long Term Debt And Capital Lease Obligation']
                year_data['長期有利子負債'] = 0  # 必ずデフォルト値0を設定
                for key in long_debt_keys:
                    if key in balance_sheet.index and len(balance_sheet.loc[key]) > year_idx:
                        debt_value = balance_sheet.loc[key].iloc[year_idx]
                        if debt_value is not None and not pd.isna(debt_value):
                            year_data['長期有利子負債'] = debt_value
                            break

                # 7. 現預金等の取得。
                # 正式ROICでは控除せず、最新年度の参考ROICでのみ控除する。
                # yfinanceの銘柄ごとの行名差を吸収するため、広い定義から順に探索する。
                cash_keys = [
                    'Cash Cash Equivalents And Short Term Investments',
                    'Cash And Cash Equivalents',
                    'Cash Financial',
                    'Cash'
                ]
                year_data['現預金等'] = 0
                for key in cash_keys:
                    if key in balance_sheet.index and len(balance_sheet.loc[key]) > year_idx:
                        cash_value = balance_sheet.loc[key].iloc[year_idx]
                        if cash_value is not None and not pd.isna(cash_value):
                            year_data['現預金等'] = cash_value
                            break
                
                roic_years.append(year_data)
            
            # 最新年度のデータを格納（出力用）
            if roic_years:
                ratios['法人税合計'] = roic_years[0].get('法人税合計')
                ratios['税引前純利益'] = roic_years[0].get('税引前純利益')
                ratios['営業利益'] = roic_years[0].get('営業利益')
                ratios['株主資本'] = roic_years[0].get('株主資本')
                # 短期有利子負債と長期有利子負債は必ず数値を設定（None の場合は0）
                ratios['短期有利子負債'] = roic_years[0].get('短期有利子負債', 0) if roic_years[0].get('短期有利子負債') is not None else 0
                ratios['長期有利子負債'] = roic_years[0].get('長期有利子負債', 0) if roic_years[0].get('長期有利子負債') is not None else 0
                ratios['現預金等'] = roic_years[0].get('現預金等', 0) if roic_years[0].get('現預金等') is not None else 0
            
            # 各年度のROIC計算
            roic_labels = ['ROIC', '1年前ROIC', '2年前ROIC', '3年前ROIC']
            for year_idx, label in enumerate(roic_labels):
                if year_idx < len(roic_years):
                    year_data = roic_years[year_idx]
                    tax_total = year_data.get('法人税合計')
                    pretax_income = year_data.get('税引前純利益')
                    operating_income = year_data.get('営業利益')
                    equity = year_data.get('株主資本')
                    # 短期・長期有利子負債は必ず数値として扱う（Noneなら0）
                    short_debt = year_data.get('短期有利子負債', 0)
                    if short_debt is None:
                        short_debt = 0
                    long_debt = year_data.get('長期有利子負債', 0)
                    if long_debt is None:
                        long_debt = 0
                    cash_and_equivalents = year_data.get('現預金等', 0)
                    if cash_and_equivalents is None:
                        cash_and_equivalents = 0
                    
                    # 全てのデータが揃っている場合のみROICを計算
                    if (tax_total is not None and pretax_income is not None and pretax_income != 0 and
                        operating_income is not None and equity is not None):
                        
                        # 1. 実効税率の計算
                        effective_tax_rate = tax_total / pretax_income
                        
                        # 2. NOPATの計算
                        nopat = operating_income * (1 - effective_tax_rate)
                        
                        # 3. 正式ROICの投下資本（現預金等を控除しない）
                        # Invested Capital = Equity + Interest-bearing Debt
                        invested_capital = equity + short_debt + long_debt
                        
                        # 4. ROICの計算。投下資本が0以下の場合は異常値化を避けるため算出しない。
                        if invested_capital > 0:
                            ratios[label] = round((nopat / invested_capital) * 100, 2)

                        # 5. 現預金控除後ROICは、最新年度のみ参考値として計算する。
                        if year_idx == 0:
                            reference_invested_capital = invested_capital - cash_and_equivalents
                            if reference_invested_capital > 0:
                                ratios['参考ROIC（現預金控除後）'] = round(
                                    (nopat / reference_invested_capital) * 100, 2
                                )
        
    except Exception as e:
        print(f"財務比率計算中にエラー: {e}")
    
    return ratios

def analyze_japanese_stocks(stock_codes):
    """
    日本株式の3年分の財務分析を行う関数
    
    Parameters:
    stock_codes (list): 分析する証券コードのリスト
    
    Returns:
    pandas.DataFrame: 各株式の財務情報
    """
    results = []
    total_stocks = len(stock_codes)
    
    for i, code in enumerate(stock_codes, 1):
        print(f"進捗: {i}/{total_stocks} - {code}を処理中...")
        
        try:
            # 日本株式は .T サフィックスを使用
            ticker = yf.Ticker(f"{code}.T")
            
            # 各種財務情報の取得
            cashflow = ticker.cashflow
            financials = ticker.financials
            balance_sheet = ticker.balance_sheet
            info = ticker.info
            
            # キャッシュフロー値を探す関数
            def find_cashflow_value(possible_keys, cashflow_data):
                for key in possible_keys:
                    if key in cashflow_data.index:
                        return cashflow_data.loc[key]
                return None
            
            # キャッシュフローの候補キー
            operating_cash_flow_keys = [
                'Net Cash From Operating Activities', 
                'Operating Cash Flow', 
                'Total Cash From Operating Activities',
                'Cash from Operating Activities'
            ]
            
            investing_cash_flow_keys = [
                'Net Cash From Investing Activities',
                'Investing Cash Flow',
                'Cash Used in Investing Activities'
            ]
            
            # 有形固定資産の取得
            capex_keys = [
                'Capital Expenditure',
                'Purchase Of PPE',
                'Net PPE Purchase And Sale'
            ]
            
            # 無形固定資産の取得
            intangible_keys = [
                'Purchase Of Intangibles',
                'Net Intangibles Purchase And Sale'
            ]
            
            # リース負債（財務CF）
            lease_keys = [
                'Repayment Of Debt',
                'Cash Flow From Continuing Financing Activities',
                'Financing Cash Flow'
            ]
            
            # 営業キャッシュフローの取得
            operating_cash_flows = find_cashflow_value(operating_cash_flow_keys, cashflow)
            
            # 投資キャッシュフローの取得
            investing_cash_flows = find_cashflow_value(investing_cash_flow_keys, cashflow)
            
            # 有形固定資産の取得の取得
            capex_flows = find_cashflow_value(capex_keys, cashflow)
            
            # 無形固定資産の取得の取得
            intangible_flows = find_cashflow_value(intangible_keys, cashflow)
            
            # リース負債の取得（財務CF）
            lease_flows = find_cashflow_value(lease_keys, cashflow)
            
            # 基本情報の抽出
            market_cap_raw = info.get('marketCap')
            # 時価総額を億円単位に変換
            market_cap = round(market_cap_raw / 100000000, 2) if market_cap_raw else None
            
            # 業種の取得
            sector = info.get('sector', '業種不明')
            
            # 配当利回りの取得（そのまま出力、無い場合は0）
            dividend_yield = 0
            if 'dividendYield' in info and info['dividendYield'] is not None:
                dividend_yield = info['dividendYield']
            
            # PERの取得
            per = None
            if 'trailingPE' in info and info['trailingPE'] is not None:
                per = round(info['trailingPE'], 2)
            elif 'forwardPE' in info and info['forwardPE'] is not None:
                per = round(info['forwardPE'], 2)
            
            # （FCF利回りは出力不要のため削除）
            
            # 真FCF利回りの計算（yfinanceのFree Cash Flowを使用）
            true_fcf_yields = []
            operating_cf_value = None
            capex_value = 0
            intangible_value = 0
            lease_value = 0
            
            # 営業CF利回りとCF設備投資率のリスト
            operating_cf_yields = []
            capex_ratios = []
            
            # Free Cash Flowの取得
            free_cash_flow_keys = ['Free Cash Flow']
            free_cash_flows = find_cashflow_value(free_cash_flow_keys, cashflow)
            
            for j in range(4):  # 最新年度、1年前、2年前、3年前
                true_fcf_yield_year = None
                operating_cf_yield_year = None
                capex_ratio_year = None
                
                # 営業CFの取得
                ocf = None
                if operating_cash_flows is not None and len(operating_cash_flows) > j:
                    ocf_val = operating_cash_flows.iloc[j]
                    if ocf_val is not None and not pd.isna(ocf_val):
                        ocf = ocf_val
                
                if market_cap_raw and market_cap_raw > 0:
                    # Free Cash Flowの取得
                    fcf = None
                    if free_cash_flows is not None and len(free_cash_flows) > j:
                        fcf = free_cash_flows.iloc[j]
                    
                    # 真FCF利回りの計算
                    if fcf is not None and not pd.isna(fcf):
                        true_fcf_yield_year = round((fcf / market_cap_raw) * 100, 2)
                    
                    # 営業CF利回りの計算（営業CF ÷ 時価総額 × 100）
                    if ocf is not None:
                        operating_cf_yield_year = round((ocf / market_cap_raw) * 100, 2)
                    
                    # CF設備投資率の計算（(営業CF - FCF) ÷ 営業CF × 100）
                    if ocf is not None and fcf is not None and not pd.isna(fcf) and ocf != 0:
                        capex_ratio_year = round(((ocf - fcf) / ocf) * 100, 2)
                
                true_fcf_yields.append(true_fcf_yield_year)
                operating_cf_yields.append(operating_cf_yield_year)
                capex_ratios.append(capex_ratio_year)
            
            # 直近3年間平均営業CF利回りの計算（最新年度～2年前）
            valid_ocf_yields_3y = [operating_cf_yields[i] for i in range(min(3, len(operating_cf_yields))) if operating_cf_yields[i] is not None]
            avg_operating_cf_yield = round(np.mean(valid_ocf_yields_3y), 2) if valid_ocf_yields_3y else None
            
            # 直近3年間平均CF設備投資率の計算（最新年度～2年前）
            valid_capex_ratios_3y = [capex_ratios[i] for i in range(min(3, len(capex_ratios))) if capex_ratios[i] is not None]
            avg_capex_ratio = round(np.mean(valid_capex_ratios_3y), 2) if valid_capex_ratios_3y else None
            
            # 最新年度の詳細データを取得（参考情報として）
            if operating_cash_flows is not None and len(operating_cash_flows) > 0:
                operating_cf_value = operating_cash_flows.iloc[0]
            
            if capex_flows is not None and len(capex_flows) > 0:
                capex_val = capex_flows.iloc[0]
                if capex_val is not None and not pd.isna(capex_val):
                    capex_value = capex_val
            
            if intangible_flows is not None and len(intangible_flows) > 0:
                intangible_val = intangible_flows.iloc[0]
                if intangible_val is not None and not pd.isna(intangible_val):
                    intangible_value = intangible_val
            
            if lease_flows is not None and len(lease_flows) > 0:
                lease_val = lease_flows.iloc[0]
                if lease_val is not None and not pd.isna(lease_val):
                    lease_value = lease_val
            
            # 3年間の平均真FCF利回りを計算（最新年度～2年前の3年間）
            valid_true_fcf_yields_3y = [true_fcf_yields[i] for i in range(min(3, len(true_fcf_yields))) if i < len(true_fcf_yields) and true_fcf_yields[i] is not None]
            avg_true_fcf_yield = round(np.mean(valid_true_fcf_yields_3y), 2) if valid_true_fcf_yields_3y else None
            
            # 財務比率の計算
            ratios = calculate_financial_ratios(info, financials, balance_sheet)
            
            # （EPS成長率・PR指数は出力不要のため削除）
            eps_growth_rate = None
            
            # ── 直近4年分の営業利益率・売上高増加率の計算 ──
            operating_margin_years = []   # [最新, 1年前, 2年前, 3年前]
            revenue_growth_years = []     # [最新, 1年前, 2年前, 3年前]
            
            if financials is not None and not financials.empty:
                # 売上高候補キー
                rev_keys = ['Total Revenue', 'Revenue', 'Net Sales', 'Operating Revenue']
                # 営業利益候補キー
                oi_keys = ['Operating Income', 'EBIT']
                
                # 売上高を5年分取得（増加率計算のため1年余分に必要）
                rev_series = None
                for key in rev_keys:
                    if key in financials.index:
                        rev_series = financials.loc[key]
                        break
                
                oi_series = None
                for key in oi_keys:
                    if key in financials.index:
                        oi_series = financials.loc[key]
                        break
                
                for yr in range(4):  # 最新年度(0)〜3年前(3)
                    # 営業利益率
                    om = None
                    if (oi_series is not None and rev_series is not None and
                            len(oi_series) > yr and len(rev_series) > yr):
                        oi_val = oi_series.iloc[yr]
                        rv_val = rev_series.iloc[yr]
                        if (oi_val is not None and not pd.isna(oi_val) and
                                rv_val is not None and not pd.isna(rv_val) and rv_val != 0):
                            om = round((oi_val / rv_val) * 100, 2)
                    operating_margin_years.append(om)
                    
                    # 売上高増加率：当年度(yr) vs 前年度(yr+1)
                    rg = None
                    if rev_series is not None and len(rev_series) > yr + 1:
                        rv_cur = rev_series.iloc[yr]
                        rv_prv = rev_series.iloc[yr + 1]
                        if (rv_cur is not None and not pd.isna(rv_cur) and
                                rv_prv is not None and not pd.isna(rv_prv) and rv_prv != 0):
                            rg = round(((rv_cur - rv_prv) / abs(rv_prv)) * 100, 2)
                    revenue_growth_years.append(rg)
            
            # 結果の格納
            result_data = {
                '証券コード': code,
                '企業名': info.get('longName', '企業名不明'),
                '業種': sector,
                '時価総額（億円）': market_cap,
                '配当利回り(%)': dividend_yield,
                'PER': per,
                '過去3年EPS年平均増減率(%)': eps_growth_rate,
                '最新年度真FCF利回り(%)': true_fcf_yields[0] if len(true_fcf_yields) > 0 else None,
                '1年前真FCF利回り(%)': true_fcf_yields[1] if len(true_fcf_yields) > 1 else None,
                '2年前真FCF利回り(%)': true_fcf_yields[2] if len(true_fcf_yields) > 2 else None,
                '3年前真FCF利回り(%)': true_fcf_yields[3] if len(true_fcf_yields) > 3 else None,
                '3年間平均真FCF利回り(%)': avg_true_fcf_yield,
                '最新年度営業CF利回り(%)': operating_cf_yields[0] if len(operating_cf_yields) > 0 else None,
                '1年前営業CF利回り(%)': operating_cf_yields[1] if len(operating_cf_yields) > 1 else None,
                '2年前営業CF利回り(%)': operating_cf_yields[2] if len(operating_cf_yields) > 2 else None,
                '3年前営業CF利回り(%)': operating_cf_yields[3] if len(operating_cf_yields) > 3 else None,
                '3年間平均営業CF利回り(%)': avg_operating_cf_yield,
                '3年間平均CF設備投資率(%)': avg_capex_ratio,
                '最新年度営業利益率(%)': operating_margin_years[0] if len(operating_margin_years) > 0 else None,
                '1年前営業利益率(%)': operating_margin_years[1] if len(operating_margin_years) > 1 else None,
                '2年前営業利益率(%)': operating_margin_years[2] if len(operating_margin_years) > 2 else None,
                '3年前営業利益率(%)': operating_margin_years[3] if len(operating_margin_years) > 3 else None,
                '最新年度売上高増加率(%)': revenue_growth_years[0] if len(revenue_growth_years) > 0 else None,
                '1年前売上高増加率(%)': revenue_growth_years[1] if len(revenue_growth_years) > 1 else None,
                '2年前売上高増加率(%)': revenue_growth_years[2] if len(revenue_growth_years) > 2 else None,
                'ROIC(%)': ratios.get('ROIC'),
                '参考ROIC（現預金控除後）(%)': ratios.get('参考ROIC（現預金控除後）'),
                '1年前ROIC(%)': ratios.get('1年前ROIC'),
                '2年前ROIC(%)': ratios.get('2年前ROIC'),
                '3年前ROIC(%)': ratios.get('3年前ROIC'),
                '自己資本比率(%)': ratios['自己資本比率'],
                '粗利率(%)': ratios['粗利率'],
                '現預金等（円）': ratios.get('現預金等')
            }
            
            results.append(result_data)
        
        except Exception as e:
            print(f"{code}の分析中にエラーが発生: {e}")
            # エラー時でも通常行と同じ列スキーマを維持する。
            # 全銘柄取得失敗時に後段のscreening/sort/statisticsで
            # KeyErrorにならないためのフェイルセーフ。
            results.append({
                '証券コード': code,
                '企業名': 'エラー',
                '業種': None,
                '時価総額（億円）': None,
                '配当利回り(%)': None,
                'PER': None,
                '過去3年EPS年平均増減率(%)': None,
                '最新年度真FCF利回り(%)': None,
                '1年前真FCF利回り(%)': None,
                '2年前真FCF利回り(%)': None,
                '3年前真FCF利回り(%)': None,
                '3年間平均真FCF利回り(%)': None,
                '最新年度営業CF利回り(%)': None,
                '1年前営業CF利回り(%)': None,
                '2年前営業CF利回り(%)': None,
                '3年前営業CF利回り(%)': None,
                '3年間平均営業CF利回り(%)': None,
                '3年間平均CF設備投資率(%)': None,
                '最新年度営業利益率(%)': None,
                '1年前営業利益率(%)': None,
                '2年前営業利益率(%)': None,
                '3年前営業利益率(%)': None,
                '最新年度売上高増加率(%)': None,
                '1年前売上高増加率(%)': None,
                '2年前売上高増加率(%)': None,
                'ROIC(%)': None,
                '参考ROIC（現預金控除後）(%)': None,
                '1年前ROIC(%)': None,
                '2年前ROIC(%)': None,
                '3年前ROIC(%)': None,
                '自己資本比率(%)': None,
                '粗利率(%)': None,
                '現預金等（円）': None
            })
    
    return pd.DataFrame(results)


# ─────────────────────────────────────────────────────────────
# YY Weekly primary screening
# ─────────────────────────────────────────────────────────────
YY_SCREENING_THRESHOLDS = {
    'ROIC_HIGH': 12.0,
    'OPERATING_MARGIN_HIGH': 15.0,
    'FCF_YIELD_HIGH': 4.0,
    'FCF_YIELD_3Y_AVG_HIGH': 3.0,
}


def _classify_trend(values_latest_first, strong_delta):
    """4年系列を Strong Up / Up / Flat / Down / Insufficient に分類する。

    values_latest_first は [最新, 1年前, 2年前, 3年前]。
    右肩上がり判定では1回までの低下を許容する。
    """
    pairs = [(idx, v) for idx, v in enumerate(reversed(values_latest_first))
             if v is not None and not pd.isna(v)]
    if len(pairs) < 3:
        return 'Insufficient'

    ys = np.array([float(v) for _, v in pairs], dtype=float)
    xs = np.arange(len(ys), dtype=float)
    diffs = np.diff(ys)
    up_count = int(np.sum(diffs > 0))
    down_count = int(np.sum(diffs < 0))
    total_delta = ys[-1] - ys[0]
    slope = float(np.polyfit(xs, ys, 1)[0]) if len(ys) >= 2 else 0.0

    if down_count == 0 and up_count >= 2 and total_delta >= strong_delta and slope > 0:
        return 'Strong Up'
    if total_delta > 0 and slope > 0 and down_count <= 1 and up_count >= 1:
        return 'Up'
    if abs(total_delta) < max(strong_delta * 0.25, 0.25):
        return 'Flat'
    return 'Down'


def add_yy_weekly_screening_columns(result_df):
    """YY Weekly用の一次抽出判定列を追加する。

    A: ROIC / 営業利益率 / FCF利回りの3項目すべてが
       「高水準」または「改善トレンド」。
    B: 3項目中2項目が該当。柳下Agentの二次選定対象として保持。
    Exclude: 0-1項目のみ。
    """
    df = result_df.copy()

    def judge_row(row):
        roic_vals = [row.get('ROIC(%)'), row.get('1年前ROIC(%)'),
                     row.get('2年前ROIC(%)'), row.get('3年前ROIC(%)')]
        opm_vals = [row.get('最新年度営業利益率(%)'), row.get('1年前営業利益率(%)'),
                    row.get('2年前営業利益率(%)'), row.get('3年前営業利益率(%)')]
        fcf_vals = [row.get('最新年度真FCF利回り(%)'), row.get('1年前真FCF利回り(%)'),
                    row.get('2年前真FCF利回り(%)'), row.get('3年前真FCF利回り(%)')]

        roic_trend = _classify_trend(roic_vals, strong_delta=3.0)
        opm_trend = _classify_trend(opm_vals, strong_delta=3.0)
        fcf_trend = _classify_trend(fcf_vals, strong_delta=1.5)

        roic_latest = roic_vals[0]
        opm_latest = opm_vals[0]
        fcf_latest = fcf_vals[0]
        fcf_avg3 = row.get('3年間平均真FCF利回り(%)')

        roic_high = roic_latest is not None and not pd.isna(roic_latest) and roic_latest >= YY_SCREENING_THRESHOLDS['ROIC_HIGH']
        opm_high = opm_latest is not None and not pd.isna(opm_latest) and opm_latest >= YY_SCREENING_THRESHOLDS['OPERATING_MARGIN_HIGH']
        fcf_high = (
            (fcf_latest is not None and not pd.isna(fcf_latest) and fcf_latest >= YY_SCREENING_THRESHOLDS['FCF_YIELD_HIGH']) or
            (fcf_avg3 is not None and not pd.isna(fcf_avg3) and fcf_avg3 >= YY_SCREENING_THRESHOLDS['FCF_YIELD_3Y_AVG_HIGH'])
        )

        roic_ok = roic_high or roic_trend in ('Strong Up', 'Up')
        opm_ok = opm_high or opm_trend in ('Strong Up', 'Up')
        fcf_ok = fcf_high or fcf_trend in ('Strong Up', 'Up')
        score = int(roic_ok) + int(opm_ok) + int(fcf_ok)
        rank = 'A' if score == 3 else ('B' if score == 2 else 'Exclude')

        reasons = []
        if roic_ok:
            reasons.append(f"ROIC:{'High' if roic_high else roic_trend}")
        if opm_ok:
            reasons.append(f"OPM:{'High' if opm_high else opm_trend}")
        if fcf_ok:
            reasons.append(f"FCF:{'High' if fcf_high else fcf_trend}")

        return pd.Series({
            'ROICトレンド': roic_trend,
            '営業利益率トレンド': opm_trend,
            'FCF利回りトレンド': fcf_trend,
            'ROIC一次条件': roic_ok,
            '営業利益率一次条件': opm_ok,
            'FCF利回り一次条件': fcf_ok,
            '一次条件充足数': score,
            'YY一次抽出ランク': rank,
            'YY一次抽出理由': '; '.join(reasons),
        })

    judged = df.apply(judge_row, axis=1)
    return pd.concat([df, judged], axis=1)


def save_yy_weekly_candidates(screened_df, timestamp):
    """一次候補(A/B)をCSV/JSONで保存し、柳下Agent二次選定へ渡す。"""
    candidates = screened_df[screened_df['YY一次抽出ランク'].isin(['A', 'B'])].copy()
    # 全銘柄取得失敗などで候補が0件でも安全に保存できるよう、
    # 実在する列だけを使ってsortする。通常時は従来と同じ5列でsortされる。
    sort_spec = [
        ('YY一次抽出ランク', True),
        ('一次条件充足数', False),
        ('ROIC(%)', False),
        ('最新年度営業利益率(%)', False),
        ('3年間平均真FCF利回り(%)', False),
    ]
    sort_cols = [col for col, _ in sort_spec if col in candidates.columns]
    sort_ascending = [asc for col, asc in sort_spec if col in candidates.columns]
    if sort_cols:
        candidates = candidates.sort_values(
            by=sort_cols,
            ascending=sort_ascending,
            na_position='last'
        )

    csv_name = f'yy_weekly_primary_candidates_{timestamp}.csv'
    json_name = f'yy_weekly_primary_candidates_{timestamp}.json'
    candidates.to_csv(csv_name, index=False, encoding='utf-8-sig')
    with open(json_name, 'w', encoding='utf-8') as f:
        json.dump(candidates.replace({np.nan: None}).to_dict(orient='records'), f,
                  ensure_ascii=False, indent=2, default=str)

    return candidates, csv_name, json_name

def main():
    """
    メイン処理
    """
    print("日本株式財務分析プログラムを開始します...")
    
    # input.lstファイルから証券コードを読み込み
    stock_codes = read_stock_codes('input.lst')
    
    if not stock_codes:
        print("証券コードが読み込めませんでした。処理を終了します。")
        return
    
    # 財務分析の実行
    print("財務分析を開始します...")
    result_df = analyze_japanese_stocks(stock_codes)
    
    # 結果を整形して表示
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1500)
    pd.set_option('display.float_format', '{:.2f}'.format)
    
    print("\n=== 分析結果 ===")
    print(result_df)
    
    # YY Weekly一次抽出判定を付加
    screened_df = add_yy_weekly_screening_columns(result_df)

    # CSVファイルに出力（日時を追加して一意のファイル名にする）
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    output_filename = f'japanese_stocks_financial_analysis_3years_{timestamp}.csv'
    screened_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    print(f"\n結果を{output_filename}に保存しました。")

    # YY Weekly用のA/B一次候補を別ファイルで保存
    yy_candidates, yy_csv, yy_json = save_yy_weekly_candidates(screened_df, timestamp)
    print(f"YY Weekly一次候補を{yy_csv} / {yy_json}に保存しました。")
    print(f"YY Weekly一次候補数: {len(yy_candidates)}件 "
          f"(A={(yy_candidates['YY一次抽出ランク'] == 'A').sum()} / "
          f"B={(yy_candidates['YY一次抽出ランク'] == 'B').sum()})")
    
    # 統計情報の表示
    print(f"\n=== 統計情報 ===")
    print(f"分析対象企業数: {len(screened_df)}")
    print(f"真FCF利回りデータ取得成功: {screened_df['3年間平均真FCF利回り(%)'].notna().sum()}件")
    print(f"営業CF利回りデータ取得成功: {screened_df['3年間平均営業CF利回り(%)'].notna().sum()}件")
    print(f"CF設備投資率データ取得成功: {screened_df['3年間平均CF設備投資率(%)'].notna().sum()}件")
    print(f"ROICデータ取得成功: {screened_df['ROIC(%)'].notna().sum()}件")
    print(f"PERデータ取得成功: {screened_df['PER'].notna().sum()}件")
    print(f"EPS成長率データ取得成功: {screened_df['過去3年EPS年平均増減率(%)'].notna().sum()}件")
    print(f"配当利回りデータ取得成功: {screened_df['配当利回り(%)'].notna().sum()}件")
    print(f"粗利率データ取得成功: {screened_df['粗利率(%)'].notna().sum()}件")
    print(f"営業利益率データ取得成功: {screened_df['最新年度営業利益率(%)'].notna().sum()}件")
    print(f"売上高増加率データ取得成功: {screened_df['最新年度売上高増加率(%)'].notna().sum()}件")
    print(f"自己資本比率データ取得成功: {screened_df['自己資本比率(%)'].notna().sum()}件")
    print(f"YY一次抽出A: {(screened_df['YY一次抽出ランク'] == 'A').sum()}件")
    print(f"YY一次抽出B: {(screened_df['YY一次抽出ランク'] == 'B').sum()}件")

if __name__ == "__main__":
    main()
