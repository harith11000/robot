from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import pandas as pd
import numpy as np
from datetime import datetime,timedelta 
import json
import os
import csv
import firebase_admin
from firebase_admin import db, credentials
from deep_translator import GoogleTranslator

from ASetting import mark_city, access_token, limit_max_notify

import random, time
from selenium.webdriver.common.action_chains import ActionChains

import json
import subprocess
from pathlib import Path
import sys

import platform
from selenium_stealth import stealth

import requests

#region จัดการระบบ

#ทำให้ปริ้นแสดงผล
sys.stdout.reconfigure(line_buffering=True)

#ตรวจสอบระบบ ที่ใช้ ทำงาน
this_system = platform.system().lower()

#เอาใว้บอกว่ารันโค้ด สำเร็จแล้ว ไม่ต้องมารันอีกครั้ง
flag_news = "/home/mir/robot/news.flag"

#endregion

#region FIREBASE

## authenticate to firebase
cred = credentials.Certificate("fire_base_admin.json")

firebase_admin.initialize_app(cred, {"databaseURL": "https://robot-mir-79bc9-default-rtdb.asia-southeast1.firebasedatabase.app/"})

# creating reference to root node
ref = db.reference("/")


#endregion

#เก็บข้อมูล
articles = []

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
    #response = requests.post(url, headers=headers, data=json.dumps(payload))

def make_old_kw(): #ถ้าเริ่มการ บันทึกไฟล์ไหม่ให้ รันไฟล์นี้

    from ASetting import base_keywords
    
    log_kw = open('log_keywords'+'.csv','w')
        
    catagory = list(base_keywords.keys())
    for k in range(len(catagory)) :
    
        key = catagory[k]

        if k == 0 : 
            log_kw.writelines(key+'\n')
        else : 
            log_kw.writelines('\n'+key+'\n')


        kw_score = list(base_keywords[key].items())

        for kws in kw_score :

            #log_kw.writelines(str(kws[0])+','+str(kws[1])+'\n')
            log_kw.writelines(str(kws[0])+','+str(kws[1])+'\n')

    log_kw.close()

def update_kw(update_keywords): 

    log_kw = open('log_keywords'+'.csv','w')
        
    catagory = list(update_keywords.keys())

    for k in range(len(catagory)) :
    
        key = catagory[k]

        if k == 0 : 
            log_kw.writelines(key+'\n')
        else : 
            log_kw.writelines('\n'+key+'\n')


        kw_score = list(update_keywords[key].items())

        for kws in kw_score :

            #log_kw.writelines(str(kws[0])+','+str(kws[1])+'\n')
            log_kw.writelines(str(kws[0])+','+str(kws[1])+'\n')

    log_kw.close()

def read_kw():

    rec_kw = {}
    mark_last_kw = [] #ทำให้รูว่าล่าสุดอยู่ กลุ่มไหน

    read_log = open("log_keywords.csv",'r').readlines()

    for rl in read_log :

        data = rl.split('\n')[0]
        
        if data != '' :
            if (',' not in data) : 
                rec_kw[data] = {}
                mark_last_kw.append(data)

            elif (',' in data) :
                sep_data = str(data).split(',')
                
                key = sep_data[0]
                val = sep_data[1]

                last_kw = mark_last_kw[-1]

                rec_kw[last_kw][key] = float(val)

    return rec_kw

def scroll_page_smooth(driver, step=500, delay=1, max_scrolls=20, timeout=5):
   
    """
    เลื่อนหน้าจอลงทีละ step px จนสุด หรือครบ max_scrolls
    timeout = เวลารอสูงสุดเมื่อหน้าไม่ขยับ (วินาที)
    """
    #"🚀 เริ่มเลื่อนหน้าจอ...
    last_height = driver.execute_script("return document.body.scrollHeight")
    still_count = 0  # นับจำนวนรอบที่หน้าไม่เปลี่ยนความสูง
   

    for i in range(max_scrolls):
        driver.execute_script(f"window.scrollBy(0, {step});")
        time.sleep(delay)
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        if new_height == last_height:
            still_count += 1
            if still_count * delay >= timeout:
                #(f"✅ หยุดเลื่อน: หน้าคงที่เกิน {timeout} วินาที")
                break
        else:
            still_count = 0  # รีเซ็ตเมื่อหน้ามีการเปลี่ยนแปลง

        #(f"เลื่อนครั้งที่ {i+1}: ความสูง {new_height}")
        last_height = new_height
    
    #("🏁 จบการเลื่อนหน้าแล้ว")

