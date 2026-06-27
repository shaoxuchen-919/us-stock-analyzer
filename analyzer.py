"""
美股财报四维分析 - 数据获取与分析模块
数据源策略：
1. SEC EDGAR XBRL API（主源）：获取5+年三大报表数据，官方10-K XBRL数据，免费无API Key
2. yfinance（辅助源）：获取公司基本信息和当前市场比率（PE/PB/Beta等）
"""

import yfinance as yf
import pandas as pd
import os
import time
import httpx
import json

from sec_data import fetch_sec_financial_data, get_cik_for_ticker

# yfinance缓存目录（云平台用/tmp避免权限问题）
if os.environ.get("RENDER"):
    _YF_CACHE = "/tmp/yf_cache"
else:
    _YF_CACHE = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(_YF_CACHE, exist_ok=True)
yf.set_tz_cache_location(_YF_CACHE)

# 本地缓存目录
if os.environ.get("RENDER"):
    EDGAR_CACHE_DIR = "/tmp/edgar_cache"
else:
    EDGAR_CACHE_DIR = os.path.join(os.path.dirname(__file__), "edgar_cache")
os.makedirs(EDGAR_CACHE_DIR, exist_ok=True)


def get_stock_info(ticker):
    """获取公司基本信息（SEC EDGAR名称 + yfinance行业/板块补充）"""
    sec_info = {"name": ticker}
    try:
        cik_str = get_cik_for_ticker(ticker)
        cache_file = os.path.join(EDGAR_CACHE_DIR, f"{ticker.upper()}_facts.json")
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                sec_data = json.load(f)
            sec_info["name"] = sec_data.get("entityName", ticker)
    except Exception:
        pass

    yf_info = {}
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        yf_info = {
            "sector": info.get("sector", "-"),
            "industry": info.get("industry", "-"),
            "market_cap": info.get("marketCap", "-"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", "-"),
            "country": info.get("country", "-"),
            "website": info.get("website", "-"),
        }
    except Exception:
        yf_info = {
            "sector": "-", "industry": "-", "market_cap": "-",
            "currency": "USD", "exchange": "-", "country": "-", "website": "-",
        }

    return {
        "name": sec_info.get("name") or yf_info.get("name", ticker),
        **yf_info,
    }


def safe_get(df, keys, year):
    if df is None or df.empty:
        return None
    if isinstance(keys, str):
        keys = [keys]
    for key in keys:
        if key in df.index:
            try:
                val = df.loc[key, year]
                if pd.isna(val):
                    continue
                return float(val)
            except (KeyError, IndexError, TypeError):
                continue
    return None


def format_billion(val, currency="USD"):
    if val is None:
        return "-"
    return f"{val / 1e9:.2f}亿美元"


def format_pct(val):
    if val is None:
        return "-%"
    return f"{val:.2f}%"


def fmt_num_2(val):
    if val is None:
        return "-"
    return f"{val:.2f}"


# yfinance键名映射
FIELD_KEYS = {
    "total_revenue": ["Total Revenue"],
    "cost_of_revenue": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "Total Operating Income As Reported"],
    "net_income": ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest"],
    "net_income_common": ["Net Income Common Stockholders", "Net Income"],
    "selling_expense": ["Selling General And Administration"],
    "rd_expense": ["Research And Development"],
    "interest_expense": ["Interest Expense", "Interest Expense Non Operating"],
    "depreciation": ["Depreciation And Amortization", "Depreciation Amortization Depletion", "Reconciled Depreciation"],
    "interest_income": ["Interest Income", "Net Interest Income", "Interest Income Non Operating"],
    "tax_provision": ["Tax Provision"],
    "pretax_income": ["Pretax Income"],
    "diluted_eps": ["Diluted EPS"],
    "basic_eps": ["Basic EPS"],
    "operating_expense": ["Operating Expense"],
    "total_assets": ["Total Assets"],
    "total_current_assets": ["Total Current Assets", "Current Assets"],
    "cash": ["Cash And Cash Equivalents At Carrying Value", "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash Financial", "Cash Equivalents"],
    "net_receivables": ["Net Receivables", "Receivables", "Accounts Receivable", "Other Receivables"],
    "inventory": ["Inventory"],
    "prepaid_expenses": ["Prepaid Expenses", "Other Current Assets"],
    "fixed_assets": ["Net Fixed Assets", "Property Plant Equipment Net", "Net PPE"],
    "intangible_assets": ["Intangible Assets", "Goodwill And Other Intangible Assets"],
    "long_term_investments": ["Long Term Investments", "Investments And Advances", "Other Investments", "Investmentin Financial Assets", "Available For Sale Securities"],
    "goodwill": ["Goodwill"],
    "other_non_current_assets": ["Other Non Current Assets", "Non Current Deferred Assets"],
    "total_liabilities": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
    "total_current_liabilities": ["Total Current Liabilities", "Current Liabilities"],
    "short_term_debt": ["Short Term Debt", "Current Debt", "Current Debt And Capital Lease Obligation", "Commercial Paper"],
    "long_term_debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "total_debt": ["Total Debt", "Net Debt"],
    "total_equity": ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    "accounts_payable": ["Accounts Payable", "Payables", "Payables And Accrued Expenses"],
    "retained_earnings": ["Retained Earnings"],
    "total_non_current_liabilities": ["Total Non Current Liabilities Net Minority Interest"],
    "operating_cash_flow": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capital_expenditure": ["Capital Expenditure", "Purchase Of PPE", "Net PPE Purchase And Sale"],
    "free_cash_flow": ["Free Cash Flow"],
    "change_in_working_capital": ["Change In Working Capital", "Change In Other Working Capital"],
    "stock_based_compensation": ["Stock Based Compensation"],
}


