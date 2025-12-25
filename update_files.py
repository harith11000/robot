import requests
import os
import json
from ASetting import access_token

def send_line_message(token, text):
    url = "https://api.line.me/v2/bot/message/broadcast"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    payload = {
        "messages": [
            {"type": "text", "text": text}
        ]
    }

    #ส่งข้อความ
    response = requests.post(url, headers=headers, data=json.dumps(payload))

# โฟลเดอร์ปลายทาง
DEST_DIR = "/home/mir/robot"

# ไฟล์ที่ต้องการดึง
FILES = [
    "auto_news.py",
    "auto_momentum.py",
    "ASetting.py",
    "main.py"
]

# Base URL ของ raw file บน GitHub
BASE_URL = "https://raw.githubusercontent.com/harith11000/robot/main/"

for f in FILES:
    url = BASE_URL + f
    dest_path = os.path.join(DEST_DIR, f)

    try:
        r = requests.get(url)
        r.raise_for_status()

        # เขียนไฟล์ลงโฟลเดอร์
        with open(dest_path, "wb") as file:
            file.write(r.content)
            
        print("...Update files successfully", flush=True)

    except Exception as e:
        print("...Update files failed", flush=True)
        send_line_message(access_token, "...ROBOT: update files failed")
