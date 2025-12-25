import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import time
import os
import sys
import json
import requests
from ASetting import access_token


#ให้ปริ้นออก log
sys.stdout.reconfigure(line_buffering=True)



def update_files():

    REPO_DIR = "/home/mir/robot"
    FILES_TO_UPDATE = [
        "auto_news.py",
        "auto_momentum.py",
        "ASetting.py",
        "main.py"]
    
    try:
        #print("...Updating 4 files from GitHub...", flush=True)
        for f in FILES_TO_UPDATE:
            subprocess.run(
                ["git", "-C", REPO_DIR, "fetch", "origin", "main"],
                check=True
            )
            subprocess.run(
                ["git", "-C", REPO_DIR, "checkout", f"origin/main", "--", f],
                check=True
            )
        #print("...Files updated successfully...", flush=True)

    except Exception as e:
        #print(f"...Update files failed: {e}", flush=True)
        send_line_message(access_token, "...ROBOT: update files failed...")


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

def next_time(t,text): #นำเข้าเป็นนาที
    now = datetime.now().replace(microsecond=0) 
    next = str(now + timedelta(minutes = t ))

    print(text+next, flush=True)
    s = t * 60
    time.sleep(s)

def run(x): # 1.NEWS  2.MOMENTUM

    try : 

        if x == 1 :
            # รันสคริปต์ปกติ
            os.system('clear')
            subprocess.run(["/home/mir/env/bin/python","-u", "/home/mir/robot/auto_news.py"])
        
    
        elif x == 2 :
            os.system('clear')
            subprocess.run(["/home/mir/env/bin/python","-u", "/home/mir/robot/auto_momentum.py"])
            os.system('clear')
            next_time(10, '...Next LOOP in ')
   
    except :

        send_line_message(access_token, '...MIR ROBOT WAS STOP BY INTERNET...')



flag_news = "/home/mir/robot/news.flag" #ไฟล์นี้ต้องถูกสร้างใน Auto_news
flag_log = "/home/mir/robot/main.log"

flag_boot = "/home/mir/robot/boot.flag"

# n = news
# r = reboot
set_time = { 3:[30,59,'n'], 6:[30,59,'n'], 11:[0,30,'n'], 15:[30,59,'n'],18:[0,30,'r'], 19:[0,30,'n'], 23:[0,30,'n'] } # ชั่วโมง : [นาทีเริ่ม , นาทีสุดท้าย, งาน]
check_time = list(set_time.keys())


pass_loop = 3

'''
----0330:0359----0630:0659----1100:1130----1530:1559----1900:1930----2300:2330
------------------------------------------------------1800:1859
'''

while True :

    now = datetime.now()
    h = now.hour
    m = now.minute

    if h in check_time :
        x_time = set_time[h]
        start_min = x_time[0] #เวลาเริ่ม
        end_min = x_time[1]   #เวลาหยุด
        work_run = x_time[2]  #ทำงานอะไร

        if work_run == 'n':
            
            #ชั่วโมง + นาที อยู่ในช่วง
            if (start_min <= m <= end_min) :

                if not os.path.exists(flag_news) :  
                    run(1)
                    time.sleep(5)
                     
                else :
                    run(2)
                
            #ชั่วโมงมีแต่ นาทีไม่อยู่ในช่วง
            else :
                # ถ้าเลยเวลาแล้ว ให้ลบ flag_news
                if os.path.exists(flag_news):
                    os.remove(flag_news)

                run(2)
                     
        elif work_run == 'r' :
            
            #ชั่วโมง + นาที อยู่ในช่วง
            if (start_min <= m <= end_min) :
              

                '''
                try :
                    open(flag_boot, "r").close() 
                    run(2)

                except :
                    open(flag_boot, "w").close()

                    #อย่าลบบรรทัดนี้
                    boot = 15
                    print('...'+str(boot)+'s Systems will Reboot', flush=True)
                    time.sleep(boot)

                    os.system("sudo reboot")

                    
                '''

                if not os.path.exists(flag_boot):

                    open(flag_boot, "w").close()  

                    #อย่าลบบรรทัดนี้
                    boot = 15
                    print('...'+str(boot)+'s Systems will Reboot', flush=True)
                    time.sleep(boot)

                    os.system("sudo reboot")

                    print('...All sys pass but not reboot', flush=True)
                
                else:
                    run(2)
                
        
            else :

                # ถ้าเลยเวลาแล้ว ให้ลบ flag_boot + notify เมื่อความต่าง broker มากๆ
                if os.path.exists(flag_boot):
                    os.remove(flag_boot)


                #restart notify flag
                path = Path("/home/mir/robot/")
                files = list(path.rglob("*.notify"))  # rglob = recursive glob
                if len(files) != 0 :

                    # ลบไฟล์ทีละตัว
                    for file in files:
                        try:
                            file.unlink()  # ลบไฟล์
                        except :
                            continue

                run(2)
 
    else :

        # ถ้าเลยเวลาแล้ว ให้ลบ flag_news
        if os.path.exists(flag_news):
            os.remove(flag_news)
        
        # ถ้าเลยเวลาแล้ว ให้ลบ flag_boot
        if os.path.exists(flag_boot):
            os.remove(flag_boot)
        
        #restart notify flag
        path = Path("/home/mir/robot/")
        files = list(path.rglob("*.notify"))  # rglob = recursive glob
        if len(files) != 0 :

            # ลบไฟล์ทีละตัว
            for file in files:
                try:
                    file.unlink()  # ลบไฟล์
                except :
                    continue

        run(2)
    