def analyze_title(title, keywords):
    keep_point = 0.0001
    score = 0
    matched = []        
          
    #ความลึกที่ 2/3
    list_key = list(keywords.keys())

    #catagory news ที่อยู่ใน ตัวแปล keywords
    for list_catagory in list_key:
        
        dict_wordr_org = keywords[list_catagory]

        #ปรับ keywords ให้เป็นตัวเล็กทั้งหมด
        dict_words_small = {k.lower(): in_catagory_org for k, in_catagory_org in dict_wordr_org.items()}

        kw_use_catagory = list(dict_words_small.keys())



        #--------------รวม keyword แบบตัวเดียว ในข่าว ที่มีตามที่เรา setใว้
        title_single = (title.lower()).split(' ') #kwyword แบบตัวเดียว

        #บันทัดนี้จะรวม เฉพาะ ตัวที่เหมือนกัน ใน list
        same_one_kw = list(set(title_single) & set(kw_use_catagory))
       
        for match_one_kw in same_one_kw :
            
            #ดึงค่าเก่ามา แล้ว + 0.0001 ค่านี้เราตั้งเอง
            value_up = float('%.4f'%((dict_words_small[match_one_kw]) + keep_point))

            #อัพเดทที่ dick
            keywords[list_catagory][match_one_kw] = value_up
            
            #รวม score
            score += value_up

            #รวม word ที่ตรงกัน
            matched.append(match_one_kw+str(value_up))
        


        #--------------รวม keyword แบบคู่ ในข่าว ที่มีตามที่เรา setใว้
        title_two = []
        for m in range(len(title_single)-1): #-1เพราะไม่ให้ถึงตัวสุดท้าย 12 23 34 45
            title_two.append(title_single[m]+' '+title_single[m+1])
            
        same_two_kw = list(set(title_two) & set(kw_use_catagory))

        for match_two_kw in same_two_kw :
            
            value_up = float('%.4f'%((dict_words_small[match_two_kw]) + keep_point))

            #อัพเดทที่ dick
            keywords[list_catagory][match_two_kw] = value_up
            
            #รวม score
            score += value_up

            #รวม word ที่ตรงกัน
            matched.append(match_two_kw+str(value_up))

    joint = ' '.join(matched)

    return score, joint, keywords

def find_head(soup_in,script,typex,main,sub) :
    
    ''' ตัวอย่าง
    for head in soup.find_all("script", type="application/ld+json"):

    try:
        print(4.1)
        data_in = json.loads(head.string)
        data_head = data_in['mainEntity']['itemListElement']
        print(4.2)
        for dx in data_head :
            url = str(dx['url'])
            clean_url = url.replace("https://www.reuters.com/", "")

            clean_slash = clean_url.split('/')


            if len(clean_slash) == 3 :
                clean_text = clean_slash[1]

            elif len(clean_slash) == 4 :
                clean_text = clean_slash[2]

        
            # แยกเนื้อข่าว กับ วันที่
            text_and_date = clean_text.split('-')

            #วันที่ข่าว
            time_text = '-'.join(text_and_date[-3:])
            time_news = datetime.strptime(str(time_text+' 00:00:00'), '%Y-%m-%d  %H:%M:%S') 

            #หัวข้อข่าว
            title_range = text_and_date[:-3]
            title_text = ' '.join(title_range)

            if title_text not in articles :
                articles.append(time_news)
                articles.append(title_text)
                articles.append(url)
        print(4.3)


        count_news_in = data_in['mainEntity']['numberOfItems']
        no_news += count_news_in
        print(f'number news == {count_news_in}')

    except :
        continue
    '''

    for head in soup_in.find_all(script, type=typex):
    
        try:
            
            data_in = json.loads(head.string)
            data_head = data_in[main][sub]

        except :
            continue
    
    return data_head

def clean_text(a,b):

    a_no_stop = a.replace('.', ' ')
    a_no_com = a_no_stop.replace(',', '')
    a_no_cod = a_no_com.replace('"', '')

    b_no_stop = b.replace('.', ' ')
    b_no_com = b_no_stop.replace(',', '')
    b_no_cod = b_no_com.replace('"', '')

    good_text = a_no_cod+' , '+b_no_cod

    return good_text

