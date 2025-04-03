from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import COMMASPACE, formatdate
from email import encoders
import smtplib
from fpdf import FPDF
from os.path import basename


# The email function we copy pasted from stackoverflow
def send_mail(send_from, send_to, subject, text, files=None, server="localhost"):
    msg = MIMEMultipart()
    
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    
    msg_content = MIMEText(text)
    msg.attach(msg_content)
    
    for f in files or []:
        with open(f, "rb") as fil:
            part = MIMEApplication(
                fil.read(),
                Name=basename(f)
            )
        # After the file is closed
        part['Content-Disposition'] = 'attachment; filename="%s"' % basename(f)
        msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.sendmail(send_from, send_to, msg.as_string())
    
    smtp.close()

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'IDDE Sensor Health Summary Report', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(5)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, body)
        self.ln()

    def add_note(self, note):
        self.set_font('Arial', 'I', 10)
        self.multi_cell(0, 10, note)
        self.ln(10)
        
def determine_status(row):
    if row['last_updated_status'] == 'NO':
        return f"{row['sensor_type']}: Updated Within 24 Hours 'NO'. Last Updated '{row['last_updated_entry']}'"
    elif 'UNAVAILABLE' in row['sensor_type']:
        return f"{row['sensor_type']}"
    else:
        if row.get('sensor_type') != 'CAM':
            battery = f"Battery '{row.get('battery_status', 'Not Applicable').replace('.0','')}'"
            missing_data = f"Missing Data '{str(row.get('percent_missing', 'Applicable')).replace('.0', '')}%'" if 'percent_missing' in row else ''
            hq_images = ''
        else:
            battery = f"Battery '{row.get('battery_status', 'Not Applicable').replace('.0','')}'"
            missing_data = ''
            hq_images = f"HQ Images '{str(row.get('percent_hq_images', 'nan')).replace('.0', '')}%'. Max Image Size: {row.get('max_image_size')} (kb)" if 'percent_hq_images' in row else ''

        updated_today = f"Updated Within 24 Hours 'Yes'" if row['last_updated_status'] == 'YES' else f"Updated Within 24 Hours 'NO'"
        last_entry = f"Last Updated '{row['last_updated_entry']}', " if row['last_updated_status'] == 'NO' else ""
        return f"{row['sensor_type']}: {battery}, {updated_today}, {last_entry} {missing_data} {hq_images}"
