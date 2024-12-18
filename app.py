from flask import Flask, render_template, request, redirect, url_for
import schedule
import time
import threading
from datetime import datetime
import sqlite3
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)

SLACK_TOKEN = 'xoxb'  # Replace with your actual bot token
EMAIL_ADDRESS = "@gmail.com"  # Your Gmail address
APP_PASSWORD = "sqk"  # The 16-character App Password
client = WebClient(token=SLACK_TOKEN)

# Hardcoded student data
students = [
    {"name": "Rohit Sharma", "marks": 28, "attendance": True},
    {"name": "Virat Kohli", "marks": 55, "attendance": False},
    {"name": "Jasprit Bumrah", "marks": 82, "attendance": False},
    {"name": "Ravindra Jadeja", "marks": 33, "attendance": True},
    {"name": "KL Rahul", "marks": 57, "attendance": False},
    {"name": "Hardik Pandya", "marks": 29, "attendance": True},
    {"name": "Shubman Gill", "marks": 51, "attendance": True}
]

# Mapping trigger functions to their message formats
TRIGGER_FUNCTIONS = {
    'low_score_alert': "The following students scored below 50:\n{}",
    'high_scorers_present': "The following students scored above 50 and are present:\n{}",
    # Add new trigger functions here as needed in the future
}


def send_slack_alert(user_id, alert_name, students_list, trigger_function):
    try:
        # Get the message template based on the trigger function
        message_template = TRIGGER_FUNCTIONS.get(trigger_function, "Unknown trigger function")
        
        # Format the message
        message = message_template.format("\n".join(students_list))
        
        # Send Slack message
        dm_response = client.conversations_open(users=user_id)
        channel_id = dm_response['channel']['id']
        client.chat_postMessage(channel=channel_id, text=message)
        print(f"Slack message sent: {message}")
    except Exception as e:
        print(f"Error sending Slack message: {e}")

def send_email_alert(email, alert_name, students_list, trigger_function):
    try:
        # Get the message template based on the trigger function
        message_template = TRIGGER_FUNCTIONS.get(trigger_function, "Unknown trigger function")
        
        # Format the message
        message = message_template.format("\n".join(students_list))
        
        # Prepare the email
        msg = MIMEText(message)
        msg['Subject'] = f"Alert: {alert_name}"
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        
        # Send the email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, APP_PASSWORD)  # Use your actual credentials
            server.sendmail(EMAIL_ADDRESS, email, msg.as_string())
            print(f"Email sent to {email}: {message}")
    except Exception as e:
        print(f"Error sending email: {e}")



def trigger_high_scorers_present(user_id, email, alert_name):
    try:
        # Fetch students who scored above 50 and are present
        high_scorers_present = [student["name"] for student in students if student["marks"] > 50 and student["attendance"]]
        if high_scorers_present:
            message = f"Alert: '{alert_name}' - The following students scored above 50 and are present:\n" + "\n".join(high_scorers_present)
            if user_id:
                send_slack_alert(user_id, alert_name, high_scorers_present)
            if email:
                send_email_alert(email, alert_name, high_scorers_present)
        else:
            print("No students met the criteria for this alert.")
    except Exception as e:
        print(f"Error in trigger_high_scorers_present: {e}")

# Trigger alert function
def trigger_alert(user_id, email, alert_name, trigger_function):
    # Fetch students based on the trigger function
    if trigger_function == 'low_score_alert':
        students_list = [student["name"] for student in students if student["marks"] < 50]
    elif trigger_function == 'high_scorers_present':
        students_list = [student["name"] for student in students if student["marks"] > 50 and student["attendance"]]
    else:
        students_list = []

    # Send the alerts
    if user_id:
        send_slack_alert(user_id, alert_name, students_list, trigger_function)
    if email:
        send_email_alert(email, alert_name, students_list, trigger_function)




