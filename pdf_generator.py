"""
美股财报四维分析 - PDF生成模块
使用reportlab生成专业的PDF分析报告
"""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import os
import platform


def register_chinese_font():
    """注册中文字体以支持中文显示"""
    # Windows: 使用系统自带的微软雅黑/黑体
    if platform.system() == "Windows":
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('Chinese', font_path))
                    return 'Chinese'
                except Exception:
                    continue

    # Linux/其他: 使用reportlab内置CJK字体（无需安装字体文件）
    try:
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        return 'STSong-Light'
    except Exception:
        pass

    return 'Helvetica'


def generate_pdf_report(report, output_path):
    """
    生成PDF分析报告
    
    Args:
        report: generate_report()返回的报告字典
        output_path: PDF输出路径
    
    Returns:
        str: 生成的PDF文件路径
    """
    # 注册中文字体
    chinese_font = register_chinese_font()
    
    # 创建PDF文档
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
    )
    
    # 准备样式
    styles = getSampleStyleSheet()
    
    # 中文标题样式
    title_style = ParagraphStyle(
        'ChineseTitle',
        parent=styles['Heading1'],
        fontName=chinese_font,
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    
    # 中文副标题样式
    subtitle_style = ParagraphStyle(
        'ChineseSubtitle',
        parent=styles['Heading2'],
        fontName=chinese_font,
        fontSize=14,
        alignment=TA_LEFT,
        spaceBefore=15,
        spaceAfter=10,
    )
    
    # 中文正文样式
    body_style = ParagraphStyle(
        'ChineseBody',
        parent=styles['BodyText'],
        fontName=chinese_font,
        fontSize=10,
        alignment=TA_LEFT,
    )
    
    # 构建PDF内容
    story = []
    
    # 1. 标题
    ticker = report['ticker']
    stock_info = report['stock_info']
    company_name = stock_info['name']
    
    title = Paragraph(f"{company_name} ({ticker})", title_style)
    story.append(title)
    
    subtitle = Paragraph("美股财报四维分析报告", subtitle_style)
    story.append(subtitle)
    
    # 公司信息
    info_text = f"行业: {stock_info.get('sector', '-')} | 细分行业: {stock_info.get('industry', '-')} | 交易所: {stock_info.get('exchange', '-')}"
    info_para = Paragraph(info_text, body_style)
    story.append(info_para)
    story.append(Spacer(1, 0.5*cm))
    
    # 2. 四个维度的表格
    years = report['years']
    
    for dim_key in ['invest', 'fund', 'operate', 'scale']:
        dim_table = report['dim_tables'][dim_key]
        dim_title = dim_table['title']
        
        # 维度标题
        dim_title_para = Paragraph(f"<b>{dim_title}</b>", subtitle_style)
        story.append(dim_title_para)
        
        # 构建表格数据
        table_data = []
        
        # 表头
        header = ['指标'] + [str(yr) for yr in years]
        table_data.append(header)
        
        # 数据行
        for row in dim_table['rows']:
            row_data = [row['label']]
            
            for yr in years:
                val = row['values'].get(yr)
                
                # 处理None或空值
                if val is None or val == '-':
                    row_data.append('-')
                    continue
                
                # 格式化数值
                try:
                    # 尝试转换为浮点数
                    num_val = float(val) if isinstance(val, str) else val
                    
                    if row.get('unit') == '%':
                        row_data.append(f"{num_val:.2f}%")
                    elif row.get('unit') == '倍':
                        row_data.append(f"{num_val:.2f}")
                    else:
                        # 默认显示为数字
                        if abs(num_val) > 1e8:
                            row_data.append(f"{num_val/1e9:.2f}B")
                        elif abs(num_val) > 1e4:
                            row_data.append(f"{num_val/1e6:.2f}M")
                        else:
                            row_data.append(f"{num_val:.2f}")
                except (ValueError, TypeError):
                    # 如果转换失败，直接显示为字符串
                    row_data.append(str(val))
            
            table_data.append(row_data)
        
        # 创建表格
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), chinese_font),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTNAME', (0, 1), (-1, -1), chinese_font),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(t)
        story.append(Spacer(1, 0.5*cm))
    
    # 3. 年度分析结论
    story.append(PageBreak())
    
    conclusion_title = Paragraph("<b>年度分析结论</b>", subtitle_style)
    story.append(conclusion_title)
    
    for conclusion in report['annual_conclusions']:
        # 结论标题
        conclusion_header = Paragraph(
            f"{conclusion['icon']} <b>{conclusion['title']}</b>",
            body_style
        )
        story.append(conclusion_header)
        story.append(Spacer(1, 0.2*cm))
        
        # 结论文本
        conclusion_text = Paragraph(conclusion['text'], body_style)
        story.append(conclusion_text)
        story.append(Spacer(1, 0.5*cm))
    
    # 4. 生命周期判断
    lifecycle = report.get('lifecycle', '-')
    lifecycle_para = Paragraph(f"<b>生命周期判断:</b> {lifecycle}", body_style)
    story.append(lifecycle_para)
    story.append(Spacer(1, 0.5*cm))
    
    # 5. 市场比率
    ratios = report.get('ratios', {})
    if ratios:
        ratio_title = Paragraph("<b>市场比率</b>", subtitle_style)
        story.append(ratio_title)
        
        ratio_text = f"PE: {ratios.get('pe_ratio', '-')} | PB: {ratios.get('price_to_book', '-')} | Beta: {ratios.get('beta', '-')}"
        ratio_para = Paragraph(ratio_text, body_style)
        story.append(ratio_para)
    
    # 生成PDF
    doc.build(story)
    
    return output_path