def open_book(book_name) : #ฟังชั่นนี้นี้เอาใว้ต่อยอด แต่ตอนนี้ไม่ได้ใช้
   
    #สำหรับค้นหา + เปิด หน้า bookmark
    # ปรับชื่อตามที่ต้องการจะหา
    TARGET_TITLE = book_name  # ชื่อ bookmark ที่บันทึกไว้

    # เป็นไปได้ว่า Chromium เก็บที่ต่างกัน ลองเช็ครายการนี้ก่อน
    bookmark_paths = [
        Path.home() / ".config" / "chromium" / "Default" / "Bookmarks",
        Path.home() / ".config" / "chromium-browser" / "Default" / "Bookmarks",
        Path.home() / ".config" / "google-chrome" / "Default" / "Bookmarks",
    ]

    bookmarks_file = None
    for p in bookmark_paths:
        if p.exists():
            bookmarks_file = p
            break

    if not bookmarks_file:
        print("ไม่พบไฟล์ Bookmarks ของ Chromium ในตำแหน่งที่คาดไว้.")
        print("ตรวจสอบ path ที่เก็บ Bookmarks และแก้ใน bookmark_paths.")
        sys.exit(1)

    with open(bookmarks_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ฟังก์ชันค้นหา bookmark แบบ recursive (ในทุกโฟลเดอร์)
    def find_bookmark(node, title):
        results = []
        t = node.get("type")
        if t == "url" and node.get("name") == title:
            return [node.get("url")]
        # ถ้าเป็น folder จะมี children
        for key in ("children",):
            if key in node:
                for child in node[key]:
                    results += find_bookmark(child, title)
        # บางเวอร์ชันเก็บใน roots
        for k in ("roots",):
            if k in node:
                for root_key in node[k]:
                    root = node[k][root_key]
                    results += find_bookmark(root, title)
        return results

    urls = find_bookmark(data, TARGET_TITLE)

    if not urls:
        print(f"ไม่พบ bookmark ชื่อ '{TARGET_TITLE}' ในไฟล์ {bookmarks_file}")
        sys.exit(1)

    # เลือก url แรกที่พบ
    url_to_open = urls[0]
    print("เปิด:", url_to_open)

    # เปิดด้วย chromium profile เดิม (เพื่อให้ใช้ cookies / session)
    CHROMIUM_BIN = "/usr/bin/chromium"  # ปรับตามเครื่อง
    USER_DATA_DIR = str(Path.home() / ".config" / "chromium")  # ใช้ profile ของผู้ใช้
    PROFILE_DIR = "Default"  # หรือ Profile 1, Profile 2 ถ้าใช้หลายโปรไฟล์

    cmd = [
        CHROMIUM_BIN,
        f"--user-data-dir={USER_DATA_DIR}",
        f"--profile-directory={PROFILE_DIR}",
        url_to_open
    ]

    # ถ้าอยากปิด headless/automation ให้แน่ใจว่าไม่ได้ใส่ --headless
    subprocess.Popen(cmd)

def get_data(driver, news_loop_round):

    loading = True

    count_high = []

    while loading == True :
        
        #region---------------------ทำพฤติกรรมให้คล้ายมนุษย์

        try :
           
            # small mouse move (ActionChains)
            actions = ActionChains(driver)
            actions.move_by_offset(random.randint(10,300), random.randint(10,200)).perform()
          
            time.sleep(random.uniform(0.5,2))

            #เลื่อนจอเล็กน้อย
            scroll_page_smooth(driver, step=300, delay=random.uniform(1,2), max_scrolls=5)
            time.sleep(random.uniform(3,6))
          
            #---------------------------------------------
           
            #random เวลา เบรค
            time.sleep(random.uniform(2,5))

            # small mouse move (ActionChains)
            actions = ActionChains(driver)
            actions.move_by_offset(random.randint(10,200), random.randint(10,100)).perform()

            #random เวลา เบรค
            time.sleep(random.uniform(2,5))

        except :
            pass


        #endregion
        
        #region----------------------เข้าถึงข้อมูล

        print(f'......Get news', flush=True)
        
        try :

            # รอให้ FeedListItem อย่างน้อย 1 ข่าวโหลด
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "li[data-testid='FeedListItem']")))
        
        except :
            print(f'.........Bad Get news...', flush=True)
            loading = False
            break

        # ดึงข่าวทั้งหมด            
        html = driver.execute_script("return document.body.innerHTML;")
        soup = BeautifulSoup(html, 'html.parser')
        
        #เข้าไปยังส่วนที่มีข่าว
        feed_items = soup.select("li[data-testid='FeedListItem']")
        
        for item in feed_items:
            
            last_update = item.select_one("time") #24 mins ago
            lastx = last_update.get_text(strip=True)

            datetime_update = last_update["datetime"] # เป็นรูปแบบ '%Y-%m-%dT%H:%M:%S.%fZ'
            
            #มี div หลายตัวเลยใช้การเรียกชื่อแทน data-testid='Title'
            title_tag = item.select_one("div[data-testid='Title']")
            title = title_tag.get_text(strip=True)
            
            desc_tag = item.select_one("p[data-testid='Description']")
            description = desc_tag.get_text(strip=True)

            url_tag = item.select_one("div[data-testid='Title']")
            url_tagx = url_tag.select_one("a")
            url_use = str(url_tagx['href'])

            #ตัดองประกอบอื่นๆ
            text_sum = clean_text(title,description)


            if text_sum not in articles :
                
                try :time_news = datetime.strptime(str(datetime_update), '%Y-%m-%dT%H:%M:%SZ') 
                except : time_news = datetime.strptime(str(datetime_update),  '%Y-%m-%dT%H:%M:%S.%fZ') 
                
                timestamp =  ( (time_news) + timedelta(hours=7) ).replace(microsecond=0)

                articles.append(str(timestamp))
                articles.append(lastx) 
                articles.append(text_sum)
                articles.append('https://www.reuters.com'+url_use)

        print(f'.........Good...', flush=True)
   
        

        #endregion     
        
        #region-----------------------หยุดเมื่อ loop ครบ ตามจำนวน รอบที่กำหนด
        #ออกจากloop จะไม่สามารถ เอาข่าวภายในวันแล้วออกได้เพราะ ข่าว มันไม่ได้เรียงลำดับเวลา
        if news_loop_round  == 0 :
            print(f'......End setting page', flush=True)
            break
         #endregion
   
        #region-----------------------เลื่อนหน้าจอ ลงล่าง
        print(f'......Scroll news', flush=True)
        scroll_page_smooth(driver)
        
        #random เวลา เบรค
        time.sleep(random.uniform(3,8))

        #endregion
      
        #region-----------------------ค้นหาปุ่ม โหลดหน้าเพิ่ม
        print(f'......Put load_more or stop', flush=True)

        try:
    
            load_more = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="FeedContentLoadMore"]')
            
            driver.execute_script("arguments[0].scrollIntoView(true);", load_more)

            #random เวลา เบรค
            time.sleep(random.uniform(2,5))

            driver.execute_script("arguments[0].click();", load_more)
            
        except :

            last_height = driver.execute_script("return document.body.scrollHeight")

            if len(count_high) == 0 : #ถ้าความูงครั้งที่แล้วไม่มี ให้เพิ่มเข้าไปก่อน
                count_high.append(int(last_height))
                continue

            else :
                if last_height != count_high[-1] : # ถ้าความสูง ไม่เท่ากัน กับครั้งท่ี่แล้วแสดงว่ายังมีหน้าโหลดอีก
                    continue
                else : # ถ้าความสูงเท่ากันกับครั้งที่แล้ว แสดงว่า / หน้าสุดท้ายแล้ว
                    break
            
        

        #endregion

        news_loop_round -= 1

    return loading 