def schedule_alerts():
    schedule.clear()

    conn = sqlite3.connect('alerts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts")
    alerts = cursor.fetchall()

    for alert in alerts:
        alert_id, frequency, time_str, days, date, user_id, email, recurring, trigger_function = alert
        trigger_functions = trigger_function.split(',')  # Handle multiple trigger functions

        for func in trigger_functions:
            if frequency == 'daily':
                schedule.every().day.at(time_str).do(trigger_alert, user_id=user_id, email=email, alert_name=alert_id, trigger_function=func)
            elif frequency == 'weekly' and days:
                for day in days.split(','):
                    getattr(schedule.every(), day.lower()).at(time_str).do(trigger_alert, user_id=user_id, email=email, alert_name=alert_id, trigger_function=func)
            elif frequency == 'monthly' and date:
                def monthly_check():
                    if datetime.now().strftime('%Y-%m-%d') == date:
                        trigger_alert(user_id=user_id, email=email, alert_name=alert_id, trigger_function=func)
                        if not recurring:
                            return schedule.CancelJob
                schedule.every().day.at(time_str).do(monthly_check)

    conn.close()


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/')
def index():
    conn = sqlite3.connect('alerts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts")
    alerts = cursor.fetchall()
    conn.close()
    return render_template('db.html', alerts=alerts)

@app.route('/schedule', methods=['POST'])
def schedule_message():
    frequency = request.form['frequency']
    time_str = request.form['time']
    user_id = request.form.get('user_id')
    email = request.form.get('email')
    recurring = 'recurring' in request.form
    days = ','.join(request.form.getlist('days')) if 'days' in request.form else None
    date = request.form.get('date')
    trigger_function = ','.join(request.form.getlist('trigger_function'))  # Store selected trigger functions

    conn = sqlite3.connect('alerts.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alerts (frequency, time, days, date, user_id, email, recurring, trigger_function)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (frequency, time_str, days, date, user_id, email, recurring, trigger_function))
    conn.commit()
    conn.close()

    schedule_alerts()  # Schedule the new alert
    return redirect(url_for('index'))



@app.route('/edit_alert/<int:alert_id>', methods=['GET', 'POST'])
def edit_alert(alert_id):
    conn = sqlite3.connect('alerts.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        # Update alert details
        frequency = request.form['frequency']
        time_str = request.form['time']
        user_id = request.form.get('user_id')
        email = request.form.get('email')
        recurring = 'recurring' in request.form
        days = ','.join(request.form.getlist('days')) if 'days' in request.form else None
        date = request.form.get('date')
        trigger_function = ','.join(request.form.getlist('trigger_function'))  # Handle trigger functions

        # Update query uses alert_id to update the correct row
        cursor.execute("""
            UPDATE alerts 
            SET frequency = ?, time = ?, days = ?, date = ?, user_id = ?, email = ?, recurring = ?, trigger_function = ?
            WHERE id = ?
        """, (frequency, time_str, days, date, user_id, email, recurring, trigger_function, alert_id))
        
        conn.commit()
        conn.close()

        # Reschedule alerts to apply changes
        schedule_alerts()
        return redirect(url_for('index'))

    # Fetch all columns for the specific alert
    cursor.execute("""
        SELECT id, frequency, time, days, date, user_id, email, recurring, trigger_function
        FROM alerts
        WHERE id = ?
    """, (alert_id,))
    alert = cursor.fetchone()
    conn.close()

    # Ensure alert is not None before rendering the template
    if not alert:
        return "Error: Alert not found.", 404

    return render_template('edit_alert.html', alert=alert)





@app.route('/delete_alert/<int:alert_id>', methods=['POST'])
def delete_alert(alert_id):
    conn = sqlite3.connect('alerts.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()

    # Reschedule alerts after deletion
    schedule_alerts()
    return redirect(url_for('index'))



if __name__ == "__main__":
    schedule_alerts()  # Load existing alerts
    threading.Thread(target=run_scheduler).start()
    app.run(debug=True)