def fetch_financial_data(ticker):
    """获取美股5+年财务数据"""
    sec_data, sec_years = fetch_sec_financial_data(ticker)

    for yr in sec_years:
        d = sec_data[yr]
        if d.get("total_debt") is None:
            st = d.get("short_term_debt") or 0
            lt = d.get("long_term_debt") or 0
            d["total_debt"] = st + lt if (st or lt) else None
        if d.get("free_cash_flow") is None:
            ocf = d.get("operating_cash_flow")
            capex = d.get("capital_expenditure")
            if ocf is not None and capex is not None:
                d["free_cash_flow"] = ocf - abs(capex)

    ratios = {}
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        ratios = {
            "roe": info.get("returnOnEquity"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "beta": info.get("beta"),
            "pe_ratio": info.get("trailingPE"),
            "price_to_book": info.get("priceToBook"),
            "enterprise_value": info.get("enterpriseValue"),
        }
    except Exception:
        pass

    return sec_data, ratios, sec_years


def compute_four_dimensions(data, ratios, years):
    """四维分析计算核心"""

    result = {}
    for yr in years:
        d = data[yr]
        dim = {}

        # 一、投资角度
        focus_parts = [d["inventory"], d["cash"], d["net_receivables"], d["prepaid_expenses"]]
        has_any_focus = any(v is not None for v in focus_parts)
        product_focus_sum = sum((v or 0) for v in focus_parts)

        if d["total_assets"] and d["total_assets"] != 0 and has_any_focus:
            dim["product_focus"] = product_focus_sum / d["total_assets"] * 100
        else:
            dim["product_focus"] = None
        dim["product_focus_label"] = (
            "聚焦型" if dim["product_focus"] is not None and dim["product_focus"] > 50
            else "分散型" if dim["product_focus"] is not None else "数据不足"
        )

        prod_parts = [d["fixed_assets"], d["intangible_assets"], d["long_term_investments"]]
        has_any_prod = any(v is not None for v in prod_parts)
        production_sum = sum((v or 0) for v in prod_parts)

        if d["total_assets"] and d["total_assets"] != 0 and has_any_prod:
            dim["production_intensity"] = production_sum / d["total_assets"] * 100
        else:
            dim["production_intensity"] = None
        dim["production_label"] = (
            "重资产型" if dim["production_intensity"] is not None and dim["production_intensity"] > 40
            else "轻资产型" if dim["production_intensity"] is not None else "数据不足"
        )

        # 二、筹资角度
        interest_debt = d["total_debt"]
        if interest_debt is None:
            interest_debt = (d["short_term_debt"] or 0) + (d["long_term_debt"] or 0)

        total_liab = d["total_liabilities"] or 0
        operating_debt = total_liab - interest_debt

        if d["total_assets"] and d["total_assets"] != 0:
            dim["operating_debt_ratio"] = operating_debt / d["total_assets"] * 100
            dim["interest_debt_ratio"] = interest_debt / d["total_assets"] * 100
            dim["debt_to_asset_ratio"] = total_liab / d["total_assets"] * 100
        else:
            dim["operating_debt_ratio"] = None
            dim["interest_debt_ratio"] = None
            dim["debt_to_asset_ratio"] = None

        cur_assets = d["total_current_assets"]
        cur_liab = d["total_current_liabilities"]
        if cur_liab and cur_liab != 0:
            dim["current_ratio"] = (cur_assets or 0) / cur_liab
            dim["quick_ratio"] = ((cur_assets or 0) - (d["inventory"] or 0)) / cur_liab
        else:
            dim["current_ratio"] = None
            dim["quick_ratio"] = None

        # 三、经营角度
        if d["total_revenue"] and d["total_revenue"] != 0:
            if d["gross_profit"] is not None:
                dim["gross_margin"] = d["gross_profit"] / d["total_revenue"] * 100
            elif d["cost_of_revenue"] is not None:
                dim["gross_margin"] = (d["total_revenue"] - d["cost_of_revenue"]) / d["total_revenue"] * 100
            else:
                dim["gross_margin"] = None
        else:
            dim["gross_margin"] = None

        if d["total_revenue"] and d["total_revenue"] != 0 and d["net_income"] is not None:
            dim["ros"] = d["net_income"] / d["total_revenue"] * 100
        else:
            dim["ros"] = None

        if d["total_equity"] and d["total_equity"] != 0 and d["net_income"] is not None:
            dim["roe"] = d["net_income"] / abs(d["total_equity"]) * 100
            dim["roe_note"] = "权益为负，ROE极高但属数学效应" if d["total_equity"] < 0 else None
        else:
            dim["roe"] = None
            dim["roe_note"] = None

        if d["total_revenue"] and d["total_revenue"] != 0:
            dim["selling_ratio"] = (d["selling_expense"] or 0) / d["total_revenue"] * 100
            dim["rd_ratio"] = (d["rd_expense"] or 0) / d["total_revenue"] * 100
        else:
            dim["selling_ratio"] = None
            dim["rd_ratio"] = None

        if d["net_income"] and d["net_income"] != 0 and d["operating_cash_flow"] is not None:
            dim["ocf_to_net_income"] = d["operating_cash_flow"] / abs(d["net_income"]) * 100
        else:
            dim["ocf_to_net_income"] = None

        dim["free_cash_flow"] = d["free_cash_flow"]

        # 四、规模角度
        dim["total_revenue_val"] = d["total_revenue"]
        dim["total_assets_val"] = d["total_assets"]
        dim["net_income_val"] = d["net_income"]

        result[yr] = dim

    return result


# ========== 各维度5年数据表构建 ==========

def build_dim_tables(dims, years):
    """
    构建四个维度的5年数据表（不含分析结论）
    返回: dict {dim_key: {title: str, rows: [{label, values:{yr->str}, tags?:{yr->str}}]}}
    """

    result = {}

    # 一、投资角度
    invest_rows = []
    for key, label in [("product_focus", "产品聚焦度"), ("production_intensity", "产能力度")]:
        row = {"label": label}
        row["values"] = {}
        row["tags"] = {}
        for yr in years:
            val = dims[yr].get(key)
            row["values"][yr] = format_pct(val)
            if key == "product_focus":
                row["tags"][yr] = dims[yr].get("product_focus_label", "")
            elif key == "production_intensity":
                row["tags"][yr] = dims[yr].get("production_label", "")
        invest_rows.append(row)
    result["invest"] = {"title": "一、投资角度", "rows": invest_rows}

    # 二、筹资角度
    fund_rows = []
    for key, label in [
        ("debt_to_asset_ratio", "资产负债率"), ("interest_debt_ratio", "有息负债占比"),
        ("operating_debt_ratio", "经营负债占比"), ("current_ratio", "流动比率"),
        ("quick_ratio", "速动比率")
    ]:
        row = {"label": label}
        row["values"] = {}
        for yr in years:
            val = dims[yr].get(key)
            if key in ["current_ratio", "quick_ratio"]:
                row["values"][yr] = fmt_num_2(val)
            else:
                row["values"][yr] = format_pct(val)
        fund_rows.append(row)
    result["fund"] = {"title": "二、筹资角度", "rows": fund_rows}

    # 三、经营角度
    operate_rows = []
    for key, label in [
        ("gross_margin", "毛利率"), ("ros", "净利润率(ROS)"), ("roe", "ROE"),
        ("selling_ratio", "销售管理费用率"), ("rd_ratio", "研发费用率"),
        ("ocf_to_net_income", "OCF/净利润"), ("free_cash_flow", "FCF")
    ]:
        row = {"label": label}
        row["values"] = {}
        row["roe_note"] = {}
        for yr in years:
            val = dims[yr].get(key)
            if key == "free_cash_flow":
                row["values"][yr] = format_billion(val)
            else:
                row["values"][yr] = format_pct(val)
            if key == "roe" and dims[yr].get("roe_note"):
                row["roe_note"][yr] = dims[yr]["roe_note"]
        operate_rows.append(row)
    result["operate"] = {"title": "三、经营角度", "rows": operate_rows}

    # 四、规模角度
    scale_rows = []
    for key, label in [("total_revenue_val", "总营收"), ("total_assets_val", "总资产"), ("net_income_val", "净利润")]:
        row = {"label": label}
        row["values"] = {}
        for yr in years:
            val = dims[yr].get(key)
            row["values"][yr] = format_billion(val)
        scale_rows.append(row)
    result["scale"] = {"title": "四、规模角度", "rows": scale_rows}

    return result


# ========== 年度分析结论生成（参考A股截图风格）==========

def build_annual_conclusion(data, dims, years):
    """
    生成年度分析结论：四个维度各一段文字分析
    返回: list of {icon, title, text}
    """

    def _avg(key):
        vals = [dims[yr].get(key) for yr in years if dims[yr].get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    def _latest(key):
        for yr in years:
            val = dims[yr].get(key)
            if val is not None:
                return val, yr
        return None, None

    def _data_latest(data_key):
        for yr in years:
            val = data[yr].get(data_key)
            if val is not None:
                return val, yr
        return None, None

    conclusions = []

    # ===== 一、投资角度 =====
    parts = []
    avg_focus = _avg("product_focus")
    latest_focus, fy_focus = _latest("product_focus")
    if avg_focus is not None:
        parts.append(f"产品聚焦度{avg_focus:.2f}%")

    # 核心经营资产占比
    core_parts = []
    for yr in years[-3:]:
        d = data[yr]
        core = sum((d.get(k) or 0) for k in ["cash", "net_receivables", "inventory", "prepaid_expenses"])
        assets = d.get("total_assets")
        if assets and assets > 0:
            core_parts.append(core / assets * 100)
    if core_parts:
        avg_core = sum(core_parts) / len(core_parts)
        parts.append(f"核心经营资产（货币资金+应收+预付+存货）占总资产{avg_core:.2f}%")

    avg_prod = _avg("production_intensity")
    if avg_prod is not None:
        if avg_prod > 40:
            parts.append(f"产能力度{avg_prod:.2f}%，属于重资产型企业——产能投入大，折旧摊销压力大。")
        else:
            parts.append(f"产能力度{avg_prod:.2f}%，属于轻资产型企业——以技术、品牌或渠道驱动为主，资本支出压力小，灵活性强。")

    if latest_focus is not None:
        if latest_focus > 50:
            parts.insert(-1, "业务高度专注。")
        else:
            parts.insert(-1, "资产配置相对分散。")

    invest_text = "".join(parts) if parts else "数据不足以做出判断。"
    conclusions.append({"icon": "📊", "title": "投资角度", "text": invest_text})

    # ===== 二、筹资角度 =====
    parts = []
    avg_interest = _avg("interest_debt_ratio")
    if avg_interest is not None:
        parts.append(f"有息负债占总资产{avg_interest:.2f}%")

    # 杠杆水平
    avg_dta = _avg("debt_to_asset_ratio")
    if avg_dta is not None:
        if avg_dta >= 70:
            parts.append(f"杠杆水平处于较高区间。")
        elif avg_dta >= 50:
            parts.append(f"杠杆水平处于中等区间。")
        elif avg_dta >= 30:
            parts.append(f"杠杆水平较低。")
        else:
            parts.append(f"杠杆水平很低。")

    # 经营负债占比
    avg_op = _avg("operating_debt_ratio")
    if avg_op is not None:
        parts.append(f"经营负债（应付+预收+合同负债等）占总资产{avg_op:.2f}%，体现了对上游供应商和下游客户的资金占用能力。")

    # 流动/速动比率
    avg_cr = _avg("current_ratio")
    avg_qr = _avg("quick_ratio")
    cr_parts = []
    if avg_cr is not None:
        cr_parts.append(f"流动比率{avg_cr:.2f}")
    if avg_qr is not None:
        cr_parts.append(f"速动比率{avg_qr:.2f}")
    if cr_parts:
        parts.append(" ".join(cr_parts) + "，短期偿债能力" +
                      ("较强。" if (avg_cr or 0) > 1.5 else "尚可。" if (avg_cr or 0) > 1 else "偏弱。"))

    fund_text = "".join(parts) if parts else "数据不足以做出判断。"
    conclusions.append({"icon": "💰", "title": "筹资角度", "text": fund_text})

    # ===== 三、经营角度 =====
    parts = []
    avg_gm = _avg("gross_margin")
    if avg_gm is not None:
        if avg_gm >= 40:
            parts.append(f"毛利率{avg_gm:.2f}%偏高，以技术壁垒或品牌溢价为核心竞争力。")
        elif avg_gm >= 20:
            parts.append(f"毛利率{avg_gm:.2f}%适中，行业有一定竞争但成本管控有效。")
        else:
            parts.append(f"毛利率{avg_gm:.2f}%偏低，以规模效应或成本管控为核心竞争力。")

    avg_ros = _avg("ros")
    if avg_ros is not None:
        parts.append(f"销售净利率{avg_ros:.2f}%")

    if len(parts) > 1:
        parts[-1] = parts[-1].rstrip("。") + "，盈利空间" + ("较厚。" if (avg_ros or 0) > 10 else "较薄。")

    avg_roe = _avg("roe")
    roe_note_latest = None
    for yr in reversed(years):
        if dims[yr].get("roe_note"):
            roe_note_latest = dims[yr]["roe_note"]
            break
    if avg_roe is not None:
        note_str = ""
        if roe_note_latest:
            note_str = f"({roe_note_latest})"
        parts.append(f"加权平均ROE为{avg_roe:.2f}%{note_str}，资本回报处于" +
                      ("优秀水平。" if avg_roe > 15 else "良好水平。" if avg_roe > 8 else "一般水平。"))

    avg_ocf = _avg("ocf_to_net_income")
    if avg_ocf is not None:
        parts.append(f"经营现金流/净利润为{avg_ocf:.2f}%，现金流与利润匹配度" +
                      ("较高。" if avg_ocf > 90 else "尚可。" if avg_ocf > 60 else "偏低。"))

    operate_text = "".join(parts) if parts else "数据不足以做出判断。"
    conclusions.append({"icon": "📈", "title": "经营角度", "text": operate_text})

    # ===== 四、规模角度 =====
    parts = []
    latest_rev, rev_yr = _data_latest("total_revenue")
    if latest_rev is not None:
        rev_b = latest_rev / 1e9
        if rev_b >= 2000:
            scale_cat = "超大型企业"
        elif rev_b >= 500:
            scale_cat = "大型企业"
        elif rev_b >= 50:
            scale_cat = "中型企业"
        else:
            scale_cat = "小型企业"
        parts.append(f"营收规模{rev_b:.2f}亿美元，处于{scale_cat}体量。")

    latest_ni, ni_yr = _data_latest("net_income")
    avg_ni_margin = None
    ni_margins = []
    for yr in years:
        r = data[yr].get("total_revenue")
        n = data[yr].get("net_income")
        if r and n and r > 0:
            ni_margins.append(n / r * 100)
    if ni_margins:
        avg_ni_margin = sum(ni_margins) / len(ni_margins)

    if latest_ni is not None:
        ni_b = latest_ni / 1e9
        parts.append(f"净利润{ni_b:.2f}亿")

    if avg_ni_margin is not None:
        parts[-1] = parts[-1].rstrip("。") + f"，净利率约{avg_ni_margin:.1f}%。"

    latest_assets, assets_yr = _data_latest("total_assets")
    if latest_assets is not None:
        assets_b = latest_assets / 1e9
        parts.append(f"总资产{assets_b:.2f}亿美元")

        if latest_rev and latest_rev > 0:
            turnover = latest_rev / latest_assets
            if turnover > 1:
                match_desc = "资产周转较快。"
            elif turnover > 0.5:
                match_desc = "资产周转中等。"
            else:
                match_desc = "资产周转偏慢。"
            parts[-1] += f"，资产体量与营收规模" + ("匹配。" if 0.8 < turnover < 1.5 else "基本匹配。" if 0.5 < turnover < 2 else match_desc)

    scale_text = "".join(parts) if parts else "数据不足以做出判断。"
    conclusions.append({"icon": "🏢", "title": "规模角度", "text": scale_text})

    return conclusions


def compute_life_cycle(data, years):
    """生命周期判断"""
    revenues = []
    for yr in years:
        rev = data[yr]["total_revenue"]
        if rev is not None:
            revenues.append(rev)

    if len(revenues) < 2:
        return "数据不足，无法判断生命周期"

    if revenues[-1] and revenues[0] and revenues[-1] != 0:
        n = len(revenues) - 1
        cagr = ((revenues[0] / revenues[-1]) ** (1 / n) - 1) * 100
    else:
        cagr = None

    if len(revenues) >= 2 and revenues[1] and revenues[1] != 0:
        recent_growth = (revenues[0] - revenues[1]) / abs(revenues[1]) * 100
    else:
        recent_growth = None

    conclusion = ""
    if cagr is not None:
        conclusion += f"5年营收CAGR: {cagr:.2f}%"
    if recent_growth is not None:
        conclusion += f"; 最近1年增速: {recent_growth:.2f}%"

    if cagr is not None:
        if cagr > 15 and (recent_growth is None or recent_growth > 20):
            conclusion += " → 成长期：营收快速增长，处于扩张阶段。"
        elif cagr > 0:
            conclusion += " → 成熟期：增速稳定，关注盈利质量和分红能力。"
        else:
            conclusion += " → 调整/转型期：营收收缩，关注转型方向和现金流安全。"

    return conclusion


def generate_report(ticker):
    """主函数：输入ticker，生成完整四维分析报告"""
    stock_info = get_stock_info(ticker)
    data, ratios, years = fetch_financial_data(ticker)
    dimensions = compute_four_dimensions(data, ratios, years)
    lifecycle = compute_life_cycle(data, years)
    edgar_link = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=10-K"

    # 四个维度的5年数据表
    dim_tables = build_dim_tables(dimensions, years)

    # 年度分析结论（四个角度的文字分析）
    annual_conclusions = build_annual_conclusion(data, dimensions, years)

    latest_ratios = {}
    for k, v in ratios.items():
        if v is not None:
            latest_ratios[k] = round(v, 4) if isinstance(v, float) else v

    return {
        "ticker": ticker,
        "stock_info": stock_info,
        "years": years,
        "data": data,
        "dimensions": dimensions,
        "ratios": latest_ratios,
        "lifecycle": lifecycle,
        "edgar_link": edgar_link,
        "dim_tables": dim_tables,
        "annual_conclusions": annual_conclusions,
    }


def format_report_text(report):
    """将报告格式化为纯文本"""
    si = report["stock_info"]
    years = report["years"]

    lines = []
    lines.append(f"{si['name']} ({report['ticker']}) 四维分析报告")
    lines.append(f"行业: {si['industry']} | 板块: {si['sector']} | 国家: {si['country']}")
    lines.append(f"SEC EDGAR核实链接: {report['edgar_link']}")
    lines.append("")

    # 四个维度5年数据表
    for dk in ["invest", "fund", "operate", "scale"]:
        dt = report["dim_tables"][dk]
        lines.append("=" * 50)
        lines.append(dt["title"])
        lines.append("-" * 40)

        header = "指标"
        for yr in years:
            header += f"  {yr}"
        lines.append(header)

        for row in dt["rows"]:
            line = row["label"]
            for yr in years:
                val = row["values"].get(yr, "-")
                line += f"  {val}"
                if row.get("roe_note") and row.get("roe_note", {}).get(yr):
                    line += "(⚠)"
            lines.append(line)
        lines.append("")

    # 年度分析结论
    lines.append("")
    lines.append("=" * 50)
    lines.append("年度分析结论")
    lines.append("=" * 50)

    for ac in report["annual_conclusions"]:
        lines.append("")
        lines.append(f"{ac['icon']} {ac['title']}")
        lines.append(ac["text"])

    lines.append("")
    lines.append("-" * 50)
    lines.append(f"生命周期判断: {report['lifecycle']}")

    if report["ratios"]:
        lines.append("")
        lines.append("当前最新关键比率(来自Yahoo Finance)")
        label_map = {
            "roe": "ROE", "gross_margin": "毛利率", "operating_margin": "营业利润率",
            "current_ratio": "流动比率", "quick_ratio": "速动比率",
            "debt_to_equity": "负债/权益比", "revenue_growth": "营收增速",
            "earnings_growth": "利润增速", "dividend_yield": "股息率",
            "payout_ratio": "派息率", "beta": "Beta", "pe_ratio": "PE(TTM)",
            "price_to_book": "PB", "enterprise_value": "企业价值",
        }
        pct_fields = ["roe", "gross_margin", "operating_margin", "revenue_growth",
                      "earnings_growth", "dividend_yield", "payout_ratio"]
        for k, v in report["ratios"].items():
            label = label_map.get(k, k)
            if isinstance(v, float) and k in pct_fields:
                lines.append(f"  {label}: {v*100:.2f}%")
            elif k == "enterprise_value" and isinstance(v, (int, float)):
                lines.append(f"  {label}: {v/1e9:.2f}亿美元")
            else:
                lines.append(f"  {label}: {v}")

    return "\n".join(lines)
