import os
from dotenv import load_dotenv
import requests
import re
import json

load_dotenv()

# Đường dẫn tới file dữ liệu
DATA_FILE = "form_info.json"

SECTION_TYPE = ["Trả lời ngắn", "Trả lời chi tiết", "Trắc nghiệm", "Menu thả xuống", "Hộp kiểm", "Thang tuyến tính", "Tiêu đề", "Ô chọn một/ô kiểm", "Phần", "Ngày", "Thời gian", "Hình ảnh", "12", "Tệp"]
REQUIRED_TYPE = ["Không bắt buộc", "Bắt buộc"]
SELECTION_TYPE = ["Ô chọn một", "Ô kiểm"]

def load_account_data(file_path):
    """Tải dữ liệu tài khoản và URL từ file JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'url' not in data or 'accounts' not in data:
                print("File JSON thiếu 'url' hoặc 'accounts'.")
                return None, []
            return data['url'], data['accounts']
    except json.JSONDecodeError as e:
        print(f"Lỗi đọc file JSON: {e}")
        return None, []
    except FileNotFoundError:
        print(f"Không tìm thấy file: {file_path}")
        return None, []

def string_to_object_list(js_constant):
    array = json.loads(js_constant)
    objects = []
    for section in array[1][1]:
        if section[4]:
            type = section[3]
            object = {'title': section[1], 'type': type}
            question_list = []
            for tmpe_section in section[4]:
                question = {}
                tmpe_question = tmpe_section
                question['entry_id'] = tmpe_question[0]
                question['required'] = tmpe_question[2]
                if type in [2, 3, 4]:
                    question['options'] = [sub_array[0] for sub_array in tmpe_question[1]]
                elif type == 5:
                    question['options'] = [sub_array[0] for sub_array in tmpe_question[1]]
                    question['min'] = tmpe_question[3][0]
                    question['max'] = tmpe_question[3][1]
                elif type == 7:
                    question['selection_type'] = tmpe_question[11][0]
                    question['columns'] = tmpe_question[3][0]
                    question['options'] = [sub_array[0] for sub_array in tmpe_question[1]]
                question_list.append(question)
            object['questions'] = question_list
            objects.append(object)
    return objects

def objects_to_result_strings(url, objects):
    result_strings = []
    for ob in objects:
        for question in ob['questions']:
            if 'value' not in question or question['value'] is None:
                continue
            if ob['type'] == 9:  # Ngày
                value = question['value']
                result_strings.append(f"entry.{question['entry_id']}_year={value['year']}")
                result_strings.append(f"entry.{question['entry_id']}_month={value['month']}")
                result_strings.append(f"entry.{question['entry_id']}_day={value['day']}")
            elif ob['type'] == 4:  # Checkbox
                values = question['value'] if isinstance(question['value'], list) else [question['value']]
                for value in values:
                    result_strings.append(f"entry.{question['entry_id']}={value}")
            else:  # Trắc nghiệm, box select, trả lời ngắn
                value = question['value']
                result_strings.append(f"entry.{question['entry_id']}={value}")
    if result_strings:
        return url + "?" + "&".join(result_strings)
    return url + "?"

def set_answers_for_account(form, account_data):
    for ob in form:
        for question in ob['questions']:
            title = ob['title']
            if title in account_data:
                if ob['type'] == 9:  # Ngày
                    question['value'] = account_data[title]
                elif ob['type'] == 4:  # Checkbox
                    valid_options = [opt for opt in account_data[title] if opt in question.get('options', [])]
                    question['value'] = valid_options if valid_options else []
                elif ob['type'] in [2, 3]:  # Trắc nghiệm, box select
                    if account_data[title] in question.get('options', []):
                        question['value'] = account_data[title]
                    else:
                        question['value'] = ""
                else:  # Trả lời ngắn
                    question['value'] = account_data[title]
            else:
                question['value'] = "" if ob['type'] != 4 else []

def get_form(url):
    response = requests.get(url)
    if response.status_code == 200:
        js_constants = re.findall(r'FB_PUBLIC_LOAD_DATA_.*?=(.*?);', response.text)
        if js_constants:
            return string_to_object_list(js_constants[0])
        else:
            print("Không tìm thấy hằng số JS FB_PUBLIC_LOAD_DATA_ trên trang.")
    else:
        print("Không thể lấy được trang web. Mã trạng thái:", response.status_code)
    return None

def submit_form(form_url, form_data):
    submit_url = form_url.replace("/viewform", "/formResponse")
    response = requests.post(submit_url, data=form_data)
    if response.status_code == 200:
        print("Đã gửi form thành công!")
    else:
        print(f"Gửi form thất bại. Mã trạng thái: {response.status_code}")
        print(f"Dữ liệu gửi đi: {form_data}")

def main():
    FORM_URL, ACCOUNT_DATA = load_account_data(DATA_FILE)
    if not FORM_URL or not ACCOUNT_DATA:
        print("Không có URL hoặc dữ liệu tài khoản để xử lý.")
        return

    form = get_form(FORM_URL)
    if not form:
        return

    print("Dữ liệu tài khoản:")
    for idx, account in enumerate(ACCOUNT_DATA, 1):
        print(f"Tài khoản {idx}: {account}")

    for idx, account in enumerate(ACCOUNT_DATA, 1):
        if 'Tên' not in account:
            print(f"Lỗi: Tài khoản {idx} thiếu khóa 'Tên': {account}")
            continue

        print(f"\nXử lý tài khoản {idx}: {account['Tên']}")
        set_answers_for_account(form, account)
        filled_url = objects_to_result_strings(FORM_URL, form)
        print(f"URL điền sẵn cho tài khoản {idx}: {filled_url}")

        form_data = {}
        for ob in form:
            for question in ob['questions']:
                if 'value' not in question or question['value'] is None:
                    continue
                if ob['type'] == 9:  # Ngày
                    value = question['value']
                    form_data[f"entry.{question['entry_id']}_year"] = str(value['year'])
                    form_data[f"entry.{question['entry_id']}_month"] = str(value['month'])
                    form_data[f"entry.{question['entry_id']}_day"] = str(value['day'])
                elif ob['type'] == 4:  # Checkbox
                    values = question['value'] if isinstance(question['value'], list) else [question['value']]
                    for value in values:
                        form_data[f"entry.{question['entry_id']}"] = str(value)
                else:  # Trắc nghiệm, box select, trả lời ngắn
                    form_data[f"entry.{question['entry_id']}"] = str(question['value'])
        submit_form(FORM_URL, form_data)

if __name__ == "__main__":
    main()