def main():

    try :
        #เขียน ลง text
        have_log_kw = open('log_keywords'+'.csv','r')
        have_log_kw.close()

    except :
        make_old_kw()
        
    # --------------------------------------------------------
    # นำเข้า key words จาก ไฟล์ text
    last_keyword_score = read_kw()

    #ไม่ได้ใช้
    #today_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    frist = True
    
    for city, count in mark_city.items() : 
        
        print('', flush=True)
        print(f'...Get news from {city}', flush=True)

        url_get = 'https://www.reuters.com/'+city
        
        options = Options()

        if "linux" in this_system :    
            CHROMEDRIVER_PATH = "/usr/bin/chromedriver"  # path ของ chromedriver บน Pi
            CHROMIUM_BIN = "/usr/bin/chromium"           # path ของ chromium บน Pi
           
            PROFILE_PATH = "/home/mir/chrome_profiles/reuters"
           
            # สร้างโฟลเดอร์ถ้ายังไม่มี
            os.makedirs(PROFILE_PATH, exist_ok=True)

            options = webdriver.ChromeOptions()
            options.binary_location = CHROMIUM_BIN

            # 🧩 ใช้ user-data-dir เดิม
            options.add_argument(f"--user-data-dir={PROFILE_PATH}")
            options.add_argument("--profile-directory=Default")
            
            #options.headless = True
            #options.add_argument("--headless=new") 

            options.binary_location = CHROMIUM_BIN
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-features=IsolateOrigins,site-per-process")
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--disable-extensions")
            options.add_argument("--start-maximized")

            #ปิด automation flags
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)


            # new user-agent (ตามที่เจ้านายให้มา)
            # new_ua คือค่สที่อ่านมา
            new_ua = ("Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")
            options.add_argument(f"user-agent={new_ua}")
        
            service = Service(CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=options)


            stealth(driver,
                languages=["en-GB","en-US", "en"],
                vendor="Google Inc.",
                platform="Linux x86_64", 
                webgl_vendor= "Broadcom",
                renderer="ANGLE (Broadcom, V3D 4.2.14.0, OpenGL ES 3.1 Mesa 25.0.7-2+rpt3)",
                fix_hairline=True)

        elif "windows" in this_system :
            driver = webdriver.Chrome(options=options)

            stealth(driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win64",
                webgl_vendor="NVIDIA Corporation",
                renderer="NVIDIA GeForce GTX 1650/PCIe/SSE2",
                fix_hairline=True)
        
        # ตั้งเวลาถ้าเว็บโหลดช้ากว่านี้จะ error
        driver.set_page_load_timeout(180)

        print(f'......Open news', flush=True)
    
        try : #เปิดหน้าหลักก่อน

            #เฉพาะครั้งแรก
            if frist == True :
                #เปิด เว็บหลัก ก่อนเข้าเว็บ
                driver.get('https://www.reuters.com')
                
                time.sleep(random.uniform(7,15))
                
                # จำลอง scroll
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                time.sleep(random.uniform(7, 15))

                frist = False
        
        except : 
            pass


        try : #linkไหนมีปัญหา / รอนานเกิน 120 ก็ข้ามไป
           
            #เปิดเว็บ ตามลิ้ง
            driver.get(url_get)
            run_app = get_data(driver, count)

            #app run ได้ปรกติ
            if run_app == True :
                driver.quit()  

            # มีบางอย่างผิดพลาด
            else :
                print(f'.........Stop by Verification Require LINE NOTICE', flush=True)
                send_line_message(access_token,'.........Stop Auto_News by Verification Require')
                break
        
        except :
            pass

    print(f'...Finish get news', flush=True)
    print(flush=True)

    #region-------------------------------------------ดึงข้อมูลเก่า 
    #ดึงข่าวที่เคยอ่านมาแล้ว ป้องกันการดึงมานับ ซ้ำ
    old_log_news = 'log_news.csv'

    try :
        news_log_readed = []
        with open(old_log_news, 'r', encoding='utf-8') as f:
            for line in f:
                news_log_readed.append(line.strip())
   
    except :
        news_log_readed = []
        with open(old_log_news, 'w', encoding='utf-8') as f:
            pass

    #endregion

    #ถ้าไม่มีข้อมูล จะไม่ดำเนินการต่อ
    if len(articles) != 0 :

        data_tran = np.array(articles).reshape(-1,4)
        print(f'...Analise news', flush=True)
    
        #region----------------------------------------วิเคราะห์ข่าวใหม่ ทั้งหมด

        prepair_for_use = []  #ข่าวรูปแบบต็ม

        for ix in range(len(data_tran)):
            
            news = str(data_tran[ix][2])

            s, matches, update_keyword_score = analyze_title(news, last_keyword_score)

            #ป้องกันข่าวซ้ำกัน และ ต้องมี score มากกว่า 0 ถึงจะจัดเก็บ
            if (news not in prepair_for_use) and (s != 0) :
            
                # บันทึกก่อนยังไม่ต้องเก็บfire base
                prepair_for_use.append(data_tran[ix][0])
                prepair_for_use.append(data_tran[ix][1])
                prepair_for_use.append(news)
                prepair_for_use.append(s)
                prepair_for_use.append(matches)
                prepair_for_use.append(data_tran[ix][3])

                # ถ้าเป็นข่าว ที่มี ใน log แล้วจะไม่ให้เก็บ ค่าความสำคัญข่าว หรือ อัพเดท keyword
                add_text = news.split(' ')

                #จัดเรียง ข้อความเพื่อตรวจสอบใน log
                keep_news = str(data_tran[ix][0])+' '+add_text[0]+' '+add_text[1]+' '+add_text[2]

               
                #ถ้าไม่เคยอ่านข่าวไดๆเลย หรือ เป็นข่าวที่ยังไม่เคยอ่านจะเข้าเงื่อนไข ==> อัพเดท score
                if (len(news_log_readed) == 0) or (keep_news not in news_log_readed) :
                    
                    #update keyword score ที่ได้มาใหม่
                    last_keyword_score.update(update_keyword_score) 
                        
        #หลังจากอัพเดท score keywords เสร็จให้อัพเดท ในไฟล์ log_keywords
        update_kw(last_keyword_score)


        # --------------------------------------------------------
        print(f'...Keep to Firebase & csv', flush=True)

        #สร้าง DataFrame และจัดเรียง
        out_data = (np.array(prepair_for_use)).reshape(-1,6)
        df = pd.DataFrame(out_data, columns=['time','lastup','news','score','matches','url'])
       
        df['score'] = df['score'].astype(float)
        #much_score = df['score'].nlargest(4).iloc[:4].tolist()

        #ปรับค่าให้เรียงลำดับตาม score
        df = df.sort_values(by='score', ascending=False)

        np_data =  df.to_numpy()

        #endregion


        db_news = {'000':['TimeTH','LastUP','News','Score','Matching','URL']}

        last_news_check = [] #keyword เวลา+[0]+[1]

        for ni in range(len(np_data)) :

            #region fierbases

            if len(db_news) < 10 : dbn = '00'+str(len(db_news))
            
            else : dbn = '0'+str(len(db_news))
            
            score = float(np_data[ni][3])

            db_news[dbn] = [str(np_data[ni][0]), str(np_data[ni][1]), str(np_data[ni][2]), score, str(np_data[ni][4]), str(np_data[ni][5])]
            
            db.reference('/News_analise').set(db_news)
        
            #endregion

            #region บันทึกไฟล์ / line

            old_readed = news_log_readed[:limit_max_notify] # 4ข่าว สั้น ที่มีscore สูงสุดในอดีต ไฟล์

            #ถ้าเป็นข่าว ที่มี ใน log แล้วจะไม่ให้เก็บ ค่าความสำคัญข่าว หรือ อัพเดท keyword
            add_text = np_data[ni][2].split(' ')

            #จัดเรียง ข้อความเพื่อตรวจสอบใน log
            keep_news = str(np_data[ni][0])+' '+add_text[0]+' '+add_text[1]+' '+add_text[2]

            #เก็บ log ไว้รออัพเดท csv
            last_news_check.append(keep_news)


            if (ni < limit_max_notify) and (keep_news not in old_readed) :

                score = float(np_data[ni][3])

                #แปลภาษา
                input_text = str(np_data[ni][2]) 
                translated_text = GoogleTranslator(source='auto', target='th').translate(input_text)

                text = 'score '+str('%.4f'%score)+' '+translated_text

                if "linux" in this_system : 
                    send_line_message(access_token,text)
                    
                else :
                    print(keep_news, flush=True)

                

     
            #endregion

       
        
        
    

        #ลบ+เขียน ไฟล์ log_news.csv  ข่าวเก่า ที่ถูก บันทกไว้นานเกินจะหายไป
        with open(old_log_news, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for row in last_news_check :
                writer.writerow([row])





        #สร้างไฟล์ เพื่อให้รู้ว่า รันสำเร็จแล้ว
        if "linux" in this_system :
            print(f'...Make flag_news', flush=True) 
            open(flag_news, "w").close() 

#ให้ปริ้นออก log

main()


