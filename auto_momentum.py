from bitkub import Bitkub
from datetime import datetime,timedelta 
from binance.client import Client
import pandas as pd
import numpy as np
import time
import os
import sys
import platform
import csv

import datetime as dt
import matplotlib.pyplot as plt
import pandas_ta as ta
import mplfinance as mpf
from matplotlib.patches import Polygon

import hashlib
import hmac
import json
import time
import requests
import urllib3

import firebase_admin
from firebase_admin import db, credentials
#------------------------------------------------------------------------------------------wallet
from ASetting import BITKUB_API_SECRET, BITKUB_API_KEY
#------------------------------------------------------------------------------------------Technical

from ASetting import start_date,mode_depth,heat_map_date,no_candles_indy, tf_bit_to_bin
from ASetting import rsi_length  
from ASetting import macd_fast, macd_slow, macd_signal
from ASetting import bb_1length, bb_1std, bb_2length, bb_2std
from ASetting import sto_length, sto_rsi_length, sto_k, sto_d, sto_up, sto_down 
from ASetting import bitkub_ema_set,binance_ema_set
from ASetting import bitkub_symbol_setting, binance_symbol_setting, no_candles, total_funding, w_avg_close, w_limit_rate_close_bit_bin, w_limit_diff_future_spot_vol, no_heiken, observation_cand, mode_order_block, no_order_block, auto_tl, predict_semi, fillter_vol, economic_set, add_economic_set, trand_bar_pattern
from ASetting import broker_pair_value, access_token
from ASetting import bitkub_tf_make_log,bitkub_keep_day_from_now

sys.stdout.reconfigure(line_buffering=True)
flag_notify = "/home/mir/robot/notify.flag"

#ตรวจสอบระบบ ที่ run
this_system = platform.system().lower()

#region FIREBASE

## authenticate to firebase
cred = credentials.Certificate("fire_base_admin.json")

firebase_admin.initialize_app(cred, {"databaseURL": "https://robot-mir-79bc9-default-rtdb.asia-southeast1.firebasedatabase.app/"})

# creating reference to root node
ref = db.reference("/")

#endregion

#region Broker
bitkub = Bitkub()
bitkub.set_api_key(BITKUB_API_KEY)
bitkub.set_api_secret(BITKUB_API_SECRET)

#a = bitkub.trades(sym="THB_ZIL", lmt=13000)['result']
#for i in range(len(a)) :
#    t = datetime.fromtimestamp(int(a[i][0]))
#    print(str(t)+', '+str(a[i][1])+', '+str(a[i][2])+', '+str(a[i][3]))

#spot del usdtm
#binance = ccxt.binanceusdm({'apiKey' : BINANCE_API_KEY, 'secret' : BINANCE_API_SECRET, 'enableRateLimit' : True} )

# ไม่ต้องใส่ API key ถ้าเอาแค่ข้อมูลสาธารณะ
client = Client()

#endregion

last_date = []

#bitkub close 3แท่ง ล่าสุด 
#เก็บ ARR ราคาปิด 3 ตัวสุดท้าย
#เก็บ ARR ราคาสูง -4:-1 ตัวสุดท้าย


use_arr_analise = {}

last_arr_mark = 3 #จำนวนแท่งเทียนที่จำนำมาสร้างเป็น last price

