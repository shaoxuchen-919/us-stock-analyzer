"""
SEC EDGAR XBRL 数据获取模块
从SEC官方XBRL API获取美股上市公司5+年财务数据
免费、无需API Key、数据源为SEC 10-K官方报表
"""

import httpx
import json
import os
import time

# 缓存目录（云平台用/tmp避免只读文件系统问题）
if os.environ.get("RENDER"):
    CACHE_DIR = "/tmp/edgar_cache"
else:
    CACHE_DIR = os.path.join(os.path.dirname(__file__), "edgar_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# SEC要求的请求标识
EDGAR_USER_AGENT = "financial-analyzer research@example.com"

# ticker -> CIK 映射缓存文件
TICKER_CIK_CACHE = os.path.join(CACHE_DIR, "ticker_cik_map.json")


def get_ticker_cik_map():
    """
    从SEC下载ticker->CIK映射表并缓存到本地
    返回: dict, key为ticker(大写), value为CIK(整数)
    """
    # 检查本地缓存（每天更新一次即可）
    if os.path.exists(TICKER_CIK_CACHE):
        mtime = os.path.getmtime(TICKER_CIK_CACHE)
        if time.time() - mtime < 86400:  # 24小时内
            with open(TICKER_CIK_CACHE, 'r') as f:
                return json.load(f)

    headers = {'User-Agent': EDGAR_USER_AGENT}
    url = 'https://www.sec.gov/files/company_tickers.json'
    resp = httpx.get(url, headers=headers, timeout=30)

    if resp.status_code != 200:
        raise ValueError(f"无法获取SEC ticker映射表: HTTP {resp.status_code}")

    raw = resp.json()
    # 转换为 ticker(大写) -> cik_str 的格式
    mapping = {}
    for k, v in raw.items():
        ticker = v['ticker'].upper()
        cik = v['cik_str']
        mapping[ticker] = cik

    # 写入缓存
    with open(TICKER_CIK_CACHE, 'w') as f:
        json.dump(mapping, f)

    return mapping


def get_cik_for_ticker(ticker):
    """根据ticker获取CIK"""
    mapping = get_ticker_cik_map()
    cik = mapping.get(ticker.upper())
    if not cik:
        raise ValueError(f"未找到ticker {ticker} 的CIK，请检查股票代码是否正确")
    return str(cik).zfill(10)


# XBRL标签名 -> 内部字段名映射
# SEC XBRL标签是US GAAP标准命名，有些字段有多种备选标签
XBRL_FIELD_MAP = {
    # === 利润表 ===
    "total_revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "TotalRevenue",
        "NetRevenue",
    ],
    "cost_of_revenue": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfRevenueExcludingDepreciationDepletionAndAmortization",
    ],
    "gross_profit": [
        "GrossProfit",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
        "TotalOperatingIncomeAsReported",
    ],
    "net_income": [
        "NetIncomeLoss",
        "NetIncome",
        "NetIncomeCommonStockholders",
    ],
    "net_income_common": [
        "NetIncomeCommonStockholders",
        "NetIncomeLoss",
        "NetIncome",
    ],
    "selling_expense": [
        "SellingGeneralAndAdministrativeExpense",
        "SellingAndMarketingExpense",
        "GeneralAndAdministrativeExpense",
    ],
    "rd_expense": [
        "ResearchAndDevelopmentExpense",
    ],
    "interest_expense": [
        "InterestExpense",
        "InterestExpenseOperating",
    ],
    "depreciation": [
        "DepreciationAndAmortization",
        "DepreciationDepletionAndAmortization",
    ],
    "operating_expense": [
        "OperatingExpenses",
        "CostsAndExpenses",
    ],
    "diluted_eps": [
        "EarningsPerShareDiluted",
        "NetIncomePerShareDiluted",
    ],
    # === 资产负债表 ===
    "total_assets": [
        "Assets",
    ],
    "total_current_assets": [
        "AssetsCurrent",
        "CurrentAssets",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
        "CashAndCashEquivalents",
    ],
    "net_receivables": [
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
        "NetReceivables",
    ],
    "inventory": [
        "InventoryNet",
        "Inventory",
    ],
    "fixed_assets": [
        "PropertyPlantAndEquipmentNet",
        "NetFixedAssets",
    ],
    "intangible_assets": [
        "IntangibleAssetsNetExcludingGoodwill",
        "IntangibleAssets",
    ],
    "goodwill": [
        "Goodwill",
    ],
    "total_liabilities": [
        "Liabilities",
        "LiabilitiesNetMinorityInterest",
        "TotalLiabilities",
    ],
    "total_current_liabilities": [
        "LiabilitiesCurrent",
        "CurrentLiabilities",
    ],
    "short_term_debt": [
        "LongTermDebtCurrent",
        "DebtCurrent",
        "ShortTermDebt",
        "CommercialPaper",
    ],
    "long_term_debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
    ],
    "total_equity": [
        "StockholdersEquity",
        "CommonStockholdersEquity",
        "Equity",
    ],
    "total_non_current_liabilities": [
        "LiabilitiesNoncurrent",
        "NoncurrentLiabilities",
        "LongTermLiabilities",
    ],
    "retained_earnings": [
        "RetainedEarningsAccumulatedDeficit",
        "RetainedEarnings",
    ],
    "prepaid_expenses": [
        "PrepaidExpenseAndOtherAssetsCurrent",
        "PrepaidExpenses",
        "OtherAssetsCurrent",
    ],
    "long_term_investments": [
        "AvailableForSaleDebtSecuritiesNoncurrent",
        "InvestmentsNoncurrent",
        "LongTermInvestments",
    ],
    "other_non_current_assets": [
        "OtherAssetsNoncurrent",
        "OtherNoncurrentAssets",
    ],
    "accounts_payable": [
        "AccountsPayableCurrent",
        "AccountsPayable",
    ],
    # === 现金流量表 ===
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "CashFlowFromContinuingOperatingActivities",
    ],
    "capital_expenditure": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "CapitalExpenditure",
        "PurchaseOfPPE",
    ],
    "free_cash_flow": [
        "FreeCashFlow",  # 不是标准XBRL标签，多数公司不报此值
    ],
    "change_in_working_capital": [
        "IncreaseDecreaseInWorkingCapital",
    ],
    "stock_based_compensation": [
        "ShareBasedCompensationArrangementNoncashEquityClassifiedFairValueLoss",
        "StockBasedCompensation",
    ],
}


