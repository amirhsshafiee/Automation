import pandas as pd
import pymysql
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
from persiantools.jdatetime import JalaliDateTime



sheet_id = "1qggo4Rs59wxWgo5gGsljKD1lI3MBEJt8BmRRsmAHMvs"
gid = "0"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
vov = pd.read_csv(url)


conn = pymysql.connect(
    host="192.168.168.13",
    port=80,
    user="VendorExcellence",
    password="kW{1EK0M)49A",
    database="adaptation"
)

query = """
SELECT VendorID, City, Tier, VendorType
FROM servicequalitymodeldata;
"""

vendors = pd.read_sql(query, conn)
vendors = vendors.drop_duplicates(subset="VendorID", keep="first")


vov = vov.rename(columns={
    '۱. لطفا وندور آی دی مجموعه خود را وارد کنید.': 'VendorID',
    "۵. از 0 تا 10 چقدر احتمال دارد که اسنپ فود را به یک دوست، آشنا یا همکار معرفی کنید؟" : "NPS",
    "۳. چقدر تمایل دارید ھمکاری خود را با اسنپ فود ادامه دھید؟" : "VRS",
    "۲. میزان رضایت شما از تجربه فعالیت در اسنپ فود در چند ماه گذشته چقدر بوده است؟" : "VSAT",
    "تاریخ شروع" : "Date"
})

vov["Date"] = vov["Date"].apply(
    lambda x: JalaliDateTime.strptime(
        x.split(" - ")[0] + " " + x.split(" - ")[1],
        "%Y/%m/%d %H:%M:%S"
    ).to_gregorian()
)

vov = vov.merge(
    vendors[["VendorID","City", "Tier", "VendorType"]],
    on="VendorID",
    how="left"
)

vov = vov.sort_values("VendorType")

tag_map = {
    "دخل": "Foodpartner",
    "پشتیبانی": "Orderticket",
    "مالی": "Finance",
    "تیکت": "Ticket",
    "اکسپرس": "Express",
    "فروش": "Promotion"
}

rate_cols = [
    col for col in vov.columns
    if "به میزان رضایت خود از" in col
    and "چه امتیازی (از ۱ تا ۵) می‌دید؟" in col
]

rename_dict = {}

for col in rate_cols:
    for key, service in tag_map.items():
        if key in col:
            rename_dict[col] = service
            break

vov = vov.rename(columns=rename_dict)


scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=scope
)
client = gspread.authorize(creds)

sheet_id = "1oOYWqE48pm5HkN9XSgN4pqAWuc2PNQIzxONxkUWdehI"
spreadsheet = client.open_by_key(sheet_id)
sheet = spreadsheet.worksheet("Sheet1")
set_with_dataframe(sheet, vov)



target_cols = [
    "Foodpartner",
    "Finance",
    "Express",
    "Orderticket",
    "Ticket",
    "Promotion",
    "VSAT",
    "NPS",
    "VRS"
]

vov = vov.dropna(subset=["Tier", "VendorType"])

Aggrigation = vov.melt(
    id_vars=["VendorID","City" ,"Tier", "VendorType", "Date"],
    value_vars=target_cols,
    var_name="Service",
    value_name="Score"
)

Aggrigation["Score"] = Aggrigation["Score"].replace({
    "از سرویس تیکت استفاده نکردم": ""
})

sheet = spreadsheet.worksheet("Aggregated")
set_with_dataframe(sheet, Aggrigation)



target_cols = {
    "۱۱. به نظر شما نرم افزار دخل در کدام موارد زیر نیازمند بهبود است؟" : "Foodpartner",
    '۱۴. به نظر شما "عملکرد پشتیبانی سفارش های  اسنپ‌فود " در کدام حوزه قابل بهبود است؟' : "Orderticket",
    "۲۰. مهم ترین چالشی که هنگام استفاده از سرویس تیکتینگ تجربه می کنیدچیست؟" : "Ticket",
    "۲۶. مھمترین دلایل نارضایتی شما در رابطه با ابزارھای ارتقای فروش (مانند کوپن، تخفیف،فود پارتی و...) اسنپفود کدام یک از موارد زیر است؟": "Promotion",
    '۳۲. مھمترین دلایل نارضایتی شما از "سرویس ارسال اکسپرس" کدام یک از موارد زیر بوده است؟' : "Express",
    "۳۵. چه تغییراتی را در شرایط پرداخت و فرآیندهای مالی اسنپ فود موجب افزایش رضایت شما میشود؟ " : "Finance"
}

rows = []

for col, service in target_cols.items():
    if col in vov.columns:
        temp = vov[["VendorID","Tier", "VendorType","Date",col]].copy()
        temp.columns = ["VendorID","Tier", "VendorType", "Date", "Reasons"]
        temp["Service"] = service
        rows.append(temp)

rootcause = pd.concat(rows, ignore_index=True).dropna(subset=["Reasons"])


rootcause["Reasons"] = rootcause["Reasons"].astype(str).str.split(",")
rootcause = rootcause.explode("Reasons")
rootcause["Reasons"] = rootcause["Reasons"].str.strip()
rootcause = rootcause[rootcause["Reasons"].ne("")]

sheet = spreadsheet.worksheet("Rootcauses")
set_with_dataframe(sheet, rootcause)

