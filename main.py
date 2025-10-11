import apis
import logs

SERVICE_CATEGORY = "2c9c486e4f821a19014f82381feb0001"  # This is the category ID for "Sports Reservation". It usually doesn't change.

# Fill in these data
USER_ID = "22110190008"
USER_PASSWORD = "Ayst15057223777/"
CAMPUS_NAME = "江湾校区"
SPORT_NAME = "羽毛球"
SPORT_LOCATION = "江湾体育馆羽毛球场"
DATE = "2025-10-17"
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
