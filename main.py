import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
import os
import sys
import json
import requests
from ASetting import access_token
from smbus2 import SMBus

#---------------------------จอ
import fcntl
import socket
import struct

import board 
import digitalio
from PIL import Image, ImageDraw, ImageFont

import adafruit_ssd1306

from board import SCL, SDA
import busio


#ให้ปริ้นออก log
sys.stdout.reconfigure(line_buffering=True)

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


def check_power_source():
    
    I2C_ADDR = 0x42

    REG_BUS_VOLTAGE = 0x02
    REG_CURRENT     = 0x04
    REG_POWER       = 0x06

    def read_word(bus, reg):
        """Read signed 16-bit word (Waveshare style)"""
        data = bus.read_word_data(I2C_ADDR, reg)
        value = ((data & 0xFF) << 8) | (data >> 8)

        if value & 0x8000:
            value -= 65536

        return value

    # ---------- BATTERY SOC ----------
    def battery_percent(voltage):
        """
        Li-ion 2S SOC table (UPS use, safe-side)
        """
        table = [
            (8.40, 100),
            (8.20, 90),
            (8.00, 80),
            (7.80, 70),
            (7.60, 60),
            (7.40, 50),
            (7.20, 40),
            (7.00, 30),
            (6.80, 20),
            (6.60, 10),
            (6.40, 0),
        ]

        if voltage >= 8.40:
            return 100
        if voltage <= 6.40:
            return 0

        for i in range(len(table) - 1):
            v1, p1 = table[i]
            v2, p2 = table[i + 1]
            if v1 >= voltage >= v2:
                return int(p1 + (voltage - v1) * (p2 - p1) / (v2 - v1))

        return 0

    # ---------- MAIN ----------
    with SMBus(1) as bus:
        raw_v = read_word(bus, REG_BUS_VOLTAGE)
        raw_c = read_word(bus, REG_CURRENT)
        raw_p = read_word(bus, REG_POWER)

        # UPS HAT voltage divider 1:2
        voltage = (raw_v / 1000.0) / 2
        current = raw_c / 1000.0
        power   = raw_p / 1000.0

        percent = battery_percent(voltage)

    #ปิดไว้เพราะไม่ต้องการให้แสดง
    #print(f"🔋 Battery Voltage : {voltage:.2f} V")
    #print(f"🔋 Battery Level   : {percent} %")
    #print(f"⚡ Current         : {current:.3f} A")
    #print(f"🔌 Power Input     : {power:.2f} W")

    text_voltage = str(voltage)+" / "+str(percent)

    if voltage >= 8.1 :
        #print("🔌 Power Source    : AC (Charging)")
        return True, text_voltage

    elif voltage < 8.1 :
        #print("🔋 Power Source    : UPS Battery")
        return False, text_voltage


def oled(power):

    # This function allows us to grab any of our IP addresses
    def get_ip_address(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(
            fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack("256s", str.encode(ifname[:15])),
            )[20:24]
        )


    # Setting some variables for our reset pin etc.
    RESET_PIN = digitalio.DigitalInOut(board.D4)
    TEXT = ""

    # Very important... This lets py-gaugette 'know' what pins to use in order to reset the display
    i2c = board.I2C()  # uses board.SCL and board.SDA
    # i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

    # Create the SSD1306 OLED class.
    # The first two parameters are the pixel width and pixel height.
    # Change these to the right size for your display!
    oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

    # Note you can change the I2C address, or add a reset pin:
    # oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3D, reset=RESET_PIN)

    # This sets TEXT equal to whatever your IP address is, or isn't
    try:
        TEXT = get_ip_address("wlan0")  # WiFi address of WiFi adapter. NOT ETHERNET
    except OSError:
        try:
            TEXT = get_ip_address("eth0")  # WiFi address of Ethernet cable. NOT ADAPTER
        except OSError:
            TEXT = "NO INTERNET!"

    # Clear display.
    oled.fill(0)
    oled.show()

    # Create blank image for drawing.
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)

    # Load a font in 2 different sizes.
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    font2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)

    # Draw the text
    intro = "FANG SI"


    batt = "BATT : "+power
    ip = "IP : "+TEXT

    draw.text((0, 0), intro, font=font, fill=255)
    draw.text((0, 30), batt, font=font2, fill=255)
    draw.text((0, 46), ip, font=font2, fill=255)

    # Display image
    oled.image(image)
    oled.show()


def oled_word(word):

    # Very important... This lets py-gaugette 'know' what pins to use in order to reset the display
    i2c = board.I2C()  # uses board.SCL and board.SDA
    # i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

    # Create the SSD1306 OLED class.
    # The first two parameters are the pixel width and pixel height.
    # Change these to the right size for your display!
    oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)

    # Note you can change the I2C address, or add a reset pin:
    # oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3D, reset=RESET_PIN)

    # Clear display.
    oled.fill(0)
    oled.show()

    # Create blank image for drawing.
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)

    # Load a font in 2 different sizes.
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)

    draw.text((0, 0), word, font=font, fill=255)
 
    # Display image
    oled.image(image)
    oled.show()


def clear_oled():
    # Create the I2C interface.
    i2c = busio.I2C(SCL, SDA)

    # Create the SSD1306 OLED class.
    # The first two parameters are the pixel width and pixel height.  Change these
    # to the right size for your display!
    display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
    # Alternatively you can change the I2C address of the device with an addr parameter:
    # display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c, addr=0x31)

    # Clear the display.  Always call show after changing pixels to make the display
    # update visible!
    display.fill(0)
    display.show()

def run(x): # 1.NEWS  2.MOMENTUM
    status, voltage = check_power_source() 

    oled(voltage)

    #---------ถ้าไฟดับจะปิด service + สร้างไฟล์ + ปิดเครื่อง อย่างถูกต้อง
    
   
    if status == True :
                                    
        try : 

            os.system('clear')
            subprocess.run(["/home/mir/env/bin/python","-u", "/home/mir/robot/update.py"])

            if x == 1 :
                # รันสคริปต์ปกติ
                subprocess.run(["/home/mir/env/bin/python","-u", "/home/mir/robot/auto_news.py"])
            
        
            elif x == 2 :
                subprocess.run(["/home/mir/env/bin/python","-u", "/home/mir/robot/auto_momentum.py"])
                os.system('clear')
                next_time(10, '...Next LOOP in ')
    
        except :

            send_line_message(access_token, '...MIR ROBOT WAS STOP BY INTERNET...')

    
    elif status == False :
        oled_word("Power OFF")

        #สร้างไฟล์ว่า เกิดไฟดับขั้น
        thai_time = datetime.now().replace(microsecond=0)
        run_flag = open("/home/mir/robot/Black_out "+str(thai_time)+'.flag','w')
        run_flag.close()

        #clear_oled()

        print('...Service Disable', flush=True)
        os.system("sudo systemctl disable auto_mir.service")

        #print('...Service Stop', flush=True)
        #os.system("sudo systemctl stop auto_mir.service")

        boot = 60
        time.sleep(boot)
        print('...'+str(boot)+'s Systems will Shutdown', flush=True)
        #os.system("sudo shutdown -h +1") #delay เวลาปิดเครื่อง ตัวเลขข้างหลัง เอา 15/60=0.25
        os.system("sudo shutdown now")

        




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
              

                if not os.path.exists(flag_boot):

                    open(flag_boot, "w").close()  

                    #อย่าลบบรรทัดนี้
                    boot = 15
                    print('...'+str(boot)+'s Systems will Reboot', flush=True)
                    time.sleep(boot)

                    os.system("sudo reboot")
                
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
    




