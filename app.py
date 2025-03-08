from flask import Flask, render_template, request, send_file
import pandas as pd
import requests
import urllib.parse
import os

app = Flask(__name__)

static_folder = "static"
if not os.path.exists(static_folder):
    os.makedirs(static_folder)

# 📌 OpenDART API 기본 URL
BASE_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
API_KEY = "d0c1aca809d67415a6a14e027f2c320b898b94fb"

# 📌 기업 코드 목록이 들어 있는 엑셀 파일 경로
EXCEL_PATH = "/Users/youngjunlee/Desktop/무제 폴더/기업별 고유번호_230819.xlsx"

# 📌 엑셀에서 기업 코드 불러오기
df = pd.read_excel(EXCEL_PATH, dtype=str)
df.columns = df.columns.str.strip()
df = df.rename(columns={df.columns[0]: "회사코드", df.columns[1]: "회사명"})
df["회사명_정리"] = df["회사명"].str.replace(" ", "").str.strip()
df["회사코드"] = df["회사코드"].str.zfill(8)  # 8자리 유지

def get_corp_code(company_name):
    """회사명을 입력하면 기업 코드를 반환"""
    clean_name = company_name.replace(" ", "").strip()
    result = df[df["회사명_정리"] == clean_name]
    return result.iloc[0]["회사코드"] if not result.empty else None

def get_financial_statements(corp_code, bsns_year, reprt_code, fs_div):
    """기업의 전체 재무제표 데이터를 OpenDART API에서 가져옴"""
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        "bsns_year": bsns_year,
        "reprt_code": reprt_code,
        "fs_div": fs_div
    }
    request_url = f"{BASE_URL}?" + urllib.parse.urlencode(params)
    response = requests.get(request_url)
    return response.json()["list"] if response.status_code == 200 and response.json()["status"] == "000" else None

import os

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        company_name = request.form["company_name"].strip()
        bsns_year = request.form["bsns_year"].strip()
        fs_type = request.form["fs_type"].strip()

        corp_code = get_corp_code(company_name)
        if not corp_code:
            return render_template("index.html", error="❌ 회사명을 찾을 수 없습니다.")

        data = get_financial_statements(corp_code, bsns_year, "11011", fs_type)
        if not data:
            return render_template("index.html", error="❌ 재무제표 데이터를 찾을 수 없습니다.")

        df_financial = pd.DataFrame(data)
        file_suffix = "개별" if fs_type == "OFS" else "연결"
        file_name = f"{company_name}_{bsns_year}_{file_suffix}_재무제표.xlsx"

        # ✅ static 폴더 절대경로 가져오기
        static_folder = os.path.join(os.getcwd(), "static")

        # ✅ static 폴더가 없으면 자동 생성
        if not os.path.exists(static_folder):
            os.makedirs(static_folder)

        # ✅ 파일 저장 경로를 절대경로로 설정
        file_path = os.path.join(static_folder, file_name)
        df_financial.to_excel(file_path, index=False)

        return send_file(file_path, as_attachment=True)

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
