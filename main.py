import json
import os
import pytz
from datetime import datetime
import traceback

from utils import send_mail
from get_raw_data import get_raw_data
from get_reports import get_reports

def send_error_report(subject, text, send_from, send_to, server):
    send_mail(send_from, send_to, subject, text, files=None, server=server)

CONFIG = json.loads(open('config.json', 'r').read())
send_from = CONFIG.get('MAIL_FROM')
send_to = CONFIG.get('MAIL_TO')
server = CONFIG.get('MAIL_SERVER')

try:
    get_raw_data()
except Exception as e:
    subject = 'ERROR: IDDE Health Report'
    text = f'There was an error in get_raw_data function.\n\n{traceback.format_exc()}'
    send_error_report(subject, text, send_from, send_to, server)
    raise

try:
    get_reports()
except Exception as e:
    subject = 'ERROR: IDDE Health Report'
    text = f'There was an error in get_reports function.\n\n{traceback.format_exc()}'
    send_error_report(subject, text, send_from, send_to, server)
    raise

# Only run when no errors for both functions
subject = 'IDDE Health Report'
text = 'See attachments'
pst = pytz.timezone('US/Pacific')
today = datetime.now(pst)
todayyear = today.year
todaymonth = today.month
todaydate = today.day
files = [x for x in os.listdir(os.path.join(os.getcwd(), "reports")) if f"{todayyear}-{todaymonth}-{todaydate}.pdf" in x]
file_paths = [os.path.join(os.getcwd(), "reports", x) for x in files]

send_mail(send_from, send_to, subject, text, files=file_paths, server=server)
