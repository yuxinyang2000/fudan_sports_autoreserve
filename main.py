import apis
import logs
import sys
import datetime

SERVICE_CATEGORY = "2c9c486e4f821a19014f82381feb0001"  # This is the category ID for "Sports Reservation". It usually doesn't change.

# Fill in these data
USER_ID = "22110190008"
USER_PASSWORD = "Ayst15057223777/"
CAMPUS_NAME = "江湾校区"
SPORT_NAME = "羽毛球"
SPORT_LOCATION = "江湾体育馆羽毛球场"

# --- 智能检测未来三天内的周五 ---
# 预约平台开放的天数窗口，你可以根据实际情况修改这个数字
BOOKING_WINDOW = 3

today = datetime.date.today()
target_date_found = None

# 从今天开始，循环检查未来几天的日期
for i in range(BOOKING_WINDOW + 1):
    potential_date = today + datetime.timedelta(days=i)
    
    # 检查这一天是不是周五 (周一=0, 周二=1, ..., 周五=4)
    if potential_date.weekday() == 4:
        target_date_found = potential_date
        # 找到了第一个符合条件的周五，就把它定为目标，并停止搜索
        break

# 判断是否找到了可以预约的周五
if target_date_found:
    # 如果找到了，就设置 DATE 变量，并打印日志
    DATE = target_date_found.strftime("%Y-%m-%d")
    print(f"[VITAL]\t\t🎯 Found a Friday in booking window. Target: {DATE}")
else:
    # 如果没找到，说明还没到预约时间，打印日志并退出脚本
    print(f"[INFO]\t\tNo Friday found within the next {BOOKING_WINDOW} days. Nothing to do today.")
    sys.exit()
# --- 智能检测代码结束 ---

TIME = "16:00"

# Optional data
EMAILS = ["22110190008@m.fudan.edu.cn"]  # Receive error notifications by email
YOUR_EMAIL = "yanyanchen235@gmail.com"  # Account to send email from
EMAIL_PASSWORD = "Ayst110449/"  # Password for the email account


if __name__ == '__main__':
    try:
        logged_in_session = apis.login(USER_ID, USER_PASSWORD)
        campus_id, sport_id = apis.load_sports_and_campus_id(logged_in_session, SERVICE_CATEGORY, CAMPUS_NAME, SPORT_NAME)
        service_id = apis.get_service_id(logged_in_session, SERVICE_CATEGORY, campus_id, sport_id, SPORT_LOCATION)
        apis.reserve(logged_in_session, service_id, SERVICE_CATEGORY, DATE, TIME)
    except Exception as e:
        if EMAILS:
            import smtplib
            import datetime
            message = f"Subject: Failed to reserve sport field\n\n{logs.FULL_LOG}"
            connection = smtplib.SMTP("smtp-mail.outlook.com", 587)
            try:
                connection.ehlo()
                connection.starttls()
                connection.login(YOUR_EMAIL, EMAIL_PASSWORD)
                connection.sendmail(YOUR_EMAIL, EMAILS, message)
            finally:
                connection.quit()
