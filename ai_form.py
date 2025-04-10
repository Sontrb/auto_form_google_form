import os
from dotenv import load_dotenv
import requests
import re
import json
import google.generativeai as genai

# Tải biến môi trường
load_dotenv()

# Thiết lập URL của Google Form
URL = 'https://docs.google.com/forms/d/e/1FAIpQLSeOTglE4C-L_QOWyrp40JflYyFd0TL6fGL5JiTG8GcgIEBmZA/viewform'

# Thiết lập các phần của lời nhắc (prompt)
PROMPT_PARTS = [
    "Tên: Sun",
    "Giới tính: Nam",
    "Điện thoại: 0912345678",
    "Ngày sinh: {\"year\": 1999,\"month\": 8,\"day\": 19}",
    "Email: xxxx@gmail.com",
    "Địa chỉ: Thành phố Cao Hùng",
    "Sở thích: Vẽ tranh, chơi game",
    "Không cần mở rộng JSON",
    "Trả lời từ các tùy chọn, chọn đáp án, nếu không có thì trả lời \"\"",
    "Thứ tự trả lời phải khớp với thứ tự câu hỏi",
    "Không trả lời được hoặc không biết thì trả lời None",
    "Trả lời tất cả các câu hỏi",
    "Chỉ trả lời từ tùy chọn, nếu không có thì để trống",
    "Trả lời theo thứ tự",
    "Định dạng ví dụ mảng [\"\", \"\", \"\"]",
    "Theo quy tắc của tôi, dựa trên nội dung bạn cung cấp: chỉ trả lời từ tùy chọn có sẵn trong câu hỏi...",
    "Ngày sử dụng định dạng này {\"year\": ,\"month\": ,\"day\": }"
]

SECTION_TYPE = ["Trả lời ngắn", "Trả lời chi tiết", "Trắc nghiệm", "Menu thả xuống", "Hộp kiểm", "Thang tuyến tính", "Tiêu đề", "Ô chọn một/ô kiểm", "Phần", "Ngày", "Thời gian", "Hình ảnh", "12", "Tệp"]
REQUIRED_TYPE = ["Không bắt buộc", "Bắt buộc"]
SELECTION_TYPE = ["Ô chọn một", "Ô kiểm"]

# Chuyển chuỗi thành danh sách đối tượng câu hỏi
def string_to_object_list(js_constant):
    array = json.loads(js_constant)

    objects = []
    for section in array[1][1]:
        if section[4]:
            type = section[3]
            object = {
                'title': section[1],
                'type': type,
            }
            question_list = []
            for tmpe_section in section[4]:
                question = {}
                tmpe_question = tmpe_section
                question['entry_id'] = tmpe_question[0]
                question['required'] = tmpe_question[2]

                if type == 2 or type == 3 or type == 4:
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

# Chuyển danh sách câu hỏi thành chuỗi tham số trả lời
def objects_to_result_strings(url, objects):
    result_strings = []
    for ob in objects:
        for question in ob['questions']:
            if ob['type'] == 9:
                value_object = question['value']
                if 'year' in value_object and value_object['year']:
                    result_strings.append(f"entry.{question['entry_id']}_year={value_object['year']}")
                if 'month' in value_object and value_object['month']:
                    result_strings.append(f"entry.{question['entry_id']}_month={value_object['month']}")
                if 'day' in value_object and value_object['day']:
                    result_strings.append(f"entry.{question['entry_id']}_day={value_object['day']}")
            elif ob['type'] == 10:
                value_object = question['value']
                if 'hour' in value_object and value_object['hour']:
                    result_strings.append(f"entry.{question['entry_id']}_hour={value_object['hour']}")
                if 'minute' in value_object and value_object['minute']:
                    result_strings.append(f"entry.{question['entry_id']}_minute={value_object['minute']}")
            else:
                if 'value' in question and question['value']:
                    if type(question['value']) == list:
                        for value in question['value']:
                            result_strings.append(f"entry.{question['entry_id']}={value}")
                    else:
                        result_strings.append(f"entry.{question['entry_id']}={question['value']}")

    result = "&".join(result_strings)
    result = url + "?" + result
    return result

# Chuyển đối tượng thành câu hỏi văn bản để dễ hỏi AI
def objects_to_string(list):
    string_list = []
    for ob in list:
        type = ob['type']
        for question in ob['questions']:
            text = f"Câu hỏi:{ob['title']}"
            text += f"\nLoại:{SECTION_TYPE[ob['type']]}"
            text += f"\nBắt buộc:{REQUIRED_TYPE[question['required']]}"

            if type == 2 or type == 3 or type == 4:
                text += f"\nTùy chọn:{question['options']}"
            elif type == 5:
                text += f"\nTùy chọn:{question['options']}"
                text += f"\nGiá trị nhỏ nhất:{question['min']}"
                text += f"\nGiá trị lớn nhất:{question['max']}"
            elif type == 7:
                text += f"\nĐề mục:{question['columns']}"
                text += f"\nLoại tùy chọn:{SELECTION_TYPE[question['selection_type']]}"
                text += f"\nTùy chọn:{question['options']}"
            string_list.append(text)
    return "\n\n".join(string_list)

# Gán đáp án vào mảng câu hỏi
def set_answer(topic_list, answer_list):
    for ob in topic_list:
        for question in ob['questions']:
            answer = answer_list.pop(0)
            question['value'] = answer

# Lấy thông tin Google Form
def get_form(url):
    response = requests.get(url)

    # Kiểm tra xem có lấy được nội dung trang web thành công không
    if response.status_code == 200:
        # Sử dụng biểu thức chính quy để trích xuất hằng số JS
        js_constants = re.findall(r'FB_PUBLIC_LOAD_DATA_.*?=(.*?);', response.text)

        if js_constants:
            # Trả về danh sách câu hỏi từ hằng số JS
            for js_constant in js_constants:
                list = string_to_object_list(js_constant)
                return list
        else:
            print("Không tìm thấy hằng số JS FB_PUBLIC_LOAD_DATA_ trên trang.")
    else:
        print("Không thể lấy được trang web. Mã trạng thái:", response.status_code)

def main():
    # Lấy khóa API từ biến môi trường
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Chưa thiết lập biến môi trường GEMINI_API_KEY")

    genai.configure(api_key=api_key)

    # Thiết lập cấu hình mô hình
    generation_config = {
        "temperature": 0.9,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 2048,
    }

    safety_settings = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
    ]

    model = genai.GenerativeModel(
        model_name="gemini-1.0-pro",
        generation_config=generation_config,
        safety_settings=safety_settings
    )

    form = get_form(URL)
    form_string = objects_to_string(form)
    
    # Thêm chuỗi form vào các phần của lời nhắc
    prompt_parts = PROMPT_PARTS + [form_string + "\nTrả lời tất cả câu hỏi bằng định dạng JSON mảng"]
    
    print("\n" + form_string + "\n")
    response = model.generate_content(prompt_parts)
    print(response.text)
    
    parsed_data = json.loads(response.text)
    set_answer(form, parsed_data)
    print("URL tự động điền Google Form:\n" + objects_to_result_strings(URL, form))

if __name__ == "__main__":
    main()