class SUB_FUCTION:

    def servertime():   
        host = 'https://api.bitkub.com'
        path = '/api/v3/servertime'
        url = host + path
        return requests.request('GET', url).text

    def convert_Day_to_Week(daily_array):

        # Create DataFrame
        df = pd.DataFrame(daily_array, columns=['UTC','Open','High','Low','Close','Volume'])

        df['Open'] = df['Open'].astype(float)
        df['High'] = df['High'].astype(float)
        df['Low'] = df['Low'].astype(float)
        df['Close'] = df['Close'].astype(float)
        df['Volume'] = df['Volume'].astype(float)
       
        #df["UTC"] = pd.to_datetime(df["UTC"], unit="ms", utc=True).dt.tz_convert("Asia/Bangkok")
       
        # Convert UTC → Bangkok timezone
        #df['UTC'] = pd.to_datetime(df['UTC']).dt.tz_convert('Asia/Bangkok')
        df = df.set_index('UTC')

        # ----------------------------------------------
        # Weekly resample (จันทร์ 07:00 – จันทร์ 06:59)
        # ใช้ W-MON แล้ว shift +7 hours
        # ----------------------------------------------
        df_week = pd.DataFrame()

        df_week['Open']  = df['Open'].resample('W-MON', label='left', closed='left').first()
        df_week['High']  = df['High'].resample('W-MON', label='left', closed='left').max()
        df_week['Low']   = df['Low'].resample('W-MON', label='left', closed='left').min()
        df_week['Close'] = df['Close'].resample('W-MON', label='left', closed='left').last()
        df_week['Volume'] = df['Volume'].resample('W-MON', label='left', closed='left').sum()
       
        # ปรับเวลาให้เป็น "จันทร์ 07:00" แทน "จันทร์ 00:00"
        df_week.index = df_week.index + pd.Timedelta(hours=7)
     
        # ลบแท่งไม่สมบูรณ์
        df_week = df_week.dropna()

        #ลบแถวแรกออก เพราะแท่งเทียไม่สมบูรณ
        df_week.drop (index= df_week.index [0], axis= 0 , inplace= True ) 

        # ⭐ Reset index ตรงนี้ ⭐
        df_week = df_week.reset_index()
       
        dn = np.array(df_week)

        return dn

    def Bitkub_ohlcv_UTC(sym,tfs,start_dt): #start_dt เป็นวันที่หรือจำนวนก็ได้
        
        # เวลาล่าสุด
        end_dt = last_date[-1]

        symbolx = sym+'_THB'
        
        stype  = str("%Y-%m-%d %H:%M:%S")

        #ถ้ารับเข้าเป็น str
        if isinstance(start_dt, str):
            
            th_time = dt.datetime.strptime(start_dt, stype)
            from_s = int(time.mktime(th_time.timetuple()))
           
            if tfs != '1w' : 
                use_tf = tfs

            elif tfs == '1w':
                use_tf = '1D'

        #ถ้านำเข้าเป็นจำนวนแท่ง
        else :
            
            if tfs != '1w' : #กรณีที่ไม่ใช้ 1W
                
                use_tf = tfs

                if tfs != '1D' :
                 
                    get_val = int((start_dt * tfs) * 1.1) # 1.1 คือเผื่อใว้
                    first_candle_date = end_dt - timedelta(minutes = get_val)
                
                elif tfs == '1D' :

                    get_val = int(start_dt * 1.1) # 1.1 คือเผื่อใว้
                    first_candle_date = end_dt - timedelta(days = get_val)

            elif tfs == '1w' :  #กรณีที่เป็น 1W
                
                use_tf = '1D'
              
                # หา Monday 07:00 ล่าสุด
                monday = end_dt - timedelta(days=end_dt.weekday())  # Monday 00:00
                monday_week = monday.replace(hour=7, minute=0, second=0, microsecond=0)
                
                # monday_week = เวลาเริ่มแท่งปัจจุบัน
                get_val = int(start_dt * 1.1) # 1.05 คือเผื่อใว้
                first_candle_date = monday_week - timedelta(weeks=get_val)
            
            from_s = int(time.mktime(first_candle_date.timetuple())) 

        to_s = int(time.mktime(end_dt.timetuple())) 
        historical = bitkub.tradingview(sym=symbolx, int=use_tf, frm=from_s, to=to_s)

        df = pd.DataFrame(historical)

        df = df[['t','o','h','l','c','v','s']]  #เปลี่ยนที่อยู่ช่อง
        #ลบ dict s
        del df['s']

        df.columns = ['UTC','Open','High','Low','Close','Volume']
        
        df['UTC'] = pd.to_datetime(df['UTC'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Bangkok') #2025-11-17 00:00:00+0000  #2025-01-06 07:00:00+07:00
       
        #แปลงเป็น แท่งเทียน 1W
        if tfs != '1w' :

            if tfs == '1D' :
                df['UTC'] = pd.to_datetime(df['UTC']).dt.tz_localize(None).dt.normalize() #2025-01-06 07:00:00 '1W' 'อื่นง --- #2025-01-06 00:00:00  1D
             
            else :
                df['UTC'] = pd.to_datetime(df['UTC']).dt.tz_localize(None) #2025-01-06 07:00:00 '1W' 'อื่นง


            #ส่งออกตามวันที่ขอ
            if isinstance(start_dt, str):       
                out = np.array(df)

            #ส่งออกตามจำนวน ที่ขอ
            else :    
                in_dn = np.array(df)                          
                out = in_dn[-start_dt:]
          
            return out
        
        elif tfs == '1w' :
            df['UTC'] = pd.to_datetime(df['UTC']).dt.tz_localize(None)            #2025-01-06 07:00:00 '1W' 'อื่นง
           
            #ส่งออกตามวันที่ขอ
            if isinstance(start_dt, str):       
                out = np.array(df)

            #ส่งออกตามจำนวน ที่ขอ
            else :    
                in_dn = np.array(df)                          
                out = in_dn[-start_dt:]
           
            outx = SUB_FUCTION.convert_Day_to_Week(out)
           
            return outx

    def Binance_ohlcv_UTC(market,mode,sym,tfs,start_dt): #mode:ohlcv/trades -- market:future/spot

        # เวลาล่าสุด
        end_dt = last_date[-1]

        symbol =  sym.upper()+'USDT'

        stype  = str("%Y-%m-%d %H:%M:%S")
        
        #ถ้ารับเข้าเป็น str
        if isinstance(start_dt, str) :
            

            utc_time = dt.datetime.strptime(start_dt, stype) - timedelta(hours = 7)
            from_s = str(utc_time)

            if tfs != '1w' :
                use_tf = tfs

            elif tfs == '1w' :
                use_tf = '1d'

        else :
                       
            if tfs != '1w' : #กรณีที่ไม่ใช้ 1W
                
                use_tf = tfs

                if tfs != '1d' :
                 
                    if tfs == '4h' : get_val = int((start_dt * 240) * 1.1) # 1.1 คือเผื่อใว้
                    elif tfs == '1h': get_val = int((start_dt * 60) * 1.1) # 1.1 คือเผื่อใว้
                    elif tfs == '30m': get_val = int((start_dt * 30) * 1.1) # 1.1 คือเผื่อใว้
                    elif tfs == '15m': get_val = int((start_dt * 15) * 1.1) # 1.1 คือเผื่อใว้
                    elif tfs == '5m': get_val = int((start_dt * 5) * 1.1) # 1.1 คือเผื่อใว้
                    first_candle_date = end_dt - timedelta(minutes = get_val)
                
                elif tfs == '1d' :

                    get_val = int(start_dt * 1.1) # 1.1 คือเผื่อใว้
                    first_candle_date = end_dt - timedelta(days = get_val)

            elif tfs == '1w' :  #กรณีที่เป็น 1W
                
                use_tf = '1d'
              

                # หา Monday 07:00 ล่าสุด
                monday = end_dt - timedelta(days=end_dt.weekday())  # Monday 00:00
                monday_week = monday.replace(hour=7, minute=0, second=0, microsecond=0)
                
                # monday_week = เวลาเริ่มแท่งปัจจุบัน
                get_val = int(start_dt * 1.2) # 1.05 คือเผื่อใว้
                first_candle_date = monday_week - timedelta(weeks=get_val)
                        
            utc_time = first_candle_date - timedelta(hours=7)
            from_s = str(utc_time)

        all_data = []

        limit = 1000

        if market == 'future' :# ดึงข้อมูลแบบ Futures USDT-M

            klines = client.futures_klines(
                symbol=symbol,
                interval=use_tf,
                limit=limit,
                startTime=pd.to_datetime(from_s).tz_localize("UTC").value // 10**6)
            
            all_data.extend(klines)

            while len(klines) > 0:
            
                last_open_time = all_data[-1][0]  # เอา open_time ล่าสุด
                klinesx = client.futures_klines(symbol=symbol, interval=use_tf, limit=limit, startTime=last_open_time)

                if len(klinesx) == limit :
                    all_data.extend(klinesx[1:])

                elif len(klinesx) < limit:
                    break
  
        elif market == 'spot' :

            klines = client.get_klines(
                symbol=symbol,
                interval=use_tf,
                limit=limit,
                startTime=pd.to_datetime(from_s).tz_localize("UTC").value // 10**6
            )
           
            all_data.extend(klines)

            while len(klines) > 0:
            
                last_open_time = all_data[-1][0]  # เอา open_time ล่าสุด
                klinesx = client.get_klines(symbol=symbol, interval=use_tf, limit=limit, startTime=last_open_time)

                if len(klinesx) == limit :
                    all_data.extend(klinesx[1:])

                elif len(klinesx) < limit:
                    break
   
        # แปลงเป็น DataFrame เพราะใช้ข้อมูลเหมือนกัน
        df = pd.DataFrame(all_data, columns=[
            'UTC','Open','High','Low','Close','Volume',
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
     
        if mode == 'ohlcv' :

            # number_of_trades จำนวนคำสั่งซื้อขายที่เกิดขึ้น
            # taker_buy_base จำนวนเหรียญที่ถูกกด ซื้อ

            df.drop(columns=["close_time","quote_asset_volume", "number_of_trades","taker_buy_base", "taker_buy_quote", "ignore"], inplace=True)

            #แปลงเวลาเป็นไทย (+07:00)
            #df["UTC"] = pd.to_datetime(df["UTC"], unit="ms", utc=True).dt.tz_convert("Asia/Bangkok")
            df['UTC'] = pd.to_datetime(df['UTC'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Bangkok') #2025-11-17 00:00:00+0000  #2025-01-06 07:00:00+07:00
        
            #แปลงเป็น แท่งเทียน 1W
            if tfs != '1w' :

                if tfs == '1D' :
                    df['UTC'] = pd.to_datetime(df['UTC']).dt.tz_localize(None).dt.normalize() #2025-01-06 07:00:00 '1W' 'อื่นง --- #2025-01-06 00:00:00  1D
                
                else :
                    df['UTC'] = pd.to_datetime(df['UTC']).dt.tz_localize(None) #2025-01-06 07:00:00 '1W' 'อื่นง


                #ส่งออกตามวันที่ขอ
                if isinstance(start_dt, str):       
                    out = np.array(df)

                #ส่งออกตามจำนวน ที่ขอ
                else :    
                    in_dn = np.array(df)                          
                    out = in_dn[-start_dt:]

                return out
            
            elif tfs == '1w' :
                
                df['UTC'] = pd.to_datetime(df['UTC']).dt.tz_localize(None)            #2025-01-06 07:00:00 '1W' 'อื่นง
            
                #ส่งออกตามวันที่ หรือจำนวน ที่ขอ
                out = np.array(df)    

                outx = SUB_FUCTION.convert_Day_to_Week(out)
                
                #ปรับให้เอาตามจำนวน
                if isinstance(start_dt, str): 
                    pass
                elif len(outx) > start_dt :
                    outx = outx[-start_dt:]
                
                return outx

        elif mode == 'trades':
            
            
            # taker_buy_base จำนวนเหรียญที่ถูก ซื้อ
            # มูลค่าซื้อขายทั้งหมด (USDT) → quote_asset_volume
            # มูลค่า USDT ที่ฝั่งซื้อ (taker buy) → taker_buy_quote
            df['Volume'] = df['Volume'].astype(float)
            df['vol_buy'] = df['taker_buy_base'].astype(float)
            df['vol_sell'] = df['Volume'] - df['vol_buy']

            df['usdt_all'] = df['quote_asset_volume'].astype(float)
            df['usdt_buy'] = df['taker_buy_quote'].astype(float)
            df['usdt_sell'] = df['usdt_all'] - df['usdt_buy']
            

            df.drop(columns=['Open','High','Low','Close','Volume',"close_time", "quote_asset_volume",'taker_buy_base', "number_of_trades", 'usdt_all',"taker_buy_quote", "ignore"], inplace=True)

            #แปลงเวลาเป็นไทย (+07:00)
            #df["UTC"] = pd.to_datetime(df["UTC"], unit="ms", utc=True).dt.tz_convert("Asia/Bangkok")
        
            # Convert UTC → Bangkok timezone
            df["UTC"] = pd.to_datetime(df["UTC"], unit="ms", utc=True).dt.tz_convert("Asia/Bangkok")
            
            if tfs != '1w' :
                df["UTC"] = df["UTC"].dt.tz_localize(None) # ลบ +0700 ออก
                
                #ส่งออกตามวันที่ขอ
                if isinstance(start_dt, str):       
                    dn = np.array(df)

                #ส่งออกตามจำนวน ที่ขอ
                else :    
                    in_dn = np.array(df)                          
                    dn = in_dn[-start_dt:]

            elif tfs == '1w' :
                    
                df = df.set_index('UTC')
                
                df_week = pd.DataFrame()

                df_week['vol_buy'] = df['vol_buy'].resample('W-MON', label='left', closed='left').sum()
                df_week['vol_sell'] = df['vol_sell'].resample('W-MON', label='left', closed='left').sum()
                df_week['usdt_buy'] = df['usdt_buy'].resample('W-MON', label='left', closed='left').sum()
                df_week['usdt_sell'] = df['usdt_sell'].resample('W-MON', label='left', closed='left').sum()

                # ปรับเวลาให้เป็น "จันทร์ 07:00" แทน "จันทร์ 00:00"
                df_week.index = df_week.index + pd.Timedelta(hours=7)

                # ลบแท่งไม่สมบูรณ์
                df_week = df_week.dropna()

                #ลบแถวแรกออก เพราะแท่งเทียไม่สมบูรณ
                df_week.drop (index= df_week.index [0], axis= 0 , inplace= True ) 

                # ⭐ Reset index ตรงนี้ ⭐
                df_week = df_week.reset_index()

                #+0700
                df_week["UTC"] = df_week["UTC"].dt.tz_localize(None) # ลบ +0700 ออก

                #ส่งออกตามวันที่ขอ
                if isinstance(start_dt, str):       
                    dn = np.array(df_week)

                #ส่งออกตามจำนวน ที่ขอ
                else :    
                    in_dn = np.array(df_week)                          
                    dn = in_dn[-start_dt:]


            return dn

    def clear_screen():
        
        if "linux" in this_system: #Raspberry Pi
            os.system('clear')
        
        elif "windows" in this_system: # สำหรับ Windows (เช่น PC)
            os.system('cls')

    def Find_stop_bitkub(sym): #'%.4f'%

        symbol = 'THB_'+ sym       

        try :
    
            put = bitkub.depth(sym = symbol, lmt = 1)
            bids = np.array(put['bids'])
            asks = np.array(put['asks'])

            bidsx = str(bids[0][0]).split('.')
            asksx = str(asks[0][0]).split('.')

            bidsy = len(bidsx[1])
            asksy = len(asksx[1])

            if (bidsy >= 2) or (asksy >= 2) :

                if bidsy > asksy :
                    os = bidsy

                elif bidsy < asksy :
                    os = asksy

                elif bidsy == asksy :
                    os = bidsy

                if os == 2 :
                    stop = '%.2f'
                    static_error = 0.005
                
                elif (os == 4) or (os == 3) :
                    stop = '%.4f'
                    static_error = 0.00005

            elif (bidsy <= 1) or (asksy <= 1) :

                print('ระบุทศนิยม')
                print('1. 0.00')
                print('2. 0.0000')
                #os = int(input('==> '))
                os = int(2)

                if os == 1 :
                    stop = '%.2f'
                    static_error = 0.005
              
                elif os == 2 :
                    stop = '%.4f'
                    static_error = 0.00005

        except : 
            print()
            print('ระบุทศนิยม')
            print('1. 0.2')
            print('2. 0.4')

            #os = int(input('==> '))
            os = int(2)

            if os == 1 :
                stop = '%.2f'
                static_error = 0.005
           
            elif os == 2 :
                stop = '%.4f'
                static_error = 0.00005
            
        return stop,static_error

    def Find_stop_binance(sym):
        set_sym ={'ZIL':['%.6f', 0.0000005]}

        try :
            stop = set_sym[sym][0]
            static_error = set_sym[sym][1]

        except :  
       
            symbol = sym+'USDT'

            try :
                
                put = client.get_order_book(symbol=symbol)
               
                bids = str(put['bids'][0][0])
                asks = str(put['asks'][0][0])
                
                bidsx = bids.split('.')
                asksx = asks.split('.')
                
                bidsy = len(bidsx[1])
                asksy = len(asksx[1])

                if bidsy == asksy  :
                
                    os = bidsy

                    if os == 1 :
                        stop = '%.1f'
                        static_error = 0.05
                    elif os == 2 :
                        stop = '%.2f'
                        static_error = 0.005
                    elif os == 3 :
                        stop = '%.3f'
                        static_error = 0.0005
                    elif os == 4 :
                        stop = '%.4f'
                        static_error = 0.00005
                    elif os == 5 :
                        stop = '%.5f'
                        static_error = 0.000005
                    elif os == 6 :
                        stop = '%.6f'
                        static_error = 0.0000005
                    elif os == 7 :
                        stop = '%.7f'
                        static_error = 0.00000005
                    elif os == 8 :
                        stop = '%.8f'
                        static_error = 0.000000005

                elif bidsy != asksy :

                    if bidsy > asksy :
                        os = bidsy

                    elif bidsy < asksy :
                        os = asksy
                    
                    if os == 1 :
                        stop = '%.1f'
                        static_error = 0.05
                    elif os == 2 :
                        stop = '%.2f'
                        static_error = 0.005
                    elif os == 3 :
                        stop = '%.3f'
                        static_error = 0.0005
                    elif os == 4 :
                        stop = '%.4f'
                        static_error = 0.00005
                    elif os == 5 :
                        stop = '%.5f'
                        static_error = 0.000005
                    elif os == 6 :
                        stop = '%.6f'
                        static_error = 0.0000005
                    elif os == 7 :
                        stop = '%.7f'
                        static_error = 0.00000005
                    elif os == 8 :
                        stop = '%.8f'
                        static_error = 0.000000005
            
            except :
                
                print()
                print('ระบุทศนิยม')
                print('1. 0.2')
                print('2. 0.4')
                print('3. 0.5')
                print('4. 0.6')
                print('5. 0.8')
                

                #os = int(input('==> '))
                os = int(4)

                if os == 1 :
                    stop = '%.2f'
                    static_error = 0.005
                elif os == 2 :
                    stop = '%.4f'
                    static_error = 0.00005
                elif os == 3 :
                    stop = '%.5f'
                    static_error = 0.000005
                elif os == 4 :
                    stop = '%.6f'
                    static_error = 0.0000005
                elif os == 5 :
                    stop = '%.8f'
                    static_error = 0.000000005

        return stop,static_error

    def depth_chart(ex, symbol) :
        
        dc = 1
        
        while dc == 1 :

            try :

                if ex == 'bitkub' :
                    dep = bitkub.depth(sym = symbol, lmt=100)
                    
                elif ex == 'binance' :
                    dep = client.get_order_book(symbol=symbol)
                    
                
                dc -= 1

           
            except :
                pass

        dep_b = dep['bids']
        dep_a = dep['asks']
       
        vb_sum = 0
        l_vb = []

        va_sum = 0
        l_va = []

        where_max_value_buy = []
        where_max_value_sell = []

        
        for db in range(len(dep_b)) :

            vb = float(dep_b[db][1])
            vb_sum += vb
            
            if mode_depth == 0 :
                l_vb.append(vb)

            elif mode_depth == 1 :
                l_vb.append(vb_sum)

            where_max_value_buy.append(vb)
            
        for da in range(len(dep_a)) :

            va = float(dep_a[da][1])
            va_sum += va

            if mode_depth == 0 :
                l_va.append(va)

            elif mode_depth == 1 :
                l_va.append(va_sum)

            where_max_value_sell.append(va)

        
        #region หา 3 อันดับการซื้อขาย
       
        #เรียงจากน้อยไปมาก
        sort_buy = where_max_value_buy.copy()
        sort_buy.sort()

        sort_sell = where_max_value_sell.copy()
        sort_sell.sort()

        
        sort_market_buy = []
        sort_market_sell = []

        for mb in range(2):

            #เอามากสุดใว้ทาง  ซ้าย
            id_mb = -(mb+1)

            #หา id
            id_max_buy = where_max_value_buy.index(sort_buy[id_mb])

            #ดึงราคา และ จำนวนที่มากที่สุด กลับ
            val_max_b = dep_b[int(id_max_buy)]
            price_max_b = val_max_b[0]
            vol_max_b = val_max_b[1]
            
            sort_market_buy.append(len(where_max_value_buy)-id_max_buy)
            sort_market_buy.append(price_max_b)
            

        for ms in range(2):

            #เอามากสุดใว้ทาง   ขวา
            id_ms = -(2-ms)

            #หา id
            id_max_sell = where_max_value_sell.index(sort_sell[id_ms])

            #ดึงราคา และ จำนวนที่มากที่สุด กลับ
            val_max_s = dep_a[int(id_max_sell)]
            price_max_s = val_max_s[0]
            vol_max_s = val_max_s[1]

            sort_market_sell.append(len(where_max_value_buy) + id_max_sell)
            sort_market_sell.append(price_max_s)
            

        max_buy = np.array(sort_market_buy).reshape(-1,2)
        max_sell = np.array(sort_market_sell).reshape(-1,2)

        #endregion

        #สร้าง sspace เพื่อสร้างช่องว่าง
        b_space = [] 
        a_space = []

        for bsx in range(len(dep_a)) :
            b_space.append(0)
       
        for asx in range(len(dep_b)) :
            a_space.append(0)

        #หา% Bid ASK
        bid_sum = vb_sum * 100 / ( va_sum + vb_sum )
        ask_sum = 100 - bid_sum

        #กลับด้าน vol bid
        l_vb.reverse()
        l_vb.extend(b_space) #เปิดตัวนี้คือเพิ่ม 0 ที่ขวาแกน

        a_space.extend(l_va) #เปิดตัวนี้คือเพิ่ม 0 ที่ซ้ายแกน + ต้องเอาไปใส่ return ด้วย

        # หาแกน X Y ตัวหนังสือ
        x_axis_bid = int( ( len(l_vb)-len(b_space) ) / 4 )  #เปลี่ยนตำแหน่งตัวหนังสือให้เปลี่ยนตัว หาร
        x_axis_ask = int(( len(a_space) - len(l_va) ) + (len(l_va) / 4 )) 
        y_axis = int ( max(vb_sum,va_sum) / 2 )


        return l_vb, a_space, x_axis_bid, x_axis_ask, y_axis, bid_sum, ask_sum, max_buy, max_sell

    def Heatmap(exs, sym, stop, number_grid, period, strength):
        
        if exs == 'bitkub' :
            #sym = str(input('Search Symbol ==> ')).upper()
            #number_grid = int(input('Number Price_range Min-Max (เลขคู่)  ==> '))
            #period = str(input('Period 1M 3M 4M 6M 12M  ==> ')).upper()
            #strength = str(input('Open Strength Zone Y/N  ==> ')).upper()
            
            #region ดึงข้อมูล
            data = np.array(SUB_FUCTION.Bitkub_ohlcv_UTC(sym,'1D',heat_map_date)).reshape(-1, 6)
            data_ohlc = data[1:]

            ohlcx = pd.DataFrame(data_ohlc, columns = ['UTC','Open','High','Low','Close','Volume'])
                
        elif exs == 'binance' :

            #sym = str(input('Search Symbol ==> ')).upper()
            #number_grid = int(input('Number Price_range Min-Max (เลขคู่)  ==> '))
            #period = str(input('Period 1M 3M 4M 6M 12M  ==> ')).upper()
            #strength = str(input('Open Strength Zone Y/N  ==> ')).upper()
            
            #region ดึงข้อมูล
            data = np.array(SUB_FUCTION.Binance_ohlcv_UTC('spot','ohlcv',sym,'1d',heat_map_date)).reshape(-1, 6)
            data_ohlc = data[1:]
           
            ohlcx = pd.DataFrame(data_ohlc, columns = ['UTC','Open','High','Low','Close','Volume'])

      
        ohlcx['Close'] = ohlcx['Close'].astype(float)
        ohlcx['High'] = ohlcx['High'].astype(float)
        ohlcx['Low'] = ohlcx['Low'].astype(float)

        max_price = ohlcx['High'].max()
        min_price = ohlcx['Low'].min()

        last_price = ohlcx['Close'][len(ohlcx)-1]
        last_index = len(ohlcx) - 1 #last index
        

        #region สร้าง period
        seperate_data = {}

        if period == '1M' :
            
            #เพิ่มช่อง abcd ขึ้นมาเพื่อ ปรับกราฟให้มันตรงกับเส้นราคาที่เราซ้อนทับกัน
            seperate_data['a'] = [0]
            seperate_data['b'] = [0]

            check_month = []
            for s in range(len(data_ohlc)) :

                datex = str(data_ohlc[s][0]).split('-')  #เลขบอกเดือนท่เท่าไหร่
                year = str(datex[0])
                month = str(datex[1])
                date_sep = year+'-'+month
                
                if s == 0 :
                    check_month.append(date_sep)                     #เพื่อ เช็คข้อมูล
                    seperate_data[date_sep] = [float(data_ohlc[s][4])]        #value แรกใน ดิก ต้องเป็น ลิสถึงจะบวกเพิ่มได้

                if (s > 0) and (date_sep == str(check_month[-1])) :
                    seperate_data[date_sep] += [float(data_ohlc[s][4])]

                elif (s > 0) and (date_sep != str(check_month[-1])) :  #ขึ้นเดือนใหม่
                    check_month.append(date_sep)                     #เพื่อ เช็คข้อมูล
                    seperate_data[date_sep] = [float(data_ohlc[s][4])]        #value แรกใน ดิก ต้องเป็น ลิสถึงจะบวกเพิ่มได้

            seperate_data['c'] = [0]
            seperate_data['d'] = [0]

        elif period == '3M' :

            #เพิ่มช่อง ab ขึ้นมาเพื่อ ปรับกราฟให้มันตรงกับเส้นราคาที่เราซ้อนทับกัน
            seperate_data['a'] = [0]
            
            for s in range(len(data_ohlc)) :

                datex = str(data_ohlc[s][0]).split('-')  #เลขบอกเดือนท่เท่าไหร่
                year = str(datex[0])
                month = str(datex[1])
                
                monthx = int(month) #ขอบเขตเดือน
                
                    
                if (monthx > 0) and (monthx <= 3) :
                    
                    date_sep = year+'-'+'03'
                    try :  seperate_data[date_sep] += [float(data_ohlc[s][4])]
                    except : seperate_data[date_sep] = [float(data_ohlc[s][4])] 


                elif (monthx > 3) and (monthx <= 6) :

                    date_sep = year+'-'+'06'
                    try :  seperate_data[date_sep] += [float(data_ohlc[s][4])]
                    except : seperate_data[date_sep] = [float(data_ohlc[s][4])] 


                elif (monthx > 6) and (monthx <= 9) :

                    date_sep = year+'-'+'09'
                    try :  seperate_data[date_sep] += [float(data_ohlc[s][4])]
                    except : seperate_data[date_sep] = [float(data_ohlc[s][4])] 


                elif (monthx > 9) and (monthx <= 12) :

                    date_sep = year+'-'+'12'
                    try :  seperate_data[date_sep] += [float(data_ohlc[s][4])]
                    except : seperate_data[date_sep] = [float(data_ohlc[s][4])] 

            seperate_data['b'] = [0]

        elif period == '4M' :

            for s in range(len(data_ohlc)) :

                datex = str(data_ohlc[s][0]).split('-')  #เลขบอกเดือนท่เท่าไหร่
                year = str(datex[0])
                month = str(datex[1])
                
                monthx = int(month) #ขอบเขตเดือน
                
                    
                if (monthx > 0) and (monthx <= 4) :
                    
                    date_sep = year+'-'+'04'
                    try :  seperate_data[date_sep] += [float(data_ohlc[s][4])]
                    except : seperate_data[date_sep] = [float(data_ohlc[s][4])] 


                elif (monthx > 4) and (monthx <= 8) :

                    date_sep = year+'-'+'08'
                    try :  seperate_data[date_sep] += [float(data_ohlc[s][4])]
                    except : seperate_data[date_sep] = [float(data_ohlc[s][4])] 


                elif (monthx > 8) and (monthx <= 12) :

                    date_sep = year+'-'+'12'
                    try :  seperate_data[date_sep] += [float(data_ohlc[s][4])]
                    except : seperate_data[date_sep] = [float(data_ohlc[s][4])] 

        elif period == '6M' :

            for s in range(len(data_ohlc)) :

                datex = str(data_ohlc[s][0]).split('-')  #เลขบอกเดือนท่เท่าไหร่
                year = str(datex[0])
                month = str(datex[1])
                
                monthx = int(month) #ขอบเขตเดือน
                
                    
                if (monthx > 0) and (monthx <= 6) :
                    
                    date_sep = year+'-'+'06'
                    try :  seperate_data[date_sep] += [float(data_ohlc[s][4])]
                    except : seperate_data[date_sep] = [float(data_ohlc[s][4])] 


                elif (monthx > 6) and (monthx <= 12) :

                    date_sep = year+'-'+'12'
                    try :  seperate_data[date_sep] += [float(data_ohlc[s][4])]
                    except : seperate_data[date_sep] = [float(data_ohlc[s][4])] 
        
        elif period == '12M' :

            check_month = []
            for s in range(len(data_ohlc)) :

                datex = str(data_ohlc[s][0]).split('-')  #เลขบอกเดือนท่เท่าไหร่
                year = str(datex[0])
                date_sep = year
                
                if s == 0 :
                    check_month.append(date_sep)                     #เพื่อ เช็คข้อมูล
                    seperate_data[date_sep] = [float(data_ohlc[s][4])]        #value แรกใน ดิก ต้องเป็น ลิสถึงจะบวกเพิ่มได้

                if (s > 0) and (date_sep == str(check_month[-1])) :
                    seperate_data[date_sep] += [float(data_ohlc[s][4])]

                elif (s > 0) and (date_sep != str(check_month[-1])) :  #ขึ้นเดือนใหม่
                    check_month.append(date_sep)                     #เพื่อ เช็คข้อมูล
                    seperate_data[date_sep] = [float(data_ohlc[s][4])]        #value แรกใน ดิก ต้องเป็น ลิสถึงจะบวกเพิ่มได้

        #endregion

        #region สร้าง Zone Low - high

        base = max_price - min_price
        constance = base / number_grid

        limit_zone = []
        high_zone = []  # grid ใช้ plot
        
        for li in range(number_grid) :
            limit_zone.append(min_price+(li*constance))
            limit_zone.append(min_price+((li+1)*constance))

            high_zone.append(float(stop%(min_price+((li+1)*constance))))

        limit_zonex = np.array(limit_zone).reshape(-1, 2)               #เรียง low - high ---- จากน้อยไปมาก
      

        #endregion

        #region แยกตามช่วงเวลา
        time_limit = list(seperate_data.keys())                        #คีย ของดิช

        keep_log = []

        for c in range(len(time_limit)) :                               #แยกช่วงเวลาออกมา

            price_for_count = seperate_data[time_limit[c]]
            count_even = {}                                             #นับเหตุการณ์ที่เกิดในแต่ละช่วง

            for xmt in range(len(limit_zonex)):                         #สร้าง dict ปล่าว
                count_even[limit_zonex[(xmt+1)*(-1)][1]] = 0
            
            for ct in range(len(price_for_count)):                      #จัดข้อมูลลงช่วงที่กำหนด
            
                cprice = price_for_count[ct]
                
                for mt in range(len(limit_zonex)):                    #จัดให้อยู่ในช่วงต่าง
                
                    low = limit_zonex[mt][0]
                    high = limit_zonex[mt][1]
                    
                    if mt == 0 :
                        if (cprice >= low) and (cprice <= high) :
                            count_even[high] += 1
                        
                    elif mt >= 0 :
                        if (cprice > low) and (cprice <= high) :
                            count_even[high] += 1

            key_even = list(count_even.keys())                          #ระดับ Zone(บน) ต่าง      

            for k in range(len(key_even)) : 
                keep_log.append(count_even[key_even[k]])
            
        high_pricex = np.array(high_zone).reshape(-1,1)
        high_pricey = np.flipud(high_pricex)

        keep_logx = np.array(keep_log).reshape(-1, number_grid)
        keep_logy = keep_logx.T

        #endregion

        #region สร้าง ความแขงแรงของ Zone + ส่งออกข้อมูล plot

        if strength == 'Y' :

            #หาผลรวม stregh zone
            zone_total = []
            for sz in range(len(keep_logy)):
                su = sum(keep_logy[sz])
                zone_total.append(int(su))
          
            zone_totalx = np.array(zone_total).reshape(-1, 1)

            sum_zone = np.hstack((high_pricey,keep_logy,zone_totalx))

            time_limit.insert(0,'')

            time_limit.append('strength')

        elif strength == 'N' :
            sum_zone = np.hstack((high_pricey,keep_logy))
            time_limit.insert(0,'p')
        
        show = pd.DataFrame(sum_zone, columns = time_limit)
        show.set_index('p', inplace=True)
    
        #endregion
        
        return show, ohlcx, constance, last_index, last_price, high_zone, min_price, max_price

    def find_other_ema(list_data, ema_range):
        #ค่าถ่วงน้ำหนัก
        alp = 2 / (ema_range +1)

        find_sma_begin = []  #เอาใว้สร้าง SMA ตัวแรก
        ema_volumex = []     #เอาใว้สร้าง EMA Volume

        for apx in range(len(list_data)) :
            vox = list_data[apx]

            if apx < (ema_range - 1) :
                find_sma_begin.append(vox) 
                ema_volumex.append(None) 
            
            elif apx == (ema_range - 1) :

                find_sma_begin.append(vox)

                sma = sum(find_sma_begin) / ema_range

                ema_volumex.append(sma)
            
            elif apx > (ema_range - 1) :
                ema_x = (vox * alp) + ( float(ema_volumex[-1]) * (1-alp) )
                ema_volumex.append(ema_x)

        return ema_volumex

    def auto_trandline(mode, tf, np_numpy, number, min_max_nox):
       
        def check_trend_line(support: bool, pivot: int, slope: float, y: np.array):
            # compute sum of differences between line and prices, 
            # return negative val if invalid 
            
            # Find the intercept of the line going through pivot point with given slope
            intercept = -slope * pivot + y.iloc[pivot]

            line_vals = slope * np.arange(len(y)) + intercept
            
            diffs = line_vals - y
            
            # Check to see if the line is valid, return -1 if it is not valid.
            if support and diffs.max() > 1e-5:
                return -1.0
            elif not support and diffs.min() < -1e-5:
                return -1.0

            # Squared sum of diffs between data and line 
            err = (diffs ** 2.0).sum()
            return err

        def optimize_slope(support: bool, pivot:int , init_slope: float, y: np.array):
            
            # Amount to change slope by. Multiplyed by opt_step
            slope_unit = (y.max() - y.min()) / len(y) 
            
            # Optmization variables
            opt_step = 1.0
            min_step = 0.0001
            curr_step = opt_step # current step
            
            # Initiate at the slope of the line of best fit
            best_slope = init_slope
            best_err = check_trend_line(support, pivot, init_slope, y)
            assert(best_err >= 0.0) # Shouldn't ever fail with initial slope

            get_derivative = True
            derivative = None
            while curr_step > min_step:

                if get_derivative:
                    # Numerical differentiation, increase slope by very small amount
                    # to see if error increases/decreases. 
                    # Gives us the direction to change slope.
                    slope_change = best_slope + slope_unit * min_step
                    test_err = check_trend_line(support, pivot, slope_change, y)
                    derivative = test_err - best_err
                    
                    # If increasing by a small amount fails, 
                    # try decreasing by a small amount
                    if test_err < 0.0:
                        slope_change = best_slope - slope_unit * min_step
                        test_err = check_trend_line(support, pivot, slope_change, y)
                        derivative = best_err - test_err

                    if test_err < 0.0: # Derivative failed, give up
                        raise Exception("Derivative failed. Check your data. ")

                    get_derivative = False

                if derivative > 0.0: # Increasing slope increased error
                    test_slope = best_slope - slope_unit * curr_step
                else: # Increasing slope decreased error
                    test_slope = best_slope + slope_unit * curr_step
                

                test_err = check_trend_line(support, pivot, test_slope, y)
                if test_err < 0 or test_err >= best_err: 
                    # slope failed/didn't reduce error
                    curr_step *= 0.5 # Reduce step size
                
                else: # test slope reduced error
                    best_err = test_err 
                    best_slope = test_slope
                    get_derivative = True # Recompute derivative
            
            # Optimize done, return best slope and intercept
            return (best_slope, -best_slope * pivot + y.iloc[pivot])

        def fit_trendlines_single(data: np.array):
            # find line of best fit (least squared) 
            # coefs[0] = slope,  coefs[1] = intercept 
            x = np.arange(len(data))
            coefs = np.polyfit(x, data, 1)

            # Get points of line.
            line_points = coefs[0] * x + coefs[1]

            # Find upper and lower pivot points
            upper_pivot = (data - line_points).argmax() 
            lower_pivot = (data - line_points).argmin() 
        
            # Optimize the slope for both trend lines
            support_coefs = optimize_slope(True, lower_pivot, coefs[0], data)
            resist_coefs = optimize_slope(False, upper_pivot, coefs[0], data)

            return (support_coefs, resist_coefs) 

        def fit_trendlines_high_low(high: np.array, low: np.array, close: np.array):
            x = np.arange(len(close))
            coefs = np.polyfit(x, close, 1)
            # coefs[0] = slope,  coefs[1] = intercept
            line_points = coefs[0] * x + coefs[1]
            upper_pivot = (high - line_points).argmax() 
            lower_pivot = (low - line_points).argmin() 
            
            support_coefs = optimize_slope(True, lower_pivot, coefs[0], low)
            resist_coefs = optimize_slope(False, upper_pivot, coefs[0], high)

            return (support_coefs, resist_coefs)

        def get_line_points(candles, line_points):
            # Place line points in tuples for matplotlib finance
            # https://github.com/matplotlib/mplfinance/blob/master/examples/using_lines.ipynb
           
            idx = candles.index
            line_i = len(candles) - len(line_points)
            assert(line_i >= 0)
            points = []
            for i in range(line_i, len(candles)):
                points.append((idx[i], line_points[i - line_i]))
           
            return points

  

        #จำนวนช่วงที่ต้องการหา
        range_dn = int(len(np_numpy) / number)
        dnx = []
        for dx in range(number) :
            
            if dx == 0 :
                dnx.append(0)
           
            elif (dx > 0) and (dx < number):
                dnx.append(range_dn * dx)
       

        #แปลงรูปแบบวัน และ float
        datex = []
        for dx in range(len(np_numpy)) :
            d = str(np_numpy[dx][0])

            if (tf == '1D') or (tf == '1d') :
                d1 = d.split(' ')
                datex.append(d1[0])
            
            elif (tf != '1D') or (tf != '1d') :
                d1 = d.split('+')
                d2 = d1[0].split(' ')
                d3 = d2[0]+'T'+d2[1]

                datex.append(d3)



        #แปลง ข้อมูล
        try : #กรณีนี้เกิดขึ้นเมื่อ เป็นข้อมูลมาจาก candles_y
            data = pd.DataFrame(np_numpy, columns = ['time','open','high','low','close','volume','Color'])
            data.drop(columns =['time','volume','Color'], inplace=True)
        
        except : #กรณีนี้เกิดขึ้นเมื่อ เป็นข้อมูลมาจาก total candles asr เพราะข้อมูลสร้างใหม่ แบบไม่ได้จัด
            data = pd.DataFrame(np_numpy, columns = ['time','open','high','low','close','volume'])
            data.drop(columns =['time','volume'], inplace=True)

        

        data['date'] = datex

        data['date'] = data['date'].astype('datetime64[s]')
        data = data.set_index('date')

        data['open'] = data['open'].astype(float)
        data['high'] = data['high'].astype(float)
        data['low'] = data['low'].astype(float)
        data['close'] = data['close'].astype(float)
   

        #ระยะเส้นที่นำมาคำนวน
        loz = []
        loz_net = []
       
        for oz in range(len(dnx)) :
           
            candles = data[dnx[oz]:]

            #region หาจุด Y ทุกจุด

            if mode == 'oc' : #open Close
                support_coefs_c, resist_coefs_c = fit_trendlines_single(candles['close'])

                resist_line = resist_coefs_c[0] * np.arange(len(candles)) + resist_coefs_c[1]
                support_line = support_coefs_c[0] * np.arange(len(candles)) + support_coefs_c[1]
                
            elif mode == 'lh' :  #low high
                support_coefs, resist_coefs = fit_trendlines_high_low(candles['high'], candles['low'], candles['close'])

                resist_line = resist_coefs[0] * np.arange(len(candles)) + resist_coefs[1]
                support_line = support_coefs[0] * np.arange(len(candles)) + support_coefs[1]
            
            #endregion

            #region กำหนด limit ราคา จากบนลงล่าง  สำหรับแสดงใน NETZONE
            resist_linex = []
            support_linex = []

            if len(min_max_nox) != 0 :
                
                #จุดปลาย สุดของเส้น ทั้งสอง
                res_last = resist_line[-1]
                sup_last = support_line[-1]

                # จุดปลายสุด res อยู่ใน min <= x <= max หรือไม่
                if (res_last >= min_max_nox[0]) and (res_last <= min_max_nox[1]) :
                    
                    #loop หาแต่ละจุดว่าจุดไหนเข้าเงื่่อนไข
                    for rl in range(len(resist_line)):
                        rl_y = resist_line[rl]

                        # ถ้าจุด อยู่ใน min <= x <= max หรือไม่
                        if (rl_y >= min_max_nox[0]) and (rl_y <= min_max_nox[1]) : resist_linex.append(rl_y)

                        
                # จุดปลายสุด sup อยู่ใน min <= x <= max หรือไม่
                if (sup_last >= min_max_nox[0]) and (sup_last <= min_max_nox[1]) :

                    for sl in range(len(support_line)):
                        sl_y = support_line[sl]

                        if (sl_y >= min_max_nox[0]) and (sl_y <= min_max_nox[1]) : support_linex.append(sl_y)


                limit_resist_line = list(filter(lambda num: (num >= min_max_nox[0]) and (num <= min_max_nox[1]) , resist_line))
                limit_support_line = list(filter(lambda num: (num >= min_max_nox[0]) and (num <= min_max_nox[1]) , support_line))
                    
            #endregion

            #region หาจุด X1 X2 Y1 Y2

            r_seq = get_line_points(candles, resist_line)
            r_x1 = dnx[oz]
            r_x2 = len(data) - 1
            r_y1 = float(r_seq[0][1])
            r_y2 = float(r_seq[-1][1])

            s_seq = get_line_points(candles, support_line)
            s_x1 = dnx[oz]
            s_x2 = len(data) - 1
            s_y1 = float(s_seq[0][1])
            s_y2 = float(s_seq[-1][1])


            loz.append(r_x1)
            loz.append(r_x2)
            loz.append(r_y1)
            loz.append(r_y2)

            loz.append(s_x1)
            loz.append(s_x2)
            loz.append(s_y1)
            loz.append(s_y2)
            
            #endregion
            
            #region กำหนด limit datetime ซ้าย ไป ขวา สำหรับแสดงใน NETZONE
          
            if len(min_max_nox) != 0 : 
                
                
                if len(resist_linex) != 0 :

                    if len(resist_linex) >= min_max_nox[2] :  
                        rn_x1 = 0
                        rn_y1 = float(resist_linex[-min_max_nox[2]])  #ถ้ายาวกว่า ใน net กำหนด
                    
                    elif len(resist_linex) <= min_max_nox[2] : 
                        rn_x1 = min_max_nox[2] - len(resist_linex)
                        rn_y1 = float(resist_linex[0]) #ถ้าสั้นกว่า ใน net กำหนด
                    
                    rn_x2 = min_max_nox[2] - 1
                    rn_y2 = float(resist_linex[-1])

                    loz_net.append(rn_x1)
                    loz_net.append(rn_x2)
                    loz_net.append(rn_y1)
                    loz_net.append(rn_y2)


                if len(support_linex) != 0 :

                    if len(support_linex) >= min_max_nox[2] :  
                        sn_x1 = 0
                        sn_y1 = float(support_linex[-min_max_nox[2]])  #ถ้ายาวกว่า ใน net กำหนด
                    
                    elif len(support_linex) <= min_max_nox[2] : 
                        sn_x1 = min_max_nox[2] - len(support_linex)
                        sn_y1 = float(support_linex[0]) #ถ้าสั้นกว่า ใน net กำหนด
                    
                    sn_x2 = min_max_nox[2] - 1
                    sn_y2 = float(support_linex[-1])

                    
                    loz_net.append(sn_x1)
                    loz_net.append(sn_x2)
                    loz_net.append(sn_y1)
                    loz_net.append(sn_y2)

            #endregion 


        line_of_zone = np.array(loz).reshape(-1,4)
        line_of_zone_net = np.array(loz_net).reshape(-1,4)
        
        #plt.style.use('dark_background')
        #ax = plt.gca()
        #mpf.plot(candles, alines=dict(alines=[s_seq, r_seq, s_seq2, r_seq2], colors=['w', 'w', 'b', 'b']), type='candle', style='charles', ax=ax)
        #plt.show()
        #print(1)

        return line_of_zone, line_of_zone_net

    def mid_area_auto_trandline(table_xy):
        #สร้างเส้นกลาง support restance
        mid_value_begin = ((float(table_xy[-2][2]) - float(table_xy[-1][2])) / 2) + float(table_xy[-1][2])
        mid_value_end = ((float(table_xy[-2][3]) - float(table_xy[-1][3])) / 2) + float(table_xy[-1][3])
        
        #สำหรับ red
        rloz_up = [table_xy[-2][0], table_xy[-2][1], table_xy[-2][2], table_xy[-2][3]]
        rloz_lo = [table_xy[-2][0], table_xy[-2][1], mid_value_begin, mid_value_end]
        #สำหรับ green
        gloz_up = [table_xy[-1][0], table_xy[-1][1], mid_value_begin, mid_value_end]
        gloz_lo = [table_xy[-1][0], table_xy[-1][1], table_xy[-1][2], table_xy[-1][3]]

        return mid_value_end, rloz_up, rloz_lo, gloz_up, gloz_lo

    def plot_area(ax, low_line, high_line, colorx, al)  : #line is list
        
        l_x1 = float(low_line[0])
        l_x2 = float(low_line[1])
        l_y1 = float(low_line[2])
        l_y2 = float(low_line[3]) 

        u_x1 = float(high_line[0])
        u_x2 = float(high_line[1])
        u_y1 = float(high_line[2])
        u_y2 = float(high_line[3]) 

        pts = [(u_x1, u_y1), (u_x2, u_y2), (l_x2, l_y2), (l_x1, l_y1)]

        triangle = Polygon(pts, color = colorx, alpha = al)
    
        ax.add_patch(triangle)

    def sort_dict_by_value(dict_input) :
            
        dictx = sorted(dict_input.items(), key = lambda x:x[1], reverse=True)

        return dictx

    def find_semi_hm_supplot(all_val_supplot, min_low, max_high, last_price) :

        all_supplot = all_val_supplot.copy() #เพื่อให่ให้ส่งค่ากลับไปเปลี่ยนแปลง input value

        #สร้างเส้นรอง ขั้น ต่อไป สำหรับ Net zone อย่างเดียว------------------------------------
        def fine_id_val_half (main_net):

            index = 0
            val = 0

            for i in range(len(main_net)):

                if i == len(main_net)-1 :
                    break

                base_up = float(main_net[i])
                base_lo = float(main_net[i+1])

                #เพิ่มเส้น จาก supplot
                if (last_price > base_lo) and (last_price < base_up):
                    
                    b1 = (base_up - base_lo) / 2 
                    b2 = base_lo + b1
                    
                    index += i+1
                    val += b2
                    
                    break
            
            return index, val
        
        def fine_limit_suplot (all_plot):

            net_sp_zone = []
            min_val = []

            for spd in range(len(all_plot)) :

                sp = float(all_plot[spd])

                if ( sp >= float(min_low) ) and ( sp <= float(max_high) ) :
                    
                    # ถ้าต้องการเพิ่มตัวก่อนหน้า
                    #if len(net_sp_zone) == 0 :
                    #    try : net_sp_zone.append(float(all_plot[spd-1]))
                    #    except : pass
                    
                    net_sp_zone.append(sp)
                    min_val.append(spd)

            #ถ้าต้องการเพิ่มตัวน้อยเข้าอีก
            #try : net_sp_zone.append(float(all_plot[int(min_val[-1])+1]))
            #except : pass
              



            return net_sp_zone
    
        #แสดง Support Resistance--------------------------------------------

        #เช็คว่านำไปแสดงมีกี่เส้น
        
        no_supplot_mark = fine_limit_suplot(all_supplot)

        if len(no_supplot_mark) <= 3 : #ถ้าน้อยกว่าให้เพิ่ม 2 เส้น
            
            #เส้นที่ 1 สร้าง แล้ว ใน heatmap
            #สร้างเส้น รองที่ 2
            index2, val2 = fine_id_val_half (all_supplot)
            all_supplot.insert(index2, val2)

            #สร้างเส้น รองที่ 3
            index3, val3 = fine_id_val_half (all_supplot)
            all_supplot.insert(index3, val3)

            #สร้างเส้น รองที่ 4
            #index4, val4 = fine_more_to_i (sup_plot_net)
            #sup_plot_net.insert(index4, val4)

            # new gen
            net_sp_zonex = fine_limit_suplot(all_supplot)

        elif len(no_supplot_mark) > 3 : #ถ้ามากกว่า ไม่ต้องเพิ่มเอาเลย

            net_sp_zonex = no_supplot_mark.copy()


        return net_sp_zonex

    def setting_symbol(ex, sym, dn_pandas):
        
        
        #region ดึงข้อมูลที่ตั้งค่า

        if ex == 'bitkub' :
            grid_begin = bitkub_symbol_setting[sym]['grid_begin'] 
            grid_range = bitkub_symbol_setting[sym]['grid_range']  
        
        elif ex == 'binance' :
            grid_begin = binance_symbol_setting[sym]['grid_begin'] 
            grid_range = binance_symbol_setting[sym]['grid_range']

        #endregion

        #region กำหนด ขอบเขต ohlcv

        if len(dn_pandas) >= no_candles :
            no_candx = no_candles
            

        elif len(dn_pandas) < no_candles :
            no_candx = len(dn_pandas)
        
        setting_cand = dn_pandas[len(dn_pandas) - no_candx: ]
        setting_cand.reset_index(drop=True, inplace=True)
        #endregion

        #region--------------------------------------------------------------สร้าง เส้นนอน ราคา horizontial_line
        
        old_min_low = dn_pandas['Low'].min()
        new_max_high = max(setting_cand['High'])
        new_min_low = min(setting_cand['Low'])

        #หา max ที่เหมือนกันไม่ว่าเราจะตั้ง คาเริ่มต้นต่ำหรือสูงกว่า
        price_max = []
        
        #ถ้าจะทดสอบต้องตั้งค่าสองอันนี้
        if float(grid_begin) >= float(new_max_high) :
        
            make_begin_price = [float(grid_begin)]

            while make_begin_price[-1] >= float(new_max_high) :
            
                val_h = make_begin_price[-1] - float(grid_range)
                make_begin_price.append(val_h)
            
            price_max.append(make_begin_price[-2])
        
        elif float(grid_begin) <= float(new_max_high) :
        
            make_begin_price = [float(grid_begin)]

            while make_begin_price[-1] <= float(new_max_high) :
            
                val_h = make_begin_price[-1] + float(grid_range)
                make_begin_price.append(val_h)

            price_max.append(make_begin_price[-1])

        #ไล่ราคาจากแท่ง สูงสุดลงไป
        grid_cand = [price_max[-1]]

        while grid_cand[-1] >= float(new_min_low) :
            range_dy = grid_cand[-1] - float(grid_range)
            grid_cand.append(range_dy)
        
        grid_cand.reverse()      


        #หา all horizontial  อันนี้เอา
        grid_all = [grid_begin] 
        
        while float(grid_all[-1]) >= float(old_min_low) :
            grid_all.append(float(grid_all[-1]) - float(grid_range))
        

        #endregion

        
        return setting_cand, grid_all, grid_cand

    def setting_volume_show (dn_pandas) : #เปลี่ยนรูป แบบ การโชว์ vol

        if fillter_vol > 0 :
            max_vol_in_cand = dn_pandas['Volume'].max()
            diff_vic = float(max_vol_in_cand / fillter_vol)
            dn_pandas.loc[dn_pandas['Volume'] < diff_vic, 'Volume'] = 0
        
        elif fillter_vol == 0 : #ปิดการใช้งาน เลยไม่เขียน
            pass

        elif fillter_vol == -1 :
           
            diff_vic = float(dn_pandas['Volume'][len(dn_pandas)-1])
       
            #ตั้งค่ารูปแบบ bar ที่ใช้แสดง
            dn_pandas.loc[dn_pandas['Volume'] < diff_vic, 'Volume'] = 0

      
        return dn_pandas
           
    def candles_with_other(dn_pandas, ax_candles, ax_vol, itype, istyle='yahoo'):  #'candle' 'yahoo'
        
        clone_dn_pandas = dn_pandas.copy()
        clone_dn_pandas['Time'] = pd.to_datetime(clone_dn_pandas['Time'], format = '%Y-%m-%d %H:%M:%S')
        clone_dn_pandas.set_index('Time', inplace=True)
      
        mpf.plot(clone_dn_pandas, ax=ax_candles, type=itype, style=istyle, volume = ax_vol)

    def tranfer_scale(range_bar, min_sr, max_sr, input_val) :

        #max min scale bar
        dif_sr = max_sr - min_sr

        #แปลง input value เป็น area
        area_input = input_val - min_sr

        scale_to_bar = (range_bar * area_input) / dif_sr

        return scale_to_bar
       
    def candlestick_to_heiken(dn_numpy):
        
        heiken = []

        for h in range(len(dn_numpy)) :

            hei_close = (float(dn_numpy[h][1]) + float(dn_numpy[h][2]) + float(dn_numpy[h][3]) + float(dn_numpy[h][4]))/ 4
            
            if h == 0 : 
                
                hei_open = (float(dn_numpy[h][1]) + float(dn_numpy[h][4])) / 2
                hei_high =  float(dn_numpy[h][2])
                hei_low = float(dn_numpy[h][3])
            
            elif h > 0 : 
                
                hei_open = (float(heiken[-4]) + float(heiken[-1])) / 2  #เอามาจากlist

                hh = [float(dn_numpy[h][2]), float(hei_open), float(hei_close)]
                hei_high = max(hh)

                hl = [float(dn_numpy[h][3]), float(hei_open), float(hei_close)]
                hei_low = min(hl)

            heiken.append(dn_numpy[h][0])
            heiken.append(hei_open)
            heiken.append(hei_high)
            heiken.append(hei_low)
            heiken.append(float(hei_close))

        heikenx = np.array(heiken).reshape(-1,5)

        
        heikeny = pd.DataFrame(heikenx, columns = ['Time','Open','High','Low','Close'])

        #เปลี่ยน แกน x จาก index เป็น datetime
        #heikeny['Time'] = pd.to_datetime(heikeny['Time'])
        #heikeny['Time'] = heikeny['Time'].apply(mdates.date2num)
        
        heikeny['Open'] = heikeny['Open'].astype(float)
        heikeny['High'] = heikeny['High'].astype(float)
        heikeny['Low'] = heikeny['Low'].astype(float)
        heikeny['Close'] = heikeny['Close'].astype(float)

        #heikeny['Color'] = heikeny['Close'] - heikeny['Open']
        #heikeny['Color'] = heikeny['Color'].astype(float)

        return heikeny

    def observation_next(list_datetime): #2024-12-08 07:00:00
        
        t_form = '%Y-%m-%d %H:%M:%S'

        list_datetimex = list_datetime.copy()

        last_date = datetime.strptime(str(list_datetimex[-1]), t_form)

        #หาค่า diff จาก date ล่าสุดที่อยู่ใน cand
        d1 = datetime.strptime(str(list_datetimex[-2]), t_form)
        d0 = datetime.strptime(str(list_datetimex[-1]), t_form)
        dx =  d0 - d1
        days, seconds = dx.days, dx.seconds
        hox = days * 24 + seconds // 3600

        #เพิ่มข้อมูลไปด้านหน้า
        for ad in range(observation_cand) :
            
            list_datetimex.append(str(last_date + timedelta(hours = hox * (ad+1))))
        
    
        return list_datetimex

    def countdown(countdown_time,word): #ใส่เลขวินาที

        while countdown_time:
            mins, secs = divmod(countdown_time, 60)
            timer = f'{mins:02d}:{secs:02d}'
            print(f'\r⏳ {word} : {timer}', end='')
            time.sleep(1)
            countdown_time -= 1

class INDICATOR:

    def RSI(df, lengthx):

        i_rsi = ta.rsi(df['Close'], lengthx)

        return i_rsi
    
    def MACD(df, fast, slow, signal):
        
        #signal histogram macd
        i_macd = ta.macd(df['Close'], fast, slow, signal)

        return i_macd
    
    def BBAND(df, lengthx, std):
        
        #low mid upper X X
        i_bband = ta.bbands(df['Close'], lengthx, std)
        
        return i_bband
    
    def STOCASTIC_RSI(df, lengthx, rsi_len, k, d):

        #fast  slow
        i_sto_rsi = ta.stochrsi(df['Close'], lengthx, rsi_len, k, d)

        return i_sto_rsi
        
    def EMA(df, ma):
        
        
        close = df['Close']
        i_ema = ta.ema(close, ma)
        
        
        return i_ema


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

def Bitkub_mot(sym,tf):
    
    #region-------------------------------------------------------- TIME

    try :
        utc_stp = bitkub.servertime()    #Time stamp
        if "linux" in this_system: #Raspberry Pi
            #เฉพาะใน rasberry pi ให้หาร 1000 เพราะใช้ เวอชั่น 3.13.5
            now_datetime = datetime.fromtimestamp(float(utc_stp)/1000).replace(microsecond=0)
        
        elif "windows" in this_system: # สำหรับ Windows (เช่น PC)
            now_datetime = datetime.fromtimestamp(float(utc_stp)).replace(microsecond=0)

    except :

        utc_stp = SUB_FUCTION.servertime()    #Time stamp
        if "linux" in this_system: #Raspberry Pi
            #เฉพาะใน rasberry pi ให้หาร 1000 เพราะใช้ เวอชั่น 3.13.5
            now_datetime = datetime.fromtimestamp(float(utc_stp)/1000).replace(microsecond=0)
        
        elif "windows" in this_system: # สำหรับ Windows (เช่น PC)
            now_datetime = datetime.fromtimestamp(float(utc_stp)/1000).replace(microsecond=0)
    
    last_date.clear()
    last_date.append(now_datetime)

    #name time
    t0 = str(now_datetime).split(' ')
    t1 = str(t0[0]).split('-')
    t2 = str(t0[1]).split(':')

    #endregion

    stop = SUB_FUCTION.Find_stop_bitkub(sym)[0]

    dn = SUB_FUCTION.Bitkub_ohlcv_UTC(sym,tf,start_date)
    main_momentum('bitkub',sym,dn,stop,tf,32,'1M','N')
    
def Binance_mot(sym,tf):
    
    #region-------------------------------------------------------- TIME

    try :
        utc_stp = bitkub.servertime()    #Time stamp
        if "linux" in this_system: #Raspberry Pi
            #เฉพาะใน rasberry pi ให้หาร 1000 เพราะใช้ เวอชั่น 3.13.5
            now_datetime = datetime.fromtimestamp(float(utc_stp)/1000).replace(microsecond=0)
        
        elif "windows" in this_system: # สำหรับ Windows (เช่น PC)
            now_datetime = datetime.fromtimestamp(float(utc_stp)).replace(microsecond=0)

    except :

        utc_stp = SUB_FUCTION.servertime()    #Time stamp
        if "linux" in this_system: #Raspberry Pi
            #เฉพาะใน rasberry pi ให้หาร 1000 เพราะใช้ เวอชั่น 3.13.5
            now_datetime = datetime.fromtimestamp(float(utc_stp)/1000).replace(microsecond=0)
        
        elif "windows" in this_system: # สำหรับ Windows (เช่น PC)
            now_datetime = datetime.fromtimestamp(float(utc_stp)/1000).replace(microsecond=0)
    
    last_date.clear()
    last_date.append(now_datetime)

    #name time
    t0 = str(now_datetime).split(' ')
    t1 = str(t0[0]).split('-')
    t2 = str(t0[1]).split(':')

    #endregion

    stop = SUB_FUCTION.Find_stop_binance(sym)[0]

    dn = SUB_FUCTION.Binance_ohlcv_UTC('spot','ohlcv',sym,tf,start_date)

    main_momentum('binance',sym,dn,stop,tf,32,'1M','N')
    
def main_momentum(ex,sym,dn,stop,tf,range_heatmap,period_ht,strength_ht): 

    print('...'+ex+'-'+sym+'-'+str(tf)+'=>'+str(last_date[-1]), flush=True)

    #region-------------------------------------------------------- FIREBASE

    sym_firebase = (sym.upper())+str(tf)
    
    #endregion

    #region-------------------------------------------------------- Momentum
    
    #print('...RECEIVE OHLCV & MOMENTUM ANALISE', flush=True)
    #เดือนกุมภา มีสองเส้นเนื่องจาก ข้อมูลที่รับมา มันมีสองค่า
    
    candles_pd = pd.DataFrame(dn, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
    candles_pd['Time'] = pd.to_datetime(candles_pd['Time']).dt.strftime('%Y-%m-%d %H:%M:%S')

    #ปิดไว้ เพราะ กำหนด รูปแบบใหม่

    candles_pd[['Open','High','Low','Close','Volume']] = candles_pd[['Open','High','Low','Close','Volume']].astype(float)
    
    #สร้าง ตารางสี
    candles_pd['Color'] = (candles_pd['Close'] >= candles_pd['Open']).astype(int)
    
    candles_np = np.array(candles_pd)    

    if ex == 'bitkub' : #คำความแตกต่าง ราคากับ binance spot

        compair_broke = {'000':['forcast','Compair']}

        #กำหนดจุดเริ่มในการ เก็บข้อมูล
        if len(candles_np) >= no_candles :
            start_pair_id = no_candles
        elif len(candles_np) < no_candles :
            start_pair_id = len(candles_np)
        
        binance_ohlcv = SUB_FUCTION.Binance_ohlcv_UTC('spot','ohlcv',sym, tf_bit_to_bin[tf], start_pair_id)


        try :    

            # หาความต่าง broker
            for i in range(start_pair_id) :

                bitkub_open =  float(candles_np[-start_pair_id+i][1])
                bitkub_close = float(candles_np[-start_pair_id+i][4])
                per_bitkub = bitkub_close / bitkub_open
                
                binance_open = float(binance_ohlcv[i][1])
                binance_close = float(binance_ohlcv[i][4])
                per_binance = binance_close / binance_open

                # vitkub ต่างกับ binance อยู่ กี่ % bitkub - binance
                cal_oc = per_bitkub - per_binance
                
                # ราคาควรจะเป็นเท่าไหร่
                compare_price = bitkub_open * per_binance


                if len(compair_broke) < 10 : dbn = '00'+str(len(compair_broke))
                else : dbn = '0'+str(len(compair_broke))

                #บันทึกรอใส่ ใน firebase
                compair_broke[dbn] = [compare_price, cal_oc]

                
                #ตรวจเฉพาะตัวสุดท้าย
                if i == (start_pair_id - 1) :

                    #แจ้งเตือน line ถ้า ต่างกันเกิน broker_pair_value
                    if  ( cal_oc <= (broker_pair_value * (-1)) ) or (cal_oc >= broker_pair_value ) :
                        
                        symtf = sym+str(tf)
                        path_notify = "/home/mir/robot/compair_"+symtf+".notify"
                        
                        #สร้างไฟล์ เพื่อให้รู้ว่า รันสำเร็จแล้ว
                        if not os.path.exists(path_notify):

                            #สร้างไฟล์เพื่อไม่ให้แจ้งเตือนช้ำ  แล้วเงื่อนนไขลบอยู่ใน ไฟล์ main.py
                            if "linux" in this_system: 

                                open(path_notify, "w").close() 

                                if per_bitkub >= per_binance :
                                    conn_ext = 'Bitkub มากกว่า Binance = '
                                    final_t = '% การขาย กำลังจะเกิดขึ้น'
                                else :
                                    conn_ext = 'Bitkub น้อยกว่า Binance = '
                                    final_t = '% การซื้อ กำลังจะเกิดขึ้น'
                                
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                text = '...ประกาศ!!! เวลา => '+str(now_str)+' '+symtf+' เกิดความแตกต่างระหว่าง Broker '+conn_ext+str('%.2f'%cal_oc)+final_t

                                send_line_message(access_token,text)

            #region บันทึก compair ไป fire base
            if len(compair_broke) != 1 :
                db.reference('/'+'Momentum/'+ex+'/compair/'+sym_firebase).set(compair_broke)
              
        except :
            pass

    #endregion

    #region สร้าง heiken

    candles_heiken = SUB_FUCTION.candlestick_to_heiken(candles_np)
        
    #endregion

    #region หาข้อมูลทำ order block

    # แปลงข้อมูลเป็น list
    sort_vol = candles_pd['Volume'].to_list()

    #ค่านี้เป็น ind ที่มี Vol ที่มากสุด n อันดับ เพื่อนำไปทำ เป็น order block
    # เอาเฉพาค่าที่เป็น id
    index_ob = []

    if mode_order_block == 1 :

        #หา vol ที่มากสุดอันดับที่ n
        sort_vol.sort()

        sort_voly = sort_vol[ -no_order_block : ]

        for sv in range(len(sort_voly)) :

            ob = float(sort_voly[sv])
            ind_ob = np.where(candles_pd['Volume'] == ob)
            index_ob.append(int(ind_ob[0][0]))
    
    elif mode_order_block == 2 :

        # สร้างช่วงค่า
        range_cand = int( len(candles_pd) / no_order_block )
        
        # id เริ่ม
        range_step = 0

        for rs in range(no_order_block) :
            
            # เอาตั้งแต่ id ที่กำหนด ถึง id ที่กำหนด
            if rs != (no_order_block - 1) :
                cand_in_range = sort_vol[ range_step : (range_cand * ( rs + 1))]
                cand_in_range.sort()

                max_in_range = float(cand_in_range[-1])
                ind_mir = np.where(candles_pd['Volume'] == max_in_range)
                index_ob.append(int(ind_mir[0][0]))

                range_step += range_cand
            
            # เอาาตั้งแต่ id ที่กำหนด ถึง 9y;l6fmhkp
            elif rs == (no_order_block - 1) :
                cand_in_range = sort_vol[ range_step : ]
                cand_in_range.sort()

                max_in_range = float(cand_in_range[-1])
                ind_mir = np.where(candles_pd['Volume'] == max_in_range)
                index_ob.append(int(ind_mir[0][0]))
    
    elif mode_order_block == 3 :

        #หาจุดมากสุด และ ต่ำสุด
        max_of_cand = candles_pd['High'].max()
        min_of_cand = candles_pd['Low'].min()
        diff_mx_mn = (max_of_cand - min_of_cand) / no_order_block

        lo_zone = min_of_cand
        up_zone = float(min_of_cand + diff_mx_mn)

        for mb in range(no_order_block) :


            # vol ที่อยู่ใน zone
            vol_of_zone = []

            for bx in range(len(candles_pd)) :
                c_close = float(candles_pd['Close'][bx])
                v_vol = float(candles_pd['Volume'][bx])

                if (c_close > lo_zone) and (c_close <= up_zone) :
                    vol_of_zone.append(v_vol)

            index_ob.append(np.where(candles_pd['Volume'] == max(vol_of_zone))[0][0])
            
            
            lo_zone += diff_mx_mn
            up_zone += diff_mx_mn

    #endregion


    #endregion    
  
    #region-------------------------------------------------------- INDICATOR
    
    #print('...INDICATORs ANALISE', flush=True)

    def find_ema(ema,key):  # ส่งออก emax, color_ema, i_emaf, i_emas

        try :
            
            #region หา EMA
            ema_f =  np.array(INDICATOR.EMA(candles_pd, int(ema[0]))).reshape(-1,1)
            ema_s =  np.array(INDICATOR.EMA(candles_pd, int(ema[1]))).reshape(-1,1)

            #print(ema_f[-5:])
            #print()
            
            #endregion
            
            #region ไม่เอาทั้งหมด 
            
            if len(candles_pd) > no_candles_indy : 
                dif = no_candles_indy * (-1)    #เอาตั้งแต่ -x ถึง ตัวสุดท้าย
            elif len(candles_pd) < no_candles_indy : 
                dif = 0     #เอาทุกตัว

            sumema = np.hstack((ema_f,ema_s))
            sumemax = sumema[int(dif):]
            
            #endregion
            
            #region color ค่า+-

            i_emax = pd.DataFrame(sumemax, columns = ['Fast','Slow'])
            i_emaf = i_emax['Fast'].astype(float)
            i_emas = i_emax['Slow'].astype(float)


            dif_ema = []
            for d in range(len(i_emaf)) :
                dife = float(i_emaf[d]) - float(i_emas[d])
                dif_ema.append(float(dife))

            #endregion
            
            #region detail

            try :   
                ema_detail = ema[2]
                buy_when = int(ema_detail[0])
                sell_when = int(ema_detail[1])

                #region ตัดเอาเฉพาะ ขีดจำกัดที่กำหนด ใช้ dif ema เป็นตวตัดสินเพราะเป็น บวกลบ

                if no_candles < no_candles_indy : #ถ้าจำนวนแท่งเทียนกับ indy เท่ากัน
                    
                    find_id_bs = dif_ema[-no_candles : ]
                    diff_cand = 0                     #เอาใว้ + ให้อินดี้ อินเดกตรง กับ แท่งเทียน

                elif no_candles >= no_candles_indy : #ถ้าจำนวนแท่งเทียน มากกว่า indy
                    find_id_bs = dif_ema.copy()
                    diff_cand = (no_candles - no_candles_indy)         #เอาใว้ + ให้อินดี้ อินเดกตรง กับ แท่งเทียน

                #endregion
                
                #region หา id ซื้อขาย
                
                id_buy_sell = {}

                for bsx in range(len(find_id_bs)) :

                    #กำหนดให้เริ่มเมื่อเข้าเงื่อนไข BUY
                    if bsx >= buy_when :

                        indy_b = find_id_bs[bsx - buy_when]          #indy อ้างอิง
                        indy_af_b = find_id_bs[bsx - buy_when + 1]   #indy หลังอ้างอิง

                        indy_last_b = find_id_bs[bsx]            #indy ล่าสุด

                        #ซื้อเมื่อ
                        if (indy_b < 0) and (indy_af_b >= 0) and (indy_last_b >= 0)  :
                            id_buy_sell[int(bsx + diff_cand)] = 'B'+ key
                                                    
                    #กำหนดให้เริ่มเมื่อเข้าเงื่อนไข SELL
                    if bsx >= sell_when :
                        indy_s = find_id_bs[bsx - sell_when]   #indy ก่อนหน้าตัวที่ x
                        indy_af_s = find_id_bs[bsx - sell_when + 1]   #indy หลังอ้างอิง
                        indy_last_s = find_id_bs[bsx]            #indy ล่าสุด

                        #ขายเมื่อ
                        if (indy_s > 0) and (indy_af_s <= 0) and (indy_last_s <= 0) :
                            id_buy_sell[int(bsx + diff_cand)] = 'S'+ key
                
                #endregion    

            except :
                
                id_buy_sell = {}
            
            #endregion
            
            ema_on_off = 1
                
        except :  
            dif_ema = []
            i_emaf = 0
            i_emas = 0
            id_buy_sell = {}

        return ema_on_off, dif_ema, i_emaf, i_emas, id_buy_sell

    try :
        
        name_tf = str(sym)+str(tf)
        
        #emax, color_ema, i_emaf, i_emas, id
        if ex == 'bitkub' :
            ema_swing = find_ema(bitkub_ema_set[name_tf]['swing'],'R')     #emax, color_ema, i_emaf, i_emas,
            ema_down = find_ema(bitkub_ema_set[name_tf]['down'],'D')
            ema_growth = find_ema(bitkub_ema_set[name_tf]['growth'],'G')
        
        elif ex == 'binance' :
            ema_swing = find_ema(binance_ema_set[name_tf]['swing'],'R')     #emax, color_ema, i_emaf, i_emas
            ema_down = find_ema(binance_ema_set[name_tf]['down'],'D')
            ema_growth = find_ema(binance_ema_set[name_tf]['growth'],'G')

    except :

        if ex == 'bitkub' :
            ema_swing = find_ema(bitkub_ema_set['BTC1D']['swing'],'R')
            ema_down = find_ema(bitkub_ema_set['BTC1D']['down'],'D')
            ema_growth = find_ema(bitkub_ema_set['BTC1D']['growth'],'G')
        
        elif ex == 'binance' :
            ema_swing = find_ema(binance_ema_set['BTC1d']['swing'],'R')
            ema_down = find_ema(binance_ema_set['BTC1d']['down'],'D')
            ema_growth = find_ema(binance_ema_set['BTC1d']['growth'],'G')

    # region หา id เพื่อ plot บน setting
    swing_on_off = ema_swing[0]
    swing_dif  = ema_swing[1]
    swing_fast  = ema_swing[2]
    swing_slow   = ema_swing[3]
    swing_bs_dict   = ema_swing[4]

    down_on_off = ema_down[0]
    down_dif  = ema_down[1]
    down_fast = ema_down[2]
    down_slow = ema_down[3]
    down_bs_dict = ema_down[4]

    growth_on_off = ema_growth[0]
    growth_dif  = ema_growth[1]
    growth_fast = ema_growth[2]
    growth_slow = ema_growth[3]
    growth_bs_dict = ema_growth[4]


    #endregion

    #endregion

    #region-------------------------------------------------------- Heat Map +  Main + Subplot กำหนด sup res

    #print('...HEATMAP ANALISE', flush=True)
    
    try :
                
        if ex == 'bitkub' :
            show, ohlcx, constance, last_index, last_price, high_zone, min_price, max_price = SUB_FUCTION.Heatmap('bitkub',sym,stop,range_heatmap,period_ht,strength_ht)
        
        elif ex == 'binance' :
            show, ohlcx, constance, last_index, last_price, high_zone, min_price, max_price = SUB_FUCTION.Heatmap('binance',sym,stop,range_heatmap,period_ht,strength_ht)
        

        #ค่ามากสุดน้อยสุด ใน Tf ที่เราเลือก
        
        ch_data = show.reset_index()
        set_p = ch_data['p'].to_list()
        set_p.append(min_price)

        max_tf = float(candles_pd['High'].max())
        min_tf = float(candles_pd['Low'].min())
        
        #สร้างเส้นหลักของ แนวต้านตาม Heat map ==> ไม่รวมเส้น ต่ำ และ สูงสุด
        all_hm_supplot = [x for x in set_p if (x >= min_tf) and (x <= max_tf) ]
        
        #ถ้าจำนวนเส้น น้อยวกว่า 6 ให้สร้างเส้นรอง ขั้น 1 + เส้นบน ล่างสุด
        if len(all_hm_supplot) <= 6 :
            
            #add บนล่าง
            val_add = float(all_hm_supplot[0] - all_hm_supplot[1])
            all_hm_supplot.insert(0, (all_hm_supplot[0] + val_add))
            all_hm_supplot.append(all_hm_supplot[-1] - val_add)

            
            #add 1st
            for sp1 in range(len(all_hm_supplot)):

                if sp1 == len(all_hm_supplot)-1 :
                    break

                base_up = float(all_hm_supplot[sp1])
                base_lo = float(all_hm_supplot[sp1+1])

                if (last_price < base_up) and (last_price > base_lo) :
                    
                    b1 = (base_up - base_lo) / 2 
                    b2 = base_up - b1

                    all_hm_supplot.insert(sp1+1, b2)

                    break
            

            print('......Add supplot upper,lower,1st', flush=True)

    except : 
        print('......Heat_map ไม่อยู่ในเงื่อนไข Min_cand <= X <= Min_cand')
        print('......Please adjust range heatmap more than ==> '+str(range_heatmap))


    #endregion

    #region-------------------------------------------------------- Depth Chart  

    if ex == 'bitkub' :
        dep_ex = ex
        dep_sym = 'THB_'+sym
        
    
    elif ex == 'binance' :
        dep_ex = ex
        dep_sym = sym+'USDT'
    

    bid_dep, ask_dep, x_axis_bid, x_axis_ask, y_axis, bid_sum, ask_sum, max_buy, max_sell = SUB_FUCTION.depth_chart(dep_ex, dep_sym)
    
    db_depth = {'000':['Buy','Sell']} # เก็บข้อมูล ไป Firebase
  
    for ix in range(len(bid_dep)):

        if len(db_depth) < 10 : dbn = '00'+str(len(db_depth))
        else : dbn = '0'+str(len(db_depth))

        db_depth[dbn] = [bid_dep[ix], ask_dep[ix]]

 
    db.reference('/'+'Momentum/'+ex+'/depth/'+sym_firebase).set(db_depth)
    
    #endregion

    #region-------------------------------------------------------- symbol setting + Volume + celendar economic , firebase

    #print('...SYMBOL SETTING ANALISE', flush=True)

    symbol_setting = False

    try :  
        
        candles_setting, all_horizontial, horizential_price  = SUB_FUCTION.setting_symbol(ex, sym, candles_pd)

        #region ส่วนนี้เอาไปใช้คำนวณ Auto_trandline

        at_max = max(horizential_price)
        at_min = min(horizential_price)

        #endregion

        symbol_setting = True
        
    except : 
        

        if len(candles_pd) >= no_candles :
            no_cand = no_candles
            
        elif len(candles_pd) < no_candles :
            no_cand = len(candles_pd)

        #สำหรับแสดงกราฟ หลัก
        candles_setting = candles_pd[len(candles_pd)-no_cand : ]
        candles_setting.reset_index(drop=True, inplace=True)

        #region ส่วนนี้เอาไปใช้คำนวณ Auto_trandline

        at_max = max(candles_setting['High'])
        at_min = min(candles_setting['Low'])

        #endregion


    no_cand_except_non = len(candles_setting) 
    
    min_of_cand, max_of_cand = min(candles_setting['Low']), max(candles_setting['High'])

    id_at_last_candles = len(candles_setting) - 1


    #region สำหรับคำนวน Buy sell , บันทึกไป firebase 
    
    #print('......Market Setting', flush=True)


    db_market = {'000':['Date','Buy','Sell','Difvol']} # เก็บข้อมูล ไป Firebase

    if ex == 'bitkub' :
        
        #print('......Receive Market', flush=True)

        sym_log_bs = 'THB_'+sym
        name_log = 'log_'+ex+sym+'.csv'
        
        
        def get_df(start_time, date_end, receive_bs): #กรอบเวลาต่ำสุด / ข้อมูลที่ดึงมา
            
            #กำหนด ขอบเขตล่าง + บน
            range_date = []
            id = 0
            
            while True :
                
                #ขอบเขตเวลาเป็น time stamp
                lo_time = start_time + timedelta(minutes = ( bitkub_tf_make_log * id ) ) 
                up_time = start_time + timedelta(minutes = ( bitkub_tf_make_log * ( id + 1 ) ) ) 
                
                range_date.append((str(lo_time), str(up_time)))
                if lo_time <= date_end < up_time :
                    break
                
                id += 1

            #แปลงข้อมูลเป็น pandas
            receive_bsx = np.flip(receive_bs, axis=0)
            df = pd.DataFrame(receive_bsx, columns=['date', 'price', 'vol', 'market'])
            df['date'] = df['date'].astype(int)
            # แปลง date เป็น datetime
            df['date'] = pd.to_datetime(df['date'], unit='s').dt.tz_localize('UTC').dt.tz_convert('Asia/Bangkok').dt.tz_localize(None)
            df['vol'] = df['vol'].astype(float)
            df['price'] = df['price'].astype(float)
    

            # สร้างคอลัมน์ val ตามเงื่อนไข
            df['val'] = df.apply(lambda row: (row['vol'] * row['price'])/0.9975 if row['market'] == 'buy' else (row['vol']*row['price'])*0.9975, axis=1)

            #จัดรูปแบบใหม่
            df = df[['date', 'price', 'vol', 'val', 'market']]
        
            # คำนวณผลรวม buy/sell ตามช่วง
            result = []
            for start, end in range_date:
                start_dt = pd.to_datetime(start)
                end_dt = pd.to_datetime(end)

                temp = df[(df['date'] >= start_dt) & (df['date'] < end_dt)]

                buy_sum = temp[temp['market']=='BUY']['vol'].sum()
                sell_sum = temp[temp['market']=='SELL']['vol'].sum()
                valbuy_sum = temp[temp['market']=='BUY']['val'].sum()
                valsell_sum = temp[temp['market']=='SELL']['val'].sum()

                result.append([start_dt,buy_sum,sell_sum,valbuy_sum,valsell_sum])
           
            return result

        def update_csv(last_date, day_from_now, data_full):
           
            #ส่วนนี้เป็น ช่วงเวลาที่นาน ที่สุด ใน ทามเฟรม 1D ตามจำนวนแท่งเทียนที่ตั้งเอาใว้ 30 60 90 โดยการเก็บวันที่ล่าสุด
            #มีใว้เพื่อ ไม่ให้ตอนเราเปลี่ยน ทามเฟรมไปมาแล้วข้อมูลหาย
            max_zero = str(last_date).split(' ')
            max_zerox = str(max_zero[0] + ' 00:00:00')
            keep_data_from = datetime.strptime(max_zerox , '%Y-%m-%d %H:%M:%S') - timedelta(days = day_from_now ) #เก็บข้อมูลมากสุด 60 วัน

            data_full  = data_full[data_full['date'] >= keep_data_from]
            
            # รีเซ็ต index ใหม่
            data_full = data_full.reset_index(drop=True)

            data_full.to_csv(name_log, index=False,header=False)


        try : #ลอง เปิด log BUY SELL 
        
            #region ดึงข้อมูลเก่า จาก csv log

            get_old_data = []
            with open(name_log, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    get_old_data.append(row)

            #endregion
          
            #region อัพเดท ใหม่ + เก่า

            #แปล เป็น np กำหนด วันที่เริ่มต้น อัพเดท
            data_old = np.array(get_old_data)
            data_old_start = datetime.strptime(str(data_old[-1][0]), '%Y-%m-%d %H:%M:%S')
            
            #ดึงข้อมูล
            main_run = 1 #ส่วนนี้จะ ตรวจสอบว่าข้อมูลที่ดึงมาล่าสุดครบหรือปล่าว ถ้าไม่ก็เพิ่มจำนวนการดึงมา
            auto_setup = 1 #ตัวคูณที่จะเอาไปคุณขึ้นเรื่อยๆ เมื่อดึงข้อมูลมาไม่พอ
            get_limit = 1000 #จำนวนที่ดึงข้อมูล
            
            while main_run == 1 :

                up_con = 1
                while up_con == 1 : #ดึงข้อมูล / ป้องกันไม่ให้ เน็ตหลุดแล้วเด้งไป except สร้างไฟล์

                    try : 
                        update_bs = bitkub.trades(sym=sym_log_bs, lmt=get_limit)['result']
                        up_con -= 1
                    
                    except : 

                        #print('......waiting error receive market again', flush=True)
                        time.sleep(3)

                    
                #ส่วนนี้ เช็คให้ ข้อมูลที่ดึงมามัน ครอบคลุมกับ ข้อมูลแถวสุดท้าย ใน csv ใหม ถ้าไม่ให้เพิ่ม lmt
                if int(update_bs[-1][0]) < int(datetime.timestamp(data_old_start)) :
                    #แสดงว่าครอบคลุม
                    #print('......Good Market receive', flush=True)
                    main_run -= 1
                
                else :
                    
                    #ให้ระบบ แอดข้อมูลไปเริื่อยๆ จนได้
                    get_limit += (30000 * auto_setup) - get_limit
                    auto_setup += 1
                    print('.........Add market '+str(get_limit), flush=True)

            # หาจุดสุดท้ายของข้อมูลที่ดึงมา 0 คือล่าสุดเพราะข้อมูลกลับด้านตั้งแต่ broker
          
            date_end =  datetime.fromtimestamp(int(update_bs[0][0]))
            
            get_update = get_df(data_old_start, date_end, update_bs)
         
            sum_data = np.vstack((data_old[:-1], get_update))

            data_full = pd.DataFrame(sum_data, columns=["date", "buy", "sell", 'valB', 'valS'])
            data_full["date"] = pd.to_datetime(data_full["date"])  
            data_full['buy'] = data_full['buy'].astype(float)
            data_full['sell'] = data_full['sell'].astype(float)
            data_full['valB'] = data_full['valB'].astype(float)
            data_full['valS'] = data_full['valS'].astype(float)      

            #endregion
    
            update_csv(date_end,bitkub_keep_day_from_now,data_full)
        
        except : #สร้าง ฐานข้อมูล ใหม่
                      

            wait_x = input(' ......Put enter to receive new Market')

            #region ดึงข้อมูลมา แล้ว เขียนไฟล์ .csv
            
            #ดึงมาสร้างวันที่
            receive_bs = bitkub.trades(sym=sym_log_bs, lmt=400000)['result']
            #[1763516477, 0.2193, 9012.227783, 'SELL'] 08:41:17
            if "linux" in this_system: #Raspberry Pi
                date_start = datetime.fromtimestamp(int(receive_bs[-1][0]) / 1000)    #เวลา นานสุดี่ดงมาได้
                date_end = datetime.fromtimestamp(int(receive_bs[0][0]) / 1000)       #ล่าสุด
            elif "windows" in this_system: # สำหรับ Windows (เช่น PC)
                date_start = datetime.fromtimestamp(int(receive_bs[-1][0]))    #เวลา นานสุดี่ดงมาได้
                date_end = datetime.fromtimestamp(int(receive_bs[0][0]))       #ล่าสุด
              
            # หาเวลาเที่ยงคืน ของวันถัดไปเพื่อเริ่ม    /    จะ tf ไหนก็ใช้ เวลานี้เพื่อเริ่ม
            set_date = str(date_start + timedelta(days=1)).split(' ')
            start_time = datetime.strptime(set_date[0] + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
            

            get_new = get_df(start_time, date_end, receive_bs)

            data_full = pd.DataFrame(get_new, columns=["date", "buy", "sell", 'valB', 'valS'])
            data_full["date"] = pd.to_datetime(data_full["date"])
            data_full['buy'] = data_full['buy'].astype(float)
            data_full['sell'] = data_full['sell'].astype(float)
            data_full['valB'] = data_full['valB'].astype(float)
            data_full['valS'] = data_full['valS'].astype(float)


            # เก็บ ไฟล์
            update_csv(date_end,bitkub_keep_day_from_now,data_full)

            #endregion     


        #เอาไว้หาว่า บันทึกตั้งแต่เมื่อไหร่
        #print('......Keep log From '+str(data_full["date"][0]), flush=True)
        #print('......... to '+str(date_end), flush=True)
        
        #region OHLCV + firebase
       
        #update txt ให้ไม่เกินจำนวน แท่งเทียนที่ ที่ตั้งค่าใว้เช่น 30 60 วัน นับจากแท่งล่าสุด/ปัจุบัน
        type_date = '%Y-%m-%d %H:%M:%S'

        if (tf == '1w') or (tf == '1D') :

            set_zerox = list(candles_setting['Time']) # แท่ง W เริ่มนับ 0700-0659
            if tf == '1w' :
                ad_date = 7
            elif tf == '1D' :
                ad_date = 1

            ad_last = datetime.strptime(set_zerox[-1], type_date) + timedelta(days = ad_date)
            set_zerox.append(str(ad_last))

        else : 

            set_zerox = list(candles_setting['Time'])

          
            ad_last = datetime.strptime(set_zerox[-1], type_date) + timedelta(minutes = tf)
            set_zerox.append(str(ad_last))

        #สร้างลิมิตล่าง บน
        limit_candles = [(set_zerox[i], set_zerox[i+1]) for i in range(len(set_zerox)-1)] #สร้าง limit บน ล่าง
        
        #จัดแบ่ง ให้ลงตาม candles + firebaes
        #output = []
        for xid  in range(len(limit_candles)):

            low, high = limit_candles[xid][0], limit_candles[xid][1]
            low_d = pd.to_datetime(low)
            high_d = pd.to_datetime(high)

            # ดึงข้อมูลที่อยู่ในช่วง
            subset = data_full[(data_full["date"] >= low_d) & (data_full["date"] < high_d)]

            # รวมปริมาณ
            total_buy = subset["buy"].sum()   # vol buy
            total_sell = subset["sell"].sum() # vol sell
            total_vb = subset["valB"].sum()   # val buy
            total_vs = subset["valS"].sum()   # val sell

            # หาผลต่าง
            difbs = float(total_buy) - float(total_sell)

            #ถ้าไม่มีทั้ง ซื้อ และ ขาย ให้ใช้ volume เต็มแทน ในช่อง buy
            if difbs == 0.0 :
                total_buy = float(candles_setting['Volume'][xid])

            #หา avg buy sell
            #avg_buy = (float(total_vb) * 1.0025) / float(total_buy) if float(total_buy) != 0 else 0
            #avg_sell = float(total_vs) / (0.9975 * float(total_sell) ) if float(total_sell) != 0 else 0
            
            if len(db_market) < 10 : dbn = '00'+str(len(db_market))
            else : dbn = '0'+str(len(db_market))

            dx = str(low).split(' ')
            dx1 = dx[0].split('-')
            dx2 = dx[1].split(':')

            #ชั่วโมง นาที วันที่ เดือน
            db_time = dx2[0]+dx2[1]+dx1[2]+dx1[1]

            db_market[dbn] = [db_time, total_buy, total_sell, difbs]
        
        # Data Output ปิดไว้เพราะ ไม่ได้ให้แสดงในคอม
        #candlestick = pd.DataFrame(output, columns=["date", "buy", "sell", 'difvol', 'difval'])
        #candlestick["date"] = pd.to_datetime(candlestick["date"])
      
        #endregion
     
    elif ex == 'binance' :   
       
        if len(candles_setting) <= no_candles :
            get_total = len(candles_setting)
        else :
            get_total = no_candles

        use_datax = SUB_FUCTION.Binance_ohlcv_UTC('spot','trades',sym,tf,get_total)

        # OHLCV + firebase
        for ud in range (len(use_datax)) : 

            # บันทึกไป db
            if len(db_market) < 10 : dbn = '00'+str(len(db_market))
            else : dbn = '0'+str(len(db_market))

            #เตรียม ข้อมูลจัดเก็บ firebase
            
            dx = str(datetime.strptime(str(use_datax[ud][0]), '%Y-%m-%d %H:%M:%S')).split(' ')
            dx1 = dx[0].split('-')
            dx2 = dx[1].split(':')

            #ชั่วโมง นาที วันที่ เดือน
            db_time = dx2[0]+dx2[1]+dx1[2]+dx1[1]

            b = float(use_datax[ud][1])
            s = float(use_datax[ud][2])
            d = b - s

            #usdt_buy = float(use_datax[ud][3])
            #usdt_sell = float(use_datax[ud][4])
           

            db_market[dbn] = [db_time, b, s, d]

    db.reference('/'+'Momentum/'+ex+'/market/'+sym_firebase).set(db_market)
    


    #endregion

    #region สร้างเส้น sub plot เฉพาะ net 2 3 

    min_of_cand = candles_setting['Low'].min()
    max_of_cand = candles_setting['High'].max()

    #endregion

    #region สร้างเส้น sub plot เฉพาะ net

    setting_sp_zonex = SUB_FUCTION.find_semi_hm_supplot(all_hm_supplot, min_of_cand, max_of_cand, last_price)

    #endregion

    #region บันทึก low close high ไป firebase

    db_price = {'000':['Low','Close','High']}
    for dbp in range(len(candles_setting)) :

        if len(db_price) < 10 : dbn = '00'+str(len(db_price))
        else : dbn = '0'+str(len(db_price))


        db_price[dbn] = [candles_setting['Low'][dbp], candles_setting['Close'][dbp], candles_setting['High'][dbp]]

    db.reference('/'+'Momentum/'+ex+'/price/'+sym_firebase).set(db_price)
    
    
    #endregion


    #endregion

    #region-------------------------------------------------------- หา Auto trandline & Semi แต่ละอัน
    
    #print('...AUTO TRANDLINE ANALISE', flush=True)

    #region ASR for subplot
    get_auto_trandline =  SUB_FUCTION.auto_trandline('lh', tf, candles_np, auto_tl, [at_min, at_max, no_cand_except_non]) #(limit ล่าง, บน , จำนวน แท่งทั้งหมด ไม่รวม nan)
    loz_supplot = get_auto_trandline[0] #เอาทุกตัว
    
    loz_net = get_auto_trandline[1] #เฉพาะตัวที่ ไม่เกิน horizon

    #หา mid area of auto_trandline supplot
    mid_value_end, rloz_up, rloz_lo, gloz_up, gloz_lo = SUB_FUCTION.mid_area_auto_trandline(loz_supplot)

    # check break up-down ASR
    check_same_y2_up = []
    check_same_y2_down = []

    for cb in range(auto_tl) :
        
        # 0 2 4 5 6...
        c_up = '%.3f'%loz_supplot[ cb * 2][3]
        if ( len(check_same_y2_up) == 0 ) or (c_up in check_same_y2_up) :
            check_same_y2_up.append(c_up)

        # 1 3 5 7 9...
        c_down = '%.3f'%loz_supplot[ (cb * 2) + 1 ][3]
        if ( len(check_same_y2_down) == 0 ) or (c_down in check_same_y2_down) :
            check_same_y2_down.append(c_down)
    
    

    #endregion

    #region semi ASR 1st 2nd for net
    
    #1st จะเก็บ ไปใน analist
    loz_net_1semi = (SUB_FUCTION.auto_trandline('lh', tf, candles_np[-no_cand_except_non:], 1, [at_min, at_max, no_cand_except_non]))[0]
    if len(loz_net_1semi) == 2 : #ถ้ามีเส้นเดียวไม่ต้องหา area
        mid_semi_end, r_semi_up, r_semi_lo, g_semi_up, g_semi_lo = SUB_FUCTION.mid_area_auto_trandline(loz_net_1semi)


    #2nd semi ไม่เก็บ
    loz_net_2semi = (SUB_FUCTION.auto_trandline('oc', tf, candles_np[-no_cand_except_non + predict_semi:], 1, [at_min, at_max, no_cand_except_non]))[0]
    
    #แก้ไข id 2nd เพราะ ไม่ควรแสดงเส้นเริ่มที่จุดเดียวกัน ถ้า predict_semi > 0
    if predict_semi != 0 :
        loz_net_2semi[loz_net_2semi == loz_net_2semi[0][0] ] = loz_net_2semi[0][0] + predict_semi
        loz_net_2semi[loz_net_2semi == loz_net_2semi[0][1] ] = loz_net_2semi[0][1] + predict_semi

    #ALL
    loz_net_semi = np.vstack((loz_net_2semi, loz_net_1semi))
    
    

    #endregion


    #endregion

    #region-------------------------------------------------------- กำหนด ขีดจำกัดที่แสดง volume เป็นได้ 3 แบบ + หาสีของ binance
    
    #ข้อมูลจะอัพเดทที่ต้นฉบับ
    
    #SUB_FUCTION.setting_volume_show(candles_y) #แปลงข้อมูล volume 
    #กำหนด ขีดจำกัดที่แสดง volume เป็นได้ 3 แบบ + หาสีของ binance  
    #ใช้ในกราฟ subplot + setting chart binance
    
    SUB_FUCTION.setting_volume_show(candles_pd) #แปลงข้อมูล volume เป็นได้ 3 แบบ candles_setting
        
    #endregion

    #region-------------------------------------------------------- สร้าง Trandline TF
    
    if ex == 'bitkub' :
        tf_mark = ['1D', 240, 60, 30, 15, 5]

    elif ex == 'binance' :
        tf_mark = ['1d', '4h', '1h', '30m', '15m', '5m']
    
    tf_color = {} #high, low เอาใว้หาสีกรอบ bar
    
    #region สำหรับ แยกเทรน + vol แต่ละ tf

    #add fuction4 fuction ด้านล่างให้เฉพาะ ข้อมูลในชุดนี้เลยไม่เอาไป Subfuction

    def ohlc_to_trand(tf) :

        #region ดึงข้อมูล
        if ex == 'bitkub' :
            candles = SUB_FUCTION.Bitkub_ohlcv_UTC(sym, tf, no_candles)

        elif ex == 'binance' :
            candles = SUB_FUCTION.Binance_ohlcv_UTC('spot','ohlcv',sym, tf, no_candles)
        
        #endregion

        # region แยกข้อมูล
        cand_set = pd.DataFrame(candles)
        cand_set.columns = ['Time','Open','High','Low','Close','Volume']
        cand_set['Volume'] = cand_set['Volume'].astype(float)

        #-----------------------------------------------เก็บ high low ไว้หาสีกรอบ bar
        max_high = max(cand_set['High'])
        min_low = min(cand_set['Low'])
        
        last_high = float(candles[-1][2])
        last_low = float(candles[-1][3])

        if last_high == max_high :
            color = 'green'

        elif last_low == min_low :
            color = 'red'
        
        else :
            color = 'w'

        
        #-----------------------------------------------level_vol กำหนดไว้แค่ 2 ชั้น  0  1

        max_vol = max(cand_set['Volume'])
        min_vol = min(cand_set['Volume'])
        
        set_lv = (max_vol - min_vol) / 3
        lv_0 = min_vol + set_lv
        lv_1 = min_vol + (set_lv*3)

        condition = [cand_set['Volume'] < lv_0 , (cand_set['Volume'] >= lv_0) & (cand_set['Volume'] < lv_1), cand_set['Volume'] >= lv_1]
        lv_get = [0, 1, 2]

        cand_set['level'] = np.select(condition, lv_get, default=0)

        lv_vol = list(cand_set['level'])
        
        #endregion


        #color
        tf_color[tf] = color


        # trandline
        candlesx = (SUB_FUCTION.auto_trandline('lh', tf, candles, 1, []))[0]

        
        return candlesx

    def analise_old_bar(per_sup, per_mid, per_res, rec_log) :#'Update sup,mid,res ถ้าค่าเป็น + = แสดงว่า trand ปัจจุบันกำลังเพิ่มขึ้น - เทรนปัจจุบันกำลังน้อยลง

        def same_compare_to_analise(new_point, old_point, text) :
                
            dif_val = abs(new_point) - abs(old_point)

            if dif_val > 0 : 
                side = 'up '
                
            
            elif dif_val < 0 : 
                side = 'down '
                
                
            #analise = text+' '+side+str('%.2f'%(dif_val))+' %'  ตัวหนังสือสำรับ โชว์
            analise = dif_val

            return analise
            
        def notsame_compare_to_analise(new_point, old_point, text_lo, text_up) :
            
            if ( new_point > 0 ) and ( old_point < 0) :
        
                dif_dif_val = (abs(new_point) + abs(old_point)) * (1)

                #analise = text_up+' '+str('%.2f'%dif_sup_val)+' %'
                analise = dif_dif_val

            
            elif ( new_point < 0 ) and ( old_point > 0) :
                
                dif_dif_val = (abs(new_point) + abs(old_point)) * (-1)

                #analise = text_lo+' '+str('%.2f'%dif_sup_val)+' %'
                analise = dif_dif_val

            

            

            return analise
                

        per_sup_old = float(rec_log['sup'])
        per_mid_old = float(rec_log['mid'])
        per_res_old = float(rec_log['res'])

        #region คำนวณ sup

        if ((per_sup > 0) and (per_sup_old > 0)) or ((per_sup < 0) and (per_sup_old < 0)) :

            dif_sup = same_compare_to_analise(per_sup, per_sup_old, 'Suport move')

        else :
            dif_sup = notsame_compare_to_analise(per_sup, per_sup_old, 'Suport change to red', 'Suport change to green')

        #endregion

        #region คำนวน res

        if ((per_res > 0) and (per_res_old > 0)) or ((per_res < 0) and (per_res_old < 0)) :

            dif_res = same_compare_to_analise(per_res, per_res_old, 'Resistance move')
            
        else :

            dif_res = notsame_compare_to_analise(per_res, per_res_old, 'Resistance change to red', 'Resistance change to green')

        #endregion  
            
        #region คำนวน GAP OVERLAB

        #ดำ ดำ
        if (per_mid > 0) and (per_mid_old > 0) :
            dif_mid = same_compare_to_analise(per_res, per_res_old, 'Gap area move')
            
        # เหลือง เหลือง
        elif (per_mid < 0) and (per_mid_old < 0) :
            dif_mid = same_compare_to_analise(per_mid, per_mid_old, 'Overlab area move')

        #เปลี่ยน zone
        else :
            dif_mid = notsame_compare_to_analise(per_mid, per_mid_old, 'Next to Overlab', 'Next to Gap')

        #endregion
        

        return dif_sup, dif_mid, dif_res
    
    def refresh_log(log_pandas):

        log = open('log_option.txt','w')
        
        log.writelines('all_tf_trandline'+'\n')
        
        
        list_col_name =  list(log_pandas.columns.tolist())

        for i in range(len(list_col_name)) :
            ex_sym_tf = list_col_name[i]
            per_sup = float(log_pandas[ex_sym_tf]['sup'])
            per_mid = float(log_pandas[ex_sym_tf]['mid'])
            per_res = float(log_pandas[ex_sym_tf]['res'])
            log.writelines(ex_sym_tf+'='+str(per_sup)+','+str(per_mid)+','+str(per_res)+'\n') 
        
        log.close()

    def analise_now_bar(per_sup, per_mid, per_res): #Support/Resistance more than 
        
        
        data = []

        #ถ้าเป็น GAP
        if per_mid > 0 :
            
            #green green
            if(per_sup > 0) and (per_res > 0)  :
                al = trand_bar_pattern['gap_up']

            #red red
            elif (per_sup < 0) and (per_res < 0)  :
                al = trand_bar_pattern['gap_down']
            
            #red green red
            else :
                dif_sr = abs(per_sup) - abs(per_res)


                if dif_sr >= 0 : 
                    #หาว่าเป็น ขาขึ้นหรือขอลง
                    if per_sup > 0:
                        al = 'Support more than = '+('%.2f'%abs(dif_sr))+' % to be up'
                    else :
                        al = 'Support more than = '+('%.2f'%abs(dif_sr))+' % to be down'
                
                else :
                    if per_res > 0:
                        al = 'Resistance more than = '+('%.2f'%abs(dif_sr))+' % to be up'
                    else :
                        al = 'Resistance more than = '+('%.2f'%abs(dif_sr))+' % to be down'

            #ดึงข
            per_swing = float(trand_bar_pattern['swing_gap'][0])
            per_swing_text = str(trand_bar_pattern['swing_gap'][1]).split('/')
            
            #ถ้ามี zone gap ที่ตั้งราคาไว้
            if per_mid >= per_swing :

                #เก็บข้อมความ swing gap
                for i in range(len(per_swing_text)) :
                    data.append(per_swing_text[i])
                
                #เก็บข้อมความ SUP RES
                data.append(al)
            
            else :
                #เก็บข้อมความ SUP RES
                data.append(al)

        #ถ้าเป็น LAP
        elif per_mid < 0 :

            if(per_sup > 0) and (per_res > 0)  :
                al = trand_bar_pattern['lap_up']

            elif (per_sup < 0) and (per_res < 0)  :
                al = trand_bar_pattern['lap_down']

            #เก็บข้อมความ SUP RES
            data.append(al)


        return data

    trand_0 = ohlc_to_trand(tf_mark[0])
    trand_1 = ohlc_to_trand(tf_mark[1])
    trand_2 = ohlc_to_trand(tf_mark[2])
    trand_3 = ohlc_to_trand(tf_mark[3])
    trand_4 = ohlc_to_trand(tf_mark[4])
    trand_5 = ohlc_to_trand(tf_mark[5])
    
    only_show_notcal = {'1D':'1D', 240:'4H', 60:'1H', 30:'30m', 15:'15m', 5:'5m',
                        '1d':'1D', '4h':'4H', '1h':'1H', '30m':'30m', '15m':'15m', '5m':'5m' }
        
    #region ดูข้อมูลที่ บันทึกใว้ใน ไฟล์ 
        
    try : #ดึงข้อมูลโดย  keep_datay[Sup][ZIL1d]
        
        #รับการตั้งค่า ถ้ามี

        receive_log = {}
        
        

        with open('log_option.txt','r') as f:
            log_rec = f.readlines()

        for set in log_rec : 

            data = set.split('\n')[0]
            
            try :
                a0 = str(data).split('=')
                content = str(a0[0])

                val = str(a0[1]).split(',')
                val0 = float(val[0])
                val1 = float(val[1])
                val2 = float(val[2])

                # เก็บ list to dice
                receive_log[content] = []
                receive_log[content].append(val0)
                receive_log[content].append(val1)
                receive_log[content].append(val2)

            except :
                pass
        
        #แปลงข้อมูล
        receive_logx = pd.DataFrame(receive_log, index=['sup', 'mid', 'res'])
        #keep_datay.set_index('TF', inplace=True)
        
    except : 
        
        receive_logx = pd.DataFrame(index=['sup', 'mid', 'res'])
            
    #endregion
    
    #region กำหนด ลักษณะ  bar
    a_1st = 5 # fix
    a_use = a_1st #ซ้ายสุด 0 ถึง ซ้ายแกน เปลี่ยน
    b_hi = 1 #บนสุดถึง บนแกน คงที่
    b_lo = 1 #ล่างสุดถึง ล่างแกน คงที่  
    c = 3 #ความกว้าง หน่วย ต้อง <= 1st
    d = 10 #ความสูง หน่วย


    max_ylim = b_hi + b_lo + d
    max_xlim = ((a_use + c) * 0) + a_use

    #ax_show.set_xlim(0, max_xlim)
    #ax_show.set_ylim(0, max_ylim) # มีผลกับล่างสุดถึง ล่างแกน
    #ax_show.set_xticks(np.arange(0, max_xlim, a_1st))
    #ax_show.set_yticks(np.arange(0, max_ylim, 1)) 

    #endregion
    
    input_all_trand = [trand_0, trand_1, trand_2, trand_3, trand_4, trand_5]
    
    #endregion

    #region สร้าง level vol แต่ละ timeframe 
    max_vol = max(candles_setting['Volume'])
    min_vol = min(candles_setting['Volume'])

    dif_vol = (max_vol - min_vol) / 2 #ถ้าเปลียน lv vol ใหเป็นเลข 2 ด้วย

    #endregion


    #endregion

   
    #region-------------------------------------------------------- สร้างกราฟ


    #region------------------------------------------------------------------subplot

    '''
    ax_candles = fig.add_subplot(ax[0:3, 2:4])
    ax_candles.set_xticklabels([])
    ax_candles.set_xticks([])
    ax_candles.yaxis.set_label_position("right")  #เปลี่ยนตำแหน่งแกน
    ax_candles.yaxis.tick_right()                 #เปลี่ยนตำแหน่งแกน

    vol_ax = fig.add_subplot(ax[3, 2:4])
    
    # ปิด vol แล้วไป เพิ่ม ที่ เพิ่มเติม volume แทน
    SUB_FUCTION.candles_with_other(candles_y, ax_candles, ax_vol= vol_ax, itype='candle')

    max_price = max(candles_y['High'])
    min_price = min(candles_y['Low'])
    
    log_line = []
    for ve in range(len(list_fibo)) :

       
        #if ve == 0 :
        #    val_fibo = max_price 
        #else :
        #    val_fibo = log_line[-1] - ( (float(list_fibo[-(ve+1)])/100)  * max_price )

        val_fibo = max_price - ( (float(list_fibo[ve])/100)  * max_price )
        

        ax_candles.plot( [ 0 , len(candles_x)-1], [val_fibo, val_fibo] , color='w' , linewidth = 0.1, alpha= 0.2)

        log_line.append(val_fibo)

    '''

    #region OB order block and data to analise

    data_show = {}
    mid_price_last_ob = 0 #สร้างขึ้นมาเพื่อป้องกัน ไม่ให้ ob เข้าไปอยู่ในกรอบ ASR
    
    for pob in range(len(index_ob)) :
        ind_pob = int(index_ob[pob])
        op = candles_pd['Open'][ind_pob]
        cl = candles_pd['Close'][ind_pob]
        hi = candles_pd['High'][ind_pob]
        lo = candles_pd['Low'][ind_pob]

        #regionหา แถบบน ล่าง block

        if cl >= op :
            x1 = hi - cl
            x2 = op - lo

            if x1 >= x2 :
                up_x = hi
                lo_x = cl
        
            elif x1 < x2 :
                up_x = op
                lo_x = lo

        elif cl < op :
            x1 = hi - op
            x2 = cl - lo

            if x1 >= x2 :
                up_x = hi
                lo_x = op
        
            elif x1 < x2 :
                up_x = cl
                lo_x = lo
    
        #endregion
        
        #region หา สี ของ Block

        if (up_x >= last_price) and  (lo_x >= last_price):
            color_x = 'red'
        
        elif (up_x >= last_price) and  (lo_x <= last_price):
            color_x = 'yellow'
    
        elif (up_x <= last_price) and  (lo_x <= last_price):
            color_x = 'green'
        
        #endregion

        #เก็บ up lo ไว้วิเคราห์ข้อมูล--------------------------------------------------------------------

        #หาว่าจะใส่ค่า สูงสุด หรือน้อยสุด เพื่อให้โดนเส้นที่ใกล้ที่สุด

        if (up_x >= last_price) and  (lo_x >= last_price):

            per = '%.2f'%((lo_x - last_price ) * 100 / last_price)
            dict_ob = 'OB '+str(stop%lo_x)+'/'+str(stop%up_x)+' => '+str(per)

            data_show[dict_ob] = lo_x

        elif (up_x >= last_price) and  (lo_x <= last_price):
            
            #up
            per1 = '%.2f'%((up_x - last_price ) * 100 / last_price)
            dict_ob1 = 'OBU '+str(stop%up_x)+' => '+str(per1)

            #up
            per2 = '%.2f'%((lo_x - last_price ) * 100 / last_price)
            dict_ob2 = 'OBL '+str(stop%lo_x)+' => '+str(per2)

            data_show[dict_ob1] = up_x
            data_show[dict_ob2] = lo_x

        elif (up_x <= last_price) and  (lo_x <= last_price) :

            per = '%.2f'%((up_x - last_price ) * 100 / last_price)
            dict_ob = 'OB '+str(stop%lo_x)+'/'+str(stop%up_x)+' => '+str(per)

            data_show[dict_ob] = up_x

    #endregion

    #region Auto sup_res & red green & max min

    #หา max min ของเส้นแนวรับแนวต้านตัวล่าสุด
    max_min_asr = []

    # plot line of auto tranline
    for loz in range(len(loz_supplot)):

        #เก็บไว้คำนวนหา max min
        max_min_asr.append(float(loz_supplot[loz][3]))


    #หา max min ของเส้นแนวรับแนวต้านตัวล่าสุด
    max_asr = max(max_min_asr)
    min_asr = min(max_min_asr)

    #endregion
    
    
    #endregion

    #region------------------------------------------------------------------bar_trandline
    


    #แสดงผล
    #ถ้าไม่มีไฟล์ ชังชั่นนี้จะเป็น false
    cal_text_analisex = [] #ส่งออก list ตัวหนังสือ แต่ละ tf วิเคราห์เรียบร้อย
    cal_val_analise = [] # ค่าเพื่อนำไป วิเคราห์นอกฟังชั่น

    for at in range(len(input_all_trand)) :
        
        sym_tf = sym+str(tf_mark[at])
        
        data_trandline = input_all_trand[at]

                        
        #region แยก ตัวแปล + cal_val_anlise     'rsOut'(return)

        ry2 = float(data_trandline[0][3])
        ry1 = float(data_trandline[0][2])
        sy2 = float(data_trandline[1][3])
        sy1 = float(data_trandline[1][2])

        cal_val_analise.append('rOut'+str(tf_mark[at]))
        cal_val_analise.append(ry2)
        cal_val_analise.append('sOut'+str(tf_mark[at]))
        cal_val_analise.append(sy2)

        #endregion

        #region หาสีของ bar

        if ry2 >= ry1 : 
            res_color = 'g'
            res_val = 1 # เอาไว้ คูณเพื่อหาเปอร์เซน
        
        else : 
            res_color = 'r'
            res_val = -1

        if sy2 >= sy1 : 
            sup_color = 'g'
            sup_val = 1
            
        else : 
            sup_color = 'r'
            sup_val = -1

        #endregion

        #region สร้าง scale normal เป็น bar

        #สร้าง scale  จาก max min
        max_sr = max(ry2, ry1, sy2, sy1)
        min_sr = min(ry2, ry1, sy2, sy1)

        #หา height ของ bar
        res_bar = abs(SUB_FUCTION.tranfer_scale(d, min_sr, max_sr, ry2) - SUB_FUCTION.tranfer_scale(d, min_sr, max_sr, ry1))
        sup_bar = abs(SUB_FUCTION.tranfer_scale(d, min_sr, max_sr, sy2) - SUB_FUCTION.tranfer_scale(d, min_sr, max_sr, sy1))


        #endregion


        #region หาว่า มี overlab หรือไม่

        lab_r = min(ry2, ry1) 
        lab_s = max(sy2, sy1)

        if lab_r < lab_s :

            #หาแค้ heigh over lab และ ใช้ bottom ของ up_bottom
            heigh_overlab = abs(SUB_FUCTION.tranfer_scale(d, min_sr, max_sr, lab_r) - SUB_FUCTION.tranfer_scale(d, min_sr, max_sr, lab_s))
            
        else :
            heigh_overlab = 0
            
        
        #endregion

        #region แก้ค่า scale พลอต

        #ค่าที่ต้องการให้แสดง บน
        up_1 = res_bar
        up_2 = (b_lo + d) - up_1

        up_left = a_use    
        up_bottom = up_2
        up_width = c            #ไม่ด้ใช้เพราะ ทุกตัวใช้ค่า c เพื่อให้ไม่ งง
        up_height = up_1


        #ค่าที่ต้องการให้แสดง ล่าง
        lo_1 = sup_bar

        lo_left = a_use             #ไม่ด้ใช้เพราะ ค่าเปลี่ยน ตลอดทุกแท่ง
        lo_bottom = b_lo
        lo_width = c            #ไม่ด้ใช้เพราะ ทุกตัวใช้ค่า c เพื่อให้ไม่ งง
        lo_height = lo_1

        #endregion

        #region หา % Area ปัจจุบัน

        dif_area_sr = lo_height + up_height

        #แถบกลางสีดำ
        if dif_area_sr <= d :
            per_res = ((up_height * 100) / d) * res_val  # * คูณเพื่อให้เปลี่ยนเป็นค่า +-
            per_sup = ((lo_height * 100) / d) * sup_val  # * คูณเพื่อให้เปลี่ยนเป็นค่า +-
            per_mid = ((d - dif_area_sr) * 100) / d        # ถาค่าเป็น + แปลว่าไม่มี เหลือง + แปลว่าค่าเป็นสีเหลือง
        
        #แถบกลางสีเหลือง
        else :
            dif_d = dif_area_sr - d    # หาที่เกินมา
            
            per_res = (((up_height - dif_d) * 100) / d) * res_val
            per_sup = (((lo_height - dif_d) * 100) / d) * sup_val
            per_mid = ((d - dif_area_sr) * 100) / d        # ถาค่าเป็น + แปลว่าไม่มี เหลือง + แปลว่าค่าเป็นสีเหลือง

        #endregion


        #region เปรียบเทียบ ปัจจุบัน และ ในไฟล์     Update sup,mid,res'
        
        #หาผลต่างอันใหม่อันเก่า ถ้ามีในไฟล์
        
        cal_text_analisex.append(tf_mark[at])

        #ไม่มีไฟล์
        if len(receive_logx) == 0 :
            
            #ไม่ต้องเขียนไฟล์เพราะจะถูก refresh
            #log.writelines(ex+sym_tf+'='+str(per_sup)+','+str(per_mid)+','+str(per_res)+'\n') 

            #เก็บ ไม่ที dict เพราะ dict จะทำการอัพเดทไฟล์ตอนท้าย
            receive_logx[ex+sym_tf] = [per_sup, per_mid, per_res]
        
        #มีไฟล์
        elif len(receive_logx) > 0 : 
            
            try : #มี SYMBOL

                #ถ้าค่าเป็น + = แสดงว่า trand ปัจจุบันกำลังเพิ่มขึ้น - เทรนปัจจุบันกำลังน้อยลง
                #เป็นการ เปรียบเทียบค่าเก่าและใหม่

                text_analise = analise_old_bar(per_sup, per_mid, per_res, receive_logx[ex+sym_tf])
                text_cont = 'Update sup = '+str('%.2f'%text_analise[0])+'%, mid = '+str('%.2f'%text_analise[1])+'%, res = '+str('%.2f'%text_analise[2])+'%'
                cal_text_analisex.append(text_cont)

                #ลบ colume ที่ดึงมา
                receive_logx = receive_logx.drop(ex+sym_tf, axis=1)
                
                #add ข้อมูลปัจจุบัน
                receive_logx[ex+sym_tf] = [per_sup, per_mid, per_res]

            except : #ไม่มี SYMBOL
                
                #ไม่ต้องเพิ่มไปที่ไฟล์ เพราะจะถูกล้างและอัพเดทตอนสุดท้าย
                #log = open('log_'+ex+'.txt','a')
                #log.writelines(sym_tf+'='+str(per_sup)+','+str(per_mid)+','+str(per_res)+'\n')

                #เก็บ ไม่ที dict เพราะ dict จะทำการอัพเดทไฟล์ตอนท้าย
                receive_logx[ex+sym_tf] = [per_sup, per_mid, per_res]
            
        #endregion

        #region al_text_analise                Res/sup more than Waiting UP < LAP < DOWN' ==> (return)

        #ดึงข้อมูลจาก setting
        analise_from_setting = analise_now_bar(per_sup, per_mid, per_res)

        for va in range(len(analise_from_setting)):
            cal_text_analisex.append(analise_from_setting[va])

        #endregion

        #region plot bar หา maxR minS เพื่อplot ราคา บนล่างสุด bar

        price_1 = stop%(max(ry2, ry1)) # บนสุด
        price_2 = stop%(min(ry2, ry1)) #
        price_3 = stop%(max(sy2, sy1)) #
        price_4 = stop%(min(sy2, sy1)) # ล่างสุด

        #เปลี่ยนแปลง
        x_mark = a_use - 0.10  # x for '➤'
        x_text = (c / 2) + a_use  # x for 4 price 

        y_text_1 = d + b_lo
        y_text_2 = up_bottom - 0.5     #ใช้ 1 แทน
        y_text_3 = b_lo + lo_1 + 0.5   #ใช้ 4 แทน
        y_text_4 = b_lo

        mid_bar = ((y_text_1-y_text_4) / 2 + b_lo)

        color_text = tf_color[tf_mark[at]]

        #ราคาปัจจุบัน เป็น bar scale
        last_price_bar_scale = SUB_FUCTION.tranfer_scale(d, min_sr, max_sr, last_price) + b_lo

        #print('Diff SR = ',(max_sr - min_sr))
        #print(ry2, ry1)
        #print('Res_bar = ',res_bar,' Aup_bar = ', sup_bar)
        #print('Price = ',last_price_bar_scale)

        #endregion


        #หา new a
        a_use += a_1st

    # refresh file .txt receive_logx
    refresh_log(receive_logx)

    cal_val_analisex = np.array(cal_val_analise).reshape(-1,2)

    #endregion
    
    #region------------------------------------------------------------------เพิ่มข้อมูลใน total data analise รวมข้อมูลใว้ใน ob, firebase


    #region OB

    #เป็นตัวแรกที่สร้างขึ้นเก็บไว้ใน supplot ต้องไปเปิดใน ฟังชั่นนั้นดู

    #endregion

    #region HM ค่าที่คำนวนมาจาก heat map / supplot
    for spl in range(len(all_hm_supplot)) :
        val_sp = float(all_hm_supplot[spl])
        dif_val_sp = '%.2f'%((val_sp - last_price) * 100 / last_price)
        dif_val_spx = 'HM '+str(stop%val_sp)+' => '+str(dif_val_sp)

        data_show[dif_val_spx] = val_sp
    #endregion

    #region GD NZ exponentiol + sub of heat map

    try:

        # ค่าที่คำนวนมาจาก net Zone นอนหลัก
        for mpr in range(len(all_horizontial)) :
            val_mp = float(all_horizontial[mpr])
            dif_val_mp = '%.2f'%((val_mp - last_price) * 100 / last_price)
            dif_val_mpx = 'GD '+str(stop%val_mp)+' => '+str(dif_val_mp)

            data_show[dif_val_mpx ] = val_mp

        # ค่าที่คำนวนมาจาก net Zone / เพิ่มเติม suplot
        for nz in range(len(setting_sp_zonex)):

            net_z = float(setting_sp_zonex[nz])

            #สูตรด้านล่างเอาใว้เทียบว่าตัวไหนมีแล้วใน suplot ไม่ต้องเอามารวมใน Net
            try : 
                index = all_hm_supplot.index(net_z)

            except :
                dif_val_nz = '%.2f'%((net_z - last_price) * 100 / last_price)
                dif_val_nzx = 'NZ '+str(stop%net_z)+' => '+str(dif_val_nz)

                data_show[dif_val_nzx] = net_z

    except :
        pass

    #endregion

    #region ASR Auto res/sup

    near_asp = []

    for ao in range(len(loz_supplot)):
        val_ao = float(loz_supplot[ao][3])
        dif_val_ao = '%.2f'%((val_ao - last_price) * 100 / last_price)
        dif_val_aox = 'ASR '+str(stop%val_ao)+' => '+str(dif_val_ao)

        data_show[dif_val_aox] = val_ao

        #เก็บใว้แสดงใน Data Filter
        near_asp.append(val_ao)
    
    near_asp.sort()
    near_res = near_asp[int(len(near_asp)/2)]
    near_sup = near_asp[(int(len(near_asp)/2)) - 1 ]

    
    #endregion

    #region MxASR, MnASR  

    #หาค่า max
    dif_val_max_asr = '%.2f'%((max_asr - last_price) * 100 / last_price)
    dif_val_max_asrx = 'MxASR '+str(stop%max_asr)+' => '+str(dif_val_max_asr)

    data_show[dif_val_max_asrx] = max_asr

    #หาค่า min
    dif_val_min_asr = '%.2f'%((min_asr - last_price) * 100 / last_price)
    dif_val_min_asrx = 'MnASR '+str(stop%min_asr)+' => '+str(dif_val_min_asr)+'%'

    data_show[dif_val_min_asrx] = min_asr


    #endregion

    #region MidSR

    dif_val_max_midsr = '%.2f'%((mid_value_end - last_price) * 100 / last_price)
    dif_val_max_midsrx = 'MidSR '+str(stop%mid_value_end)+' => '+str(dif_val_max_midsr)

    data_show[dif_val_max_midsrx] = mid_value_end

    #endregion

    #region เพิ่ม ราคาล่าสุด
    data_show['Last'] = last_price
    #endregion

    #region trand analise
    
    for va in range(len(cal_val_analisex)) :
        text_va = str(cal_val_analisex[va][0])
        val_va = float(cal_val_analisex[va][1])

        dif_val_va = '%.2f'%((val_va - last_price) * 100 / last_price)
        dif_val_vax = text_va+' '+str(stop%val_va)+' => '+str(dif_val_va)

        if ( va == 0 ) or ( va == len(cal_val_analisex) - 1 ) :
            data_show[dif_val_vax] = val_va
    
    #endregion

    #region ตัวเรียงลำดับข้อมูล limit od data show , firebase
    sort_data = sorted(data_show.items(), key=lambda x:x[1], reverse=True)
    
    colume_total = 11

    if len(sort_data) <= colume_total :
        sort_datax = sort_data
    
    elif len(sort_data) > colume_total :
    

        #คำนวน ไล่ตั้งแต่ last price ไป
        id_lastp = 0
        id_lastp_on = False #ถ้าเจอ ไอดีแล้วไม่ต้องหาอีก

        auto_up = []
        auto_down = []

        for dx in range(len(sort_data)) :
            
            value_etc = float(sort_data[dx][1])
            #ถ้าเจอ ไอดีแล้วไม่ต้องหาอีก

            if ( id_lastp_on == False ) and (value_etc == last_price) :
                id_lastp += dx
                id_lastp_on = True
            
            if value_etc > last_price : auto_up.append(value_etc)
            elif value_etc < last_price : auto_down.append(value_etc)
            

        #find up lo
        corr = (colume_total - 1) / 2
        lo_last_price = int(corr)
        up_last_price = int(corr)

        if (id_lastp >= lo_last_price) and ( len(sort_data) >= (lo_last_price + up_last_price) ) :
        
            sort_datax = sort_data[ ( id_lastp - lo_last_price ) : ( id_lastp + up_last_price + 1 )]
    
        elif id_lastp == 0 : #ถ้าอยู่บนสุด เพราะเรียงจาก มากไปน้อย
            print('...Auto gen Analise Text ', flush=True)
            sort_datax = sort_data[ 0: ( id_lastp + up_last_price + 1 )]
        
        elif id_lastp == (len(sort_data)-1 ) : #ถ้าอยูล่างสุด
            print('...Auto gen Analise Text', flush=True)
            sort_datax = sort_data[ -(lo_last_price+1) :]

        else :
            print('...Auto gen Analise Text', flush=True)
            
            #เอาตัวน้อยสุดเป็นตัวกำหนดขนาด
            number_mark = min(len(auto_up), len(auto_down))

            sort_datax = sort_data[ (id_lastp - number_mark) : (id_lastp * 2) + 1 ]

    #เก็บข้อมูลไป firebase
    db_zone = {'000':['Zone','Price','Move%']}
    
    for sd in range(len(sort_data)) :
        sep_tex = (sort_data[sd][0]).split(' ')

        if len(db_zone) < 10 : dbn = '00'+str(len(db_zone))
        else : dbn = '0'+str(len(db_zone))
        
            
        try : 
            db_list = [sep_tex[0],'%.4f'%sort_data[sd][1],float(sep_tex[3])]
            db_zone[dbn] = db_list

        except : pass
        
    db.reference('/'+'Momentum/'+ex+'/zone/'+sym_firebase).set(db_zone)



    #endregion

       
    #เลื่อนแนวนอน +  แนวตั้ง  MxASR
    list_text = ['OB = Order block UP/LOW',
                'HM,NZ = Heat map scale , sub of heat map',
                'GD,ASR = Grid zone , Auto sup/res at last id',
                'MnASR,MxASR = Min/Max ASR',
                'Min/Max ASR = '+str(stop%min_asr)+'_'+str(stop%max_asr), 
                'MidSR = Mid point ASR > '+str(stop%mid_value_end),
                'Near ASR = '+str(stop%near_sup)+'_'+str(stop%near_res),
                'Near Semi ASR LH = '+str(stop%(float(loz_net_semi[-1][3])))+'_'+str(stop%(float(loz_net_semi[-2][3])))]

    

    #endregion

    #endregion

    #region-------------------------------------------------------- ส่งออก
    #plt.tight_layout()
    #plt.show()

    #เก็บ ARR เปลี่ยนให้รูปแบบเหมือน binance
    if ex == 'bitkub' : 
        tf = tf_bit_to_bin[tf]

        symtf = sym+str(tf)
        use_arr_analise[symtf] = {}

        bit_close = (sum(float(row[4]) for row in candles_np[-last_arr_mark:])) / last_arr_mark
        bit_open = (sum(float(row[1]) for row in candles_np[-last_arr_mark:])) / last_arr_mark
        bin_close_spot = (sum(float(row[4]) for row in binance_ohlcv[-last_arr_mark:])) / last_arr_mark
        bin_open_spot = (sum(float(row[1]) for row in binance_ohlcv[-last_arr_mark:])) / last_arr_mark
        use_arr_analise[symtf]['last_bit_close_rate'] = (bit_close - bit_open) / bit_open
        use_arr_analise[symtf]['last_bin_close_rate'] = (bin_close_spot - bin_open_spot) / bin_open_spot
    
    if ex == 'binance' :
        symtf = sym+str(tf)
        use_arr_analise[symtf] = {}
   
    time.sleep(1)


    #plt.savefig('/storage/emulated/0/MOT_DATA/'+ex+'/'+sym+str(tf)+'/'+ name2, dpi=2000)
        
    #endregion


def get_data_ls(params,url, name):
    
    resp_ratio = requests.get(url, params=params)
    df_ratio = pd.DataFrame(resp_ratio.json())
    df_ratio["timestamp"] = pd.to_datetime(df_ratio["timestamp"], unit="ms", utc=True).dt.tz_convert("Asia/Bangkok").dt.tz_localize(None)
    df_ratio['shortAccount'] = df_ratio['shortAccount'].astype(float)
    df_ratio['longAccount'] = df_ratio['longAccount'].astype(float)
    df_ratio[name] = df_ratio['longAccount'] - df_ratio['shortAccount']

    return df_ratio

def get_long_short_ratio(params):
    
    df_LS_top_position = get_data_ls(params, "https://fapi.binance.com/futures/data/topLongShortPositionRatio",'difTopLSpos')
    df_LS_top_account = get_data_ls(params, "https://fapi.binance.com/futures/data/topLongShortAccountRatio",'difTopLSacc')
    df_LS_glo_account= get_data_ls(params, "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",'difGloLSacc')
  
    df_LS_top_position = df_LS_top_position.merge(df_LS_top_account, on="timestamp", how="left")
    df_LS_top_position = df_LS_top_position.merge(df_LS_glo_account, on="timestamp", how="left")
    
    df_LS_top_position = df_LS_top_position[["timestamp",'difTopLSpos','difTopLSacc','difGloLSacc']]
  
    return df_LS_top_position
    
def main_future(sym, tf, limit):
    
    symbol = str(sym).upper()+"USDT"
    main_params = {"symbol": symbol, "period": tf, "limit": limit}
    
    sym_firebase = (sym.upper())+str(tf)

    #region-------------------------------------------------------- TIME

    try :
        utc_stp = bitkub.servertime()    #Time stamp
        if "linux" in this_system: #Raspberry Pi
            #เฉพาะใน rasberry pi ให้หาร 1000 เพราะใช้ เวอชั่น 3.13.5
            now_datetime = datetime.fromtimestamp(float(utc_stp)/1000).replace(microsecond=0)
        
        elif "windows" in this_system: # สำหรับ Windows (เช่น PC)
            now_datetime = datetime.fromtimestamp(float(utc_stp)).replace(microsecond=0)

    except :

        utc_stp = SUB_FUCTION.servertime()    #Time stamp
        if "linux" in this_system: #Raspberry Pi
            #เฉพาะใน rasberry pi ให้หาร 1000 เพราะใช้ เวอชั่น 3.13.5
            now_datetime = datetime.fromtimestamp(float(utc_stp)/1000).replace(microsecond=0)
        
        elif "windows" in this_system: # สำหรับ Windows (เช่น PC)
            now_datetime = datetime.fromtimestamp(float(utc_stp)/1000).replace(microsecond=0)
    
    last_date.clear()
    last_date.append(now_datetime)

    #endregion

    #ราคา---------------------------------------------
    get_spot = SUB_FUCTION.Binance_ohlcv_UTC('spot', 'ohlcv', sym, tf, limit)
    get_future = SUB_FUCTION.Binance_ohlcv_UTC('future', 'ohlcv', sym, tf, limit)


    spot = pd.DataFrame(get_spot, columns=["timestamp","open","high","low","close","volume"])
    future = pd.DataFrame(get_future, columns=["timestamp","open","high","low","close","volume"])

    spot["timestamp"] = pd.to_datetime(spot["timestamp"], unit="ms")
    future["timestamp"] = pd.to_datetime(future["timestamp"], unit="ms")

    #เปลี่ยนให้เป็น float
    to_float = ["open", "high", "low", "close", "volume"]
    future[to_float] = future[to_float].astype(float)
    spot[to_float] = spot[to_float].astype(float)

    spot_df = spot[["timestamp", "close"]].rename(columns={"close": "close_s"})
    future_df = future[["timestamp", "close"]].rename(columns={"close": "close_f"})

    #vol----------------------------------------------
    get_spot_trades = SUB_FUCTION.Binance_ohlcv_UTC('spot', 'trades', sym, tf, limit)
    get_future_trades = SUB_FUCTION.Binance_ohlcv_UTC('future', 'trades', sym, tf, limit)

    spot_t = pd.DataFrame(get_spot_trades, columns=["timestamp","volb","vols","valb","vals"])
    future_t = pd.DataFrame(get_future_trades, columns=["timestamp","volb","vols","valb","vals"])

    #เปลี่ยนให้เป็น float
    to_float = ["volb","vols","valb","vals"]
    spot_t[to_float] = spot_t[to_float].astype(float)
    future_t[to_float] = future_t[to_float].astype(float)

    #ผลต่าง volume
    spot_t['spot_trades'] = spot_t["volb"] - spot_t["vols"]
    future_t['future_trades'] = future_t["volb"] - future_t["vols"]

    vol_trades = pd.merge(spot_t[["timestamp", 'spot_trades']], future_t[["timestamp", 'future_trades']], on="timestamp")
    vol_trades[['spot_trades', 'future_trades']] = vol_trades[['spot_trades', 'future_trades']].astype(float)
    vol_trades['diff_trades'] = vol_trades['future_trades'] - vol_trades['spot_trades']

    df = pd.merge(spot_df, future_df, on="timestamp")
    
    #ราคา future ต่างจาก spot อยู่ที่
    df["diff"] = df["close_f"] - df["close_s"]
    
    df = pd.merge(df, vol_trades, on="timestamp")
    
    # --- 2) ดึง Open Interest ---
    resp_oi = requests.get("https://fapi.binance.com/futures/data/openInterestHist", params=main_params)
    df_oi = pd.DataFrame(resp_oi.json())
    df_oi["timestamp"] = pd.to_datetime(df_oi["timestamp"], unit="ms", utc=True).dt.tz_convert("Asia/Bangkok").dt.tz_localize(None)
    df_oi["sumOpenInterest"] = df_oi["sumOpenInterest"].astype(float)
    df_oi["sumOpenInterestValue"] = df_oi["sumOpenInterestValue"].astype(float)
    df_oi['CMCCirculatingSupply'] = df_oi['CMCCirculatingSupply'].astype(float)
   
    df = pd.merge(df, df_oi, on="timestamp")

    df["leverage"] = df["sumOpenInterestValue"] / (df["sumOpenInterest"] * df["close_f"])
    
    long_shot_ratio = get_long_short_ratio(main_params)
    
    df = df.merge(long_shot_ratio, on="timestamp")

    #-------------------------------------------------------------------จัด colume

    cols = ['timestamp', 'close_s','close_f','diff','spot_trades','future_trades','diff_trades','sumOpenInterest', 'sumOpenInterestValue', 'CMCCirculatingSupply', 'leverage', 
            'difTopLSpos', 'difTopLSacc', 'difGloLSacc']
    
    df = df[cols]
    
    # ---  แสดงผล ---
    pd.set_option("display.float_format", "{:.6f}".format)
    df = df.rename(columns={'timestamp':'date','sumOpenInterest':'OI.vol',  'sumOpenInterestValue':'OI.val', 'CMCCirculatingSupply':'Supply'})
    df = df.fillna(0)
    
    # ------------------------
    db_future = {'000':['date', 'close_s', 'close_f', 'diff','spot_trades','future_trades','diff_trades','OI.vol','OI.valx', 'Supplyx', 'leverage',
                        'difTopLSpos', 'difTopLSacc', 'difGloLSacc']} # เก็บข้อมูล ไป Firebase
   
    data = df.to_numpy()
    
    for ud in range (len(data)) : 

        # บันทึกไป db
        if len(db_future) < 10 : dbn = '00'+str(len(db_future))
        else : dbn = '0'+str(len(db_future))

        #เตรียม ข้อมูลจัดเก็บ firebase
        
        dx = str(datetime.strptime(str(data[ud][0]), '%Y-%m-%d %H:%M:%S')).split(' ')
        dx1 = dx[0].split('-')
        dx2 = dx[1].split(':')
        #ชั่วโมง นาที วันที่ เดือน
        db_time = dx2[0]+dx2[1]+dx1[2]+dx1[1]

        a = float(data[ud][1])
        b = float(data[ud][2])
        c = float(data[ud][3])
        d = float('%.2f'%data[ud][4])
        e = float('%.2f'%data[ud][5])
        f = float('%.2f'%data[ud][6])
        g = float(data[ud][7])
        h = float(data[ud][8])
        
        # 'Supply' ขยับน้อยเกินฉนั้นจึงต้อง หาว่า วันที่เพิ่มจากเมื่อวานเท่าไหร่
        if ud == 0 :
            i = 0
        else :
            i = float(data[ud][9]) - float(data[ud-1][9])

        j = float(data[ud][10])
        k = float(data[ud][11])
        l = float(data[ud][12])
        m = float(data[ud][13])
        

        db_future[dbn] = [db_time, a,b,c,d,e,f,g,h,i,j,k,l,m]

    db.reference('/Future/'+sym_firebase).set(db_future)


    #--------------------------------------------------
    #เก็บ ARR 
    symtf = sym+str(tf)

    close_s = (sum(float(row[4]) for row in get_spot[-last_arr_mark:])) / last_arr_mark
    use_arr_analise[symtf]['last_spot_close'] = close_s
    use_arr_analise[symtf]['avg_spot_price'] = sum( float(candles[4]) for candles in get_spot[-limit:] ) / limit

    close_f = (sum(float(row[4]) for row in get_future[-last_arr_mark:])) / last_arr_mark
    use_arr_analise[symtf]['last_future_close'] = close_f
   
    get_spot_trades = SUB_FUCTION.Binance_ohlcv_UTC('spot', 'trades', sym, tf, limit)
    use_arr_analise[symtf]['bin_spot_buy'] = sum( float(vol[1]) for vol in get_spot_trades[-last_arr_mark:])
    use_arr_analise[symtf]['bin_spot_sell'] = sum( float(vol[2]) for vol in get_spot_trades[-last_arr_mark:])
    #use_arr_analise[symtf]['bin_spot_vol_diff'] = bin_buy - bin_sell
    #use_arr_analise[symtf]['bin_spot_avg_vol_diff'] = bin_avg

    get_future_trades = SUB_FUCTION.Binance_ohlcv_UTC('future', 'trades', sym, tf, limit)
    use_arr_analise[symtf]['bin_future_buy'] = sum( float(vol[1]) for vol in get_future_trades[-last_arr_mark:])
    use_arr_analise[symtf]['bin_future_sell'] = sum( float(vol[2]) for vol in get_future_trades[-last_arr_mark:])
    
    use_arr_analise[symtf]['last_oi'] = df_oi["sumOpenInterest"][len(df_oi) - 1]
    use_arr_analise[symtf]['prev_oi'] = df_oi["sumOpenInterest"][len(df_oi) - 2]

    use_arr_analise[symtf]['last_leverage'] = df["leverage"][len(df)-1]
    use_arr_analise[symtf]['avg_leverage'] = (df["leverage"].sum()) / len(df)

    use_arr_analise[symtf]['whale_money'] = df["difTopLSpos"][len(df)-1]
    use_arr_analise[symtf]['avg_whale_money'] = (df["difTopLSpos"].sum()) / len(df)
    use_arr_analise[symtf]['whale_acc'] = df["difTopLSacc"][len(df)-1]
    use_arr_analise[symtf]['avg_whale_acc'] = (df["difTopLSacc"].sum()) / len(df)
    use_arr_analise[symtf]['global_acc'] = df["difGloLSacc"][len(df)-1]
    use_arr_analise[symtf]['avg_global_acc'] = (df["difGloLSacc"].sum()) / len(df)


def main_funding(sym,total):
    #ไม่รวมกับ future ตัวนี้ไม่มี TF
    #fundingTime   fundingRate      markPrice

    symbol = str(sym).upper()+"USDT"
    sym_firebase = sym.upper()

    url_funding = "https://fapi.binance.com/fapi/v1/fundingRate"
    
    params_funding = {
        "symbol": symbol,
        "limit" : total
    }
    resp_funding = requests.get(url_funding, params=params_funding).json()
    df_funding = pd.DataFrame(resp_funding)

    df_funding["fundingTime"] = pd.to_datetime(df_funding["fundingTime"], unit="ms").dt.tz_localize("UTC").dt.tz_convert("Asia/Bangkok").dt.tz_localize(None).dt.floor('s')

    df_funding["fundingRate"] = df_funding["fundingRate"].astype(float)
    df_funding = df_funding.drop(columns=["symbol"])

    db_funding = {'000':['date', 'fundingRate', 'markPrice']}

    data = df_funding.to_numpy()

    sum_funding = 0

    for ud in range(len(data)) : 

        # บันทึกไป db
        if len(db_funding) < 10 : dbn = '00'+str(len(db_funding))
        else : dbn = '0'+str(len(db_funding))

        #เตรียม ข้อมูลจัดเก็บ firebase
        
        dx = str(datetime.strptime(str(data[ud][0]), '%Y-%m-%d %H:%M:%S')).split(' ')
        dx1 = dx[0].split('-')
        dx2 = dx[1].split(':')
        #ชั่วโมง นาที วันที่ เดือน
        db_time = dx2[0]+dx2[1]+dx1[2]+dx1[1]

        a = float(data[ud][1])
        b = float(data[ud][2])
      
        #usdt_buy = float(use_datax[ud][3])
        #usdt_sell = float(use_datax[ud][4])

        db_funding[dbn] = [db_time, a,b]

        #---------------------เก็บข้อมูล วิเคราห์ ผล
        sum_funding += a
        if ud == len(data)-1 : 
            use_arr_analise[sym] = {}
            use_arr_analise[sym]['last_funding'] = a

    use_arr_analise[sym]['avg_funding'] = sum_funding / len(data)

    db.reference('/Funding/'+sym_firebase).set(db_funding)


def learning (ex, sym, tf):
    
    symtf = sym+str(tf)
    
    if ex == 'bitkub' :
        symtf = sym+tf_bit_to_bin[tf]
        bitkub_close_rate = use_arr_analise[symtf]['last_bit_close_rate'] #ราคาปิด3แท่งสุดท้าย bitkub เป็นกี่เท่าของ 3open #(close - open) / open 
        binance_close_rate = use_arr_analise[symtf]['last_bin_close_rate'] #ราคาปิด3แท่งสุดท้าย binance เป็นกี่เท่าของ 3open #(close - open) / open 
        
    
    spot_vol_buy = use_arr_analise[symtf]['bin_spot_buy'] #ซื้อ 3แท่งสุดท้าย
    spot_vol_sell = use_arr_analise[symtf]['bin_spot_sell'] #ขาย 3แท่งสุดท้าย
    future_vol_buy = use_arr_analise[symtf]['bin_future_buy'] #ซื้อ 3แท่งสุดท้าย
    future_vol_sell = use_arr_analise[symtf]['bin_future_sell'] #ขาย 3แท่งสุดท้าย

    #นำเข้า แค่ symbol
    funding_rate = use_arr_analise[sym]['last_funding'] #funding rate ล่าสุด
    avg_funding_rate = use_arr_analise[sym]['avg_funding'] #funding rate เฉลี่ย
    
    oi = use_arr_analise[symtf]['last_oi'] #open interest ล่าสุด
    prev_oi = use_arr_analise[symtf]['prev_oi'] #open interest ก่อนหน้า
   
    leverage = use_arr_analise[symtf]['last_leverage'] #การใช้ lerverage ล่าสุด
    avg_leverage = use_arr_analise[symtf]['avg_leverage'] #การใช้ lerverage เฉลี่ย

    whale_money = use_arr_analise[symtf]['whale_money'] #ความแตกต่าง top trader เปิดสัญญา position + เท่ากับ  long > shot
    avg_whale_money = use_arr_analise[symtf]['avg_whale_money'] #เฉลี่ยความแตกต่าง top trader เปิดสัญญา position + เท่ากับ  long > shot
    whale_acc = use_arr_analise[symtf]['whale_acc'] #ความแตกต่าง top trader เปิดสัญญา account + เท่ากับ  long > shot
    avg_whale_acc = use_arr_analise[symtf]['avg_whale_acc'] #เฉลี่ยความแตกต่าง top trader เปิดสัญญา account + เท่ากับ  long > shot
    global_acc = use_arr_analise[symtf]['global_acc'] #ความแตกต่าง global binance เปิดสัญญา account + เท่ากับ  long > shot
    avg_global_acc = use_arr_analise[symtf]['avg_global_acc']  #เฉลี่ยความแตกต่าง global binance เปิดสัญญา account + เท่ากับ  long > shot

    future_price = use_arr_analise[symtf]['last_future_close'] #เฉลี่ยราคาปิด future 3 แท่งสุดท้าย
    spot_price = use_arr_analise[symtf]['last_spot_close']   #เฉลี่ยราคาปิด spot 3 แท่งสุดท้าย

    avg_spot_price = use_arr_analise[symtf]['avg_spot_price']  * w_avg_close #เฉลี่ย ระยะห่าง (close-open) / open 3candles * w_avg_close

    score_buy = 0    # Fake Buy
    score_sell = 0   # Fake Sell
    log = []

    # ---------- 1) Spot Volume vs Price ----------
    if spot_vol_buy > spot_vol_sell and spot_price < avg_spot_price:
        score_buy += 15
       
        log.append("Fake Buy: binance Spot buy เยอะ แต่ราคาไม่ขึ้น")

    if spot_vol_sell > spot_vol_buy and spot_price > avg_spot_price:
        score_sell += 15
        log.append("Fake Sell: binance Spot sell เยอะ แต่ราคาไม่ลง")
    
    # ---------- 1.5) Bitkub vs Binance (Local vs Global) ----------
    if ex == 'bitkub' :

        if abs(bitkub_close_rate - binance_close_rate) > w_limit_rate_close_bit_bin:
           
            if bitkub_close_rate >= binance_close_rate :
                log.append("Fake Buy: Bitkub pump แต่ Binance spot ไม่ขึ้นตาม")
            else : 
                log.append("Fake Sell: Bitkub dump แต่ Binance spot ไม่ลงตาม")
            
            text = "Broker Diff: Bitkub & Binance ราคาต่างเกิน "+str(w_limit_rate_close_bit_bin*100)+"% เกิดความผัดผวน"
            log.append(text)
           

    # ---------- 2) Futures vs Spot (ปรับให้ dominant) ----------
    if future_vol_buy > (spot_vol_buy * w_limit_diff_future_spot_vol) or future_vol_sell > (spot_vol_sell * w_limit_diff_future_spot_vol):
       
        if (future_vol_buy - future_vol_sell) > (spot_vol_buy - spot_vol_sell) * w_limit_diff_future_spot_vol:
            # Dominant buy
            score_buy += 10
            text = "Fake Buy: Futures buy มากกว่า "+str(w_limit_diff_future_spot_vol) +"เท่า ของ vol Spot buy-sell"
            log.append(text)
        
       
        elif (future_vol_sell - future_vol_buy) > (spot_vol_sell - spot_vol_buy) * w_limit_diff_future_spot_vol:
            # Dominant sell
            score_sell += 10
            text = "Fake Sell: Futures sell มากกว่า "+str(w_limit_diff_future_spot_vol) +"เท่า ของ vol Spot sell-buy"
            log.append(text)

    # ---------- 3) Funding + OI ----------
    if funding_rate > avg_funding_rate and oi > prev_oi and spot_price < avg_spot_price :
        score_buy += 10
        text = "Fake Buy: Funding > avg , OI เพิ่มขึ้น , ราคาปิดเฉลี่ย spot < avg"
        log.append(text)

    if funding_rate < avg_funding_rate and oi > prev_oi :
        score_buy += 10
        score_sell += 10
        text = "Fake Sell: Funding < avg , OI เพิ่มขึ้น" 
        log.append(text)

    # ---------- 4) Leverage ----------
    if leverage > avg_leverage:
        score_buy += 5
        score_sell += 5

        log.append("Liqudity: Leverage binance สูง ตลาดพร้อมล้าง liqudity")

    # ---------- 5) Whale Behavior ----------
    if whale_money > avg_whale_money and spot_price < avg_spot_price:
        score_buy += 15
        log.append("Fake Buy: Money Whale > avg , แต่ราคาไม่ขึ้น")

    if whale_money < avg_whale_money and spot_price > avg_spot_price:
        score_sell += 15
        log.append("Fake Sell: Money Whale < avg , แต่ราคาไม่ลง")

     # ---------- 5.1) Whale Account ----------
   
    if whale_acc > avg_whale_acc and spot_price < avg_spot_price:
        score_buy += 5
        log.append("Fake Buy: Top trader account Long > avg")

    if whale_acc < avg_whale_acc and spot_price > avg_spot_price:
        score_sell += 5
        log.append("Fake Sell: Top trader account Short < avg")

    # ---------- 6) Retail Bias ----------
    if global_acc > avg_global_acc and spot_price < avg_spot_price:
        score_buy += 5
        log.append("Fake Buy: Retail Long bias")

    if global_acc < avg_global_acc and spot_price > avg_spot_price:
        score_sell += 5
        log.append("Fake Sell: Retail Short bias")

    # ---------- 7) Futures Premium ----------
    if future_price > spot_price and spot_price < avg_spot_price:
        score_buy += 5
        log.append("Fake Buy: Futures > spot , spot_price < avg")

    if future_price < spot_price and spot_price > avg_spot_price:
        score_sell += 5
        log.append("Fake Sell: Futures < spot , spot_price > avg")
    
    # ---------- Normalize 0–100 ----------
    MAX_SCORE = 60  # กำหนดจาก sum ของทุก condition
    score_buy = float('%.2f'%max(0, min(100, (score_buy / MAX_SCORE) * 100)))
    score_sell = float('%.2f'%max(0, min(100, (score_sell / MAX_SCORE) * 100)))

     # ---------- Mapping trap_score ----------
    def map_trap(score):

        if score <= 25:
            return "Level 1 Real Move แรงจริง"
        elif score <= 45:
            return "Level 2 Medium strength เผ้าระวัง"
        elif score <= 60:
            return "Level 3 Trap Zone เริ่มหลอก"
        elif score <= 80:
            return "Level 4 Fake Buy/Sell แรงหลอก"
        else:
            return "Level 5 Heavy Trap เตรียมล้าง liqudation"

    # ---------- Final Decision ----------
    if score_buy >= 60 and score_buy > score_sell:
        trap_type = "Fake Buy"
        confidence = "High" if score_buy >= 80 else "Medium"
        trap_score = score_buy
        trap_level = map_trap(score_buy)

    elif score_sell >= 60 and score_sell > score_buy:
        trap_type = "Fake Sell"
        confidence = "High" if score_sell >= 80 else "Medium"
        trap_score = score_sell
        trap_level = map_trap(score_sell)

    else:
        trap_type = "Real Move"
        confidence = "Low"
        trap_score = max(score_buy, score_sell)
        trap_level = map_trap(trap_score)
    
    #----------------เก็บข้อมูลไป firebase-------------------
    learning = {'000':["สถานะ", trap_type]}
    learning['001'] = ["ความสำคัญ", confidence]
    learning['002'] = ["คะแนน", trap_score]
    learning['003'] = ["work", trap_level]

    for read in log :

        if len(learning) < 10 : dbn = '00'+str(len(learning))
        else : dbn = '0'+str(len(learning))

        text = read.split(":")
        learning[dbn] = [text[0], text[1]]

    db.reference('/'+'Learning/'+ex+'/'+symtf).set(learning)

#Bitkub_mot('ZIL','1D')
#main_future('ZIL','1d',30)
#main_funding('ZIL',30)
#learning('bitkub', 'ZIL', '1d')

tx = 3
input_sym = ['ZIL', 'BTC']
input_bitkub_tf = ['1w','1D',240,60,30,15]
input_binance_tf = ['1w','1d','4h','1h','30m','15m']
tf_bit_to_bin = { '1w':'1w', '1D':'1d', 240:'4h', 60:'1h',30:'30m', 15:'15m'}

for sym in input_sym :

    main_funding(sym, total_funding)

    for tf in input_bitkub_tf :

        Bitkub_mot(sym, tf)
        time.sleep(tx)

        if tf != '1w' :
            
            main_future(sym, tf_bit_to_bin[tf], no_candles)
            learning('bitkub', sym, tf)
            
            #เก็บเฉพาะ funding
            arr_1, arr_2 = use_arr_analise[sym]['last_funding'], use_arr_analise[sym]['avg_funding']
            use_arr_analise.clear()
            use_arr_analise[sym] = {}
            use_arr_analise[sym]['last_funding'] = arr_1
            use_arr_analise[sym]['avg_funding'] = arr_2

    for tf in input_binance_tf :

        Binance_mot(sym, tf)
        time.sleep(tx)

        if tf != '1w' :

            main_future(sym, tf, no_candles)
            learning('binance', sym, tf)
            
            #เก็บเฉพาะ funding
            arr_1, arr_2 = use_arr_analise[sym]['last_funding'], use_arr_analise[sym]['avg_funding']
            use_arr_analise.clear()
            use_arr_analise[sym] = {}
            use_arr_analise[sym]['last_funding'] = arr_1
            use_arr_analise[sym]['avg_funding'] = arr_2

    