def fetch_sec_financial_data(ticker):
    """
    从SEC EDGAR XBRL API获取5+年财务数据
    返回: (data_dict, years_list)
    data_dict: {year_str: {field_name: value_or_None}}
    years_list: 按降序排列的财年字符串列表

    注意：
    - SEC财年基于公司实际财年结束月份（如AAPL是FY ending Sep）
    - 数据来源是SEC 10-K XBRL filing，是最权威的数据源
    """
    cik_str = get_cik_for_ticker(ticker)

    # 获取company facts
    headers = {'User-Agent': EDGAR_USER_AGENT}
    facts_url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_str}.json'

    # 检查本地缓存
    cache_file = os.path.join(CACHE_DIR, f"{ticker.upper()}_facts.json")
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if time.time() - mtime < 86400:  # 24小时缓存
            with open(cache_file, 'r') as f:
                sec_data = json.load(f)
        else:
            sec_data = None
    else:
        sec_data = None

    if sec_data is None:
        resp = httpx.get(facts_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise ValueError(f"无法获取 {ticker} (CIK:{cik_str}) 的SEC XBRL数据: HTTP {resp.status_code}")
        sec_data = resp.json()
        # 写入缓存
        with open(cache_file, 'w') as f:
            json.dump(sec_data, f)

    us_gaap = sec_data.get('facts', {}).get('us-gaap', {})
    if not us_gaap:
        raise ValueError(f"未找到 {ticker} 的US-GAAP数据")

    # 从XBRL数据中提取年度值
    # XBRL数据结构：每个字段有units->USD/shares等，每个unit下是值列表
    # 每个值有 fy(财年), fp(财期: FY=全年, Q1/Q2/Q3/Q4=季度), filed(提交日期), val(值)

    def extract_fy_values(xbrl_tags):
        """
        从XBRL标签列表中提取财年全年值，按优先级尝试
        
        关键逻辑：XBRL中同一tag同一fy会有多个值
        - 同一10-K filing包含3个财年数据（当前年+2个比较年）
        - fy=2024但end=2022-09-24的值是FY2022的，不是FY2024的
        - 必须用end字段（财年结束日期）来区分真正属于哪个财年
        
        策略：
        1. 用end日期归组，同一end日期下取最大值（合并数>分部数）
        2. 同一end日期同一tag可能有分部拆分，取abs最大值
        """
        for tag in xbrl_tags:
            if tag not in us_gaap:
                continue
            units = us_gaap[tag].get('units', {})
            # 优先取USD单位
            for unit_type in ['USD', 'USD/shares', 'shares', 'pure']:
                if unit_type not in units:
                    continue
                vals = units[unit_type]
                # 按 end日期 归组取值（end是财年结束日期，真正标识数据归属）
                end_map = {}  # {end_date: max_value}
                for v in vals:
                    fy = v.get('fy')
                    fp = v.get('fp')
                    end = v.get('end')
                    if not (fy and fp == 'FY'):
                        continue
                    if not end:
                        # 无end字段的值不可靠，跳过
                        continue
                    val = v.get('val')
                    if val is None:
                        continue
                    existing = end_map.get(end)
                    if existing is None or abs(val) > abs(existing):
                        end_map[end] = val
                
                if not end_map:
                    continue
                
                # 将end日期转为财年标签
                # end=2025-09-27 → FY2025, end=2024-09-28 → FY2024
                fy_result = {}
                for end_date, val in end_map.items():
                    # end日期的年份就是财年
                    fy_label = end_date[:4]  # 取年份部分
                    # 如果同一财年有多个end日期（不同filing），取最新的filing值
                    existing_val = fy_result.get(fy_label)
                    if existing_val is None or abs(val) > abs(existing_val):
                        fy_result[fy_label] = val
                
                if fy_result:
                    return fy_result
        return {}  # 未找到任何标签

    # 提取所有字段
    field_data = {}
    for field_name, xbrl_tags in XBRL_FIELD_MAP.items():
        field_data[field_name] = extract_fy_values(xbrl_tags)

    # 确定共有财年范围（取所有核心字段都有的年份）
    core_fields = ["total_revenue", "total_assets", "net_income", "total_liabilities", "total_equity"]
    year_sets = []
    for f in core_fields:
        if field_data[f]:
            year_sets.append(set(field_data[f].keys()))

    if not year_sets:
        raise ValueError(f"{ticker} 的SEC数据中未找到核心财务字段")

    # 取交集，然后取最近5年
    common_years = set.intersection(*year_sets)
    years_sorted = sorted(common_years, reverse=True)[:5]
    years = years_sorted

    # 构建按年份的数据字典
    result = {}
    for yr in years:
        yr_data = {}
        for field_name, yr_values in field_data.items():
            yr_data[field_name] = yr_values.get(yr)  # None if not available
        result[yr] = yr_data

    return result, years


def get_sec_company_info(ticker):
    """从SEC获取公司基本信息（名称等）"""
    cik_str = get_cik_for_ticker(ticker)

    headers = {'User-Agent': EDGAR_USER_AGENT}
    # SEC company info API
    url = f'https://data.sec.gov/api/xbrl/companyconcept/CIK{cik_str}/us-gaap/Assets.json'
    resp = httpx.get(url, headers=headers, timeout=15)

    # 从XBRL数据的元信息中提取公司名称
    cache_file = os.path.join(CACHE_DIR, f"{ticker.upper()}_facts.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            sec_data = json.load(f)
        # 公司名在顶层
        return {
            "name": sec_data.get("entityName", ticker),
            "cik": cik_str,
        }

    return {"name": ticker, "cik": cik_str}
