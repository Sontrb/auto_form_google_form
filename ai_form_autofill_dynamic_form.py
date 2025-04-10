import os
from dotenv import load_dotenv
import requests
import re
import json

load_dotenv()

DATA_FILE = "form_info_auto_generate.json"

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
                return None, [], []
            return data['url'], data['accounts'], data.get('question_labels', [])
    except json.JSONDecodeError as e:
        print(f"Lỗi đọc file JSON: {e}")
        return None, [], []
    except FileNotFoundError:
        print(f"Không tìm thấy file: {file_path}")
        return None, [], []

def save_account_data(file_path, url, accounts, question_labels):
    """Lưu dữ liệu, bao gồm nhãn câu hỏi, vào file JSON."""
    data = {
        "url": url,
        "question_labels": question_labels,
        "accounts": accounts
    }
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"Đã cập nhật file {file_path} với nhãn câu hỏi và 10 object mới.")

def string_to_object_list(js_constant):
    """Chuyển dữ liệu JS thành danh sách đối tượng và nhãn câu hỏi."""
    array = json.loads(js_constant)
    objects = []
    labels = []
    for section in array[1][1]:
        if section[4]:
            type = section[3]
            title = section[1]
            labels.append(title)
            object = {'title': title, 'type': type}
            question_list = []
            for tmpe_section in section[4]:
                question = {'entry_id': tmpe_section[0], 'required': tmpe_section[2]}
                if type in [2, 3, 4]:
                    question['options'] = [sub_array[0] for sub_array in tmpe_section[1]]
                elif type == 5:
                    question['options'] = [sub_array[0] for sub_array in tmpe_section[1]]
                    question['min'] = tmpe_section[3][0]
                    question['max'] = tmpe_section[3][1]
                elif type == 7:
                    question['selection_type'] = tmpe_section[11][0]
                    question['columns'] = tmpe_section[3][0]
                    question['options'] = [sub_array[0] for sub_array in tmpe_section[1]]
                question_list.append(question)
            object['questions'] = question_list
            objects.append(object)
    return objects, labels

def generate_empty_accounts(question_labels, num_accounts=10):
    """Tạo 10 object rỗng dựa trên question_labels."""
    empty_accounts = []
    for _ in range(num_accounts):
        account = {}
        for label in question_labels:
            # Giả định mặc định là chuỗi rỗng, sau này có thể tùy chỉnh dựa trên type
            account[label] = ""
        empty_accounts.append(account)
    return empty_accounts

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
            else:
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
                    question['value'] = account_data[title] if account_data[title] else ""
                elif ob['type'] == 4:  # Checkbox
                    value = account_data[title]
                    valid_options = [opt for opt in value if opt in question.get('options', [])] if isinstance(value, list) else []
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
    return None, []

def submit_form(form_url, form_data):
    submit_url = form_url.replace("/viewform", "/formResponse")
    response = requests.post(submit_url, data=form_data)
    if response.status_code == 200:
        print("Đã gửi form thành công!")
    else:
        print(f"Gửi form thất bại. Mã trạng thái: {response.status_code}")
        print(f"Dữ liệu gửi đi: {form_data}")

def main():
    FORM_URL, ACCOUNT_DATA, QUESTION_LABELS = load_account_data(DATA_FILE)
    if not FORM_URL:
        print("Không có URL để xử lý.")
        return

    form, labels = get_form(FORM_URL)
    if not form:
        return

    # Nếu nhãn mới khác nhãn cũ hoặc chưa có accounts, cập nhật file JSON
    if set(labels) != set(QUESTION_LABELS) or not ACCOUNT_DATA:
        if not ACCOUNT_DATA:  # Nếu không có accounts, tạo mới
            ACCOUNT_DATA = generate_empty_accounts(labels)
        save_account_data(DATA_FILE, FORM_URL, ACCOUNT_DATA, labels)
        QUESTION_LABELS = labels

    print("Nhãn câu hỏi từ form:")
    for idx, label in enumerate(QUESTION_LABELS, 1):
        print(f"{idx}. {label}")

    print("\nDữ liệu tài khoản:")
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
                    form_data[f"entry.{question['entry_id']}_year"] = str(value['year']) if value else ""
                    form_data[f"entry.{question['entry_id']}_month"] = str(value['month']) if value else ""
                    form_data[f"entry.{question['entry_id']}_day"] = str(value['day']) if value else ""
                elif ob['type'] == 4:  # Checkbox
                    values = question['value'] if isinstance(question['value'], list) else [question['value']]
                    for value in values:
                        form_data[f"entry.{question['entry_id']}"] = str(value)
                else:
                    form_data[f"entry.{question['entry_id']}"] = str(question['value'])
        submit_form(FORM_URL, form_data)

if __name__ == "__main__":
    main()