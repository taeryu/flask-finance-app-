from flask import Flask, render_template, request, send_file, flash, jsonify
import pandas as pd
import requests
import urllib.parse
import os
import math

app = Flask(__name__)
app.secret_key = "your_secret_key"  # flash 메시지를 위해 필요

# 📌 OpenDART API 기본 URL
BASE_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
API_KEY = "d0c1aca809d67415a6a14e027f2c320b898b94fb"

BASE_URL_DISCLOSURES = "https://opendart.fss.or.kr/api/list.json"

# 📌 기업 코드 목록이 들어 있는 엑셀 파일 경로
EXCEL_PATH = os.path.join(os.getcwd(), "corporate_code.xlsx")

if not os.path.exists(EXCEL_PATH):
    raise FileNotFoundError(f"❌ 엑셀 파일을 찾을 수 없습니다: {EXCEL_PATH}")

# 📌 엑셀에서 기업 코드 불러오기 (속도 개선)
df = pd.read_excel(EXCEL_PATH, dtype=str)
df.columns = df.columns.str.strip()
df = df.rename(columns={df.columns[0]: "회사코드", df.columns[1]: "회사명"})
df["회사명_정리"] = df["회사명"].str.replace(" ", "").str.strip()
df["회사코드"] = df["회사코드"].str.zfill(8)  # 8자리 유지

# ✅ 기업 코드 매핑 딕셔너리 생성 (검색 속도 개선)
corp_code_dict = dict(zip(df["회사명_정리"], df["회사코드"]))

def get_corp_code(company_name):
    """회사명을 입력하면 기업 코드를 반환"""
    clean_name = company_name.replace(" ", "").strip()
    return corp_code_dict.get(clean_name)

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

    try:
        response = requests.get(request_url)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생

        data = response.json()
        if data.get("status") == "000":
            return data.get("list", [])
        else:
            print(f"❌ API 오류: {data.get('message', '알 수 없는 오류')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ API 요청 중 오류 발생: {e}")
        return None
    except ValueError:
        print(f"❌ JSON 파싱 오류: {response.text}")
        return None


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        company_name = request.form["company_name"].strip()
        bsns_year = request.form["bsns_year"].strip()
        fs_type = request.form["fs_type"].strip()

        corp_code = get_corp_code(company_name)
        if not corp_code:
            flash("❌ 회사명을 찾을 수 없습니다.", "danger")
            return render_template("index.html")

        data = get_financial_statements(corp_code, bsns_year, "11011", fs_type)
        if not data:
            flash("❌ 재무제표 데이터를 찾을 수 없습니다.", "danger")
            return render_template("index.html")

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


def get_disclosure_list(corp_code, bgn_de, end_de, max_pages=3):
    """기업의 공시 목록을 OpenDART API에서 가져옴"""
    all_data = []

    for page_no in range(1, max_pages + 1):
        params = {
            "crtfc_key": API_KEY,
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "corp_cls": "Y",
            "page_no": str(page_no),
            "page_count": "100"
        }

        request_url = f"{BASE_URL_DISCLOSURES}?" + urllib.parse.urlencode(params)

        try:
            response = requests.get(request_url)
            response.raise_for_status()

            data = response.json()
            if data.get("status") == "000" and "list" in data:
                all_data.extend(data["list"])
            else:
                break
        except requests.exceptions.RequestException as e:
            print(f"❌ API 요청 오류 발생: {e}")
            break

    return all_data

@app.route("/disclosures", methods=["GET", "POST"])
def disclosures():
    disclosures_data = []
    total_pages = 1
    page = int(request.args.get("page", 1))  # ✅ 현재 페이지 번호 (기본값 1)
    per_page = 20  # ✅ 페이지당 20개씩 표시
    company_name = ""
    bgn_de = ""
    end_de = ""

    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        bgn_de = request.form.get("bgn_de", "").strip().replace("-", "")
        end_de = request.form.get("end_de", "").strip().replace("-", "")

        if not company_name or not bgn_de or not end_de:
            return render_template("disclosures.html", error="❌ 모든 입력값을 입력해주세요.", current_page=1, total_pages=1)

        corp_code = get_corp_code(company_name)  # ✅ 직접 구현한 함수 호출
        if not corp_code:
            return render_template("disclosures.html", error="❌ 회사명을 찾을 수 없습니다.", current_page=1, total_pages=1)

        disclosures_data = get_disclosure_list(corp_code, bgn_de, end_de)  # ✅ 직접 구현한 함수 호출

        # ✅ 총 페이지 수 계산
        total_pages = math.ceil(len(disclosures_data) / per_page)

    # ✅ 페이지네이션 처리
    if disclosures_data:
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        disclosures_data = disclosures_data[start_idx:end_idx]

    return render_template("disclosures.html", disclosures=disclosures_data, total_pages=total_pages, current_page=page)

if __name__ == "__main__":
    app.run(debug=True)