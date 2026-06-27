"""
美股财报四维分析 - Flask后端
"""

from flask import Flask, render_template, jsonify, request, send_file
from analyzer import generate_report, format_report_text
from pdf_generator import generate_pdf_report
import traceback
import os
import tempfile

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    ticker = request.json.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "请输入美股代码"}), 400

    try:
        report = generate_report(ticker)
        text = format_report_text(report)
        return jsonify({
            "success": True,
            "ticker": ticker,
            "stock_info": report["stock_info"],
            "report_text": text,
            "years": report["years"],
            "dimensions": report["dimensions"],
            "data": report["data"],
            "dim_tables": report["dim_tables"],
            "annual_conclusions": report["annual_conclusions"],
            "lifecycle": report["lifecycle"],
            "edgar_link": report["edgar_link"],
            "ratios": report["ratios"],
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"分析失败: {str(e)}"}), 500


@app.route("/api/quick", methods=["GET"])
def quick_analyze():
    """快速分析 - GET方式"""
    ticker = request.args.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "请输入美股代码"}), 400

    try:
        report = generate_report(ticker)
        text = format_report_text(report)
        return jsonify({
            "success": True,
            "report_text": text,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export-pdf", methods=["POST"])
def export_pdf():
    """导出PDF报告"""
    ticker = request.json.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "请输入美股代码"}), 400

    try:
        # 生成分析报告
        report = generate_report(ticker)
        
        # 创建临时PDF文件
        temp_dir = tempfile.gettempdir()
        pdf_filename = f"{ticker}_analysis_report.pdf"
        pdf_path = os.path.join(temp_dir, pdf_filename)
        
        # 生成PDF
        generate_pdf_report(report, pdf_path)
        
        # 返回PDF文件
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=pdf_filename,
            mimetype='application/pdf'
        )
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"PDF生成失败: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
