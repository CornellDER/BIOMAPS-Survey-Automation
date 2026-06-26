from datetime import datetime, timedelta
import os
import requests
import json

from utilities.qualtrics_utils import get_response_count

QUALTRICS_BASE_URL = os.environ['QUALTRICS_BASE_URL']
EMAIL_REQUEST_URL = os.environ['EMAIL_REQUEST_URL']
QUALTRICS_API_TOKEN = os.environ['QUALTRICS_API_TOKEN']

def send_email(class_id, reponse_data_values, email_template):
    """
    This function calls build_email to actually send an email.
    """
    # Obtain email contents
    email_address, email_subject, email_body = build_email(class_id = class_id, reponse_data_values = reponse_data_values, email_template = email_template)

    # Build the JSON payload
    payload = {
        "emailAddress": email_address,
        "emailSubject": email_subject,
        "emailBody": email_body
    }

    # Build HTTP headers
    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": QUALTRICS_API_TOKEN
    }

    try:
        response = requests.post(EMAIL_REQUEST_URL, json=payload, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors
        print(f"Success! Status code: {response.status_code}")
        print("Response body:", response.text)
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        print("Response body:", response.text)
    except Exception as e:
        print(f"Error occurred: {e}")

def build_email(class_id, reponse_data_values, email_template):
    """
    This function generates the email for survey reminders.
    It does this by first getting the variables needed for the email's text.
    It then retrieves the email text and fills in the necessary variables with f strings.
    Finally, it returns the email address, email subject, and email body.
    """

    # Define email address
    email_address = reponse_data_values.get("QID4_TEXT")

    # Obtain necessary value for email subject
    survey_type = reponse_data_values.get("Survey Type")
    
    # Define email subject
    if email_template == "reminder":
        email_subject = f'Reminder for the {survey_type} Survey ({class_id})'
    elif email_template == "report_sent":
        email_subject = f'{survey_type} Results ({class_id})'
    else: # in case some error occurs
        email_subject = f'{survey_type} Update ({class_id})'
    
    # Define common variables for email
    email_vars = {
        "email_address": email_address,
        "first_name": reponse_data_values.get("QID2_TEXT"),
        "last_name": reponse_data_values.get("QID3_TEXT"),
        "survey_type": survey_type,
        "course_identifier": class_id,
        "course_name": reponse_data_values.get("QID37_TEXT"),
        "course_number": reponse_data_values.get("QID38_TEXT"),
        "change_url": "https://cornell.ca1.qualtrics.com/jfe/form/SV_3TTUJMbWVDZ2aKG",
        "survey_admin": "BIOMAPS",
        "dashboard_url": f'https://biomapsdashboard.streamlit.app/?class_id={class_id}&assessment={survey_type}',
        "close_date": reponse_data_values.get("Survey Close Date"),
        "survey_url": QUALTRICS_BASE_URL + "/jfe/form/" + reponse_data_values.get("Survey ID"),
        "response_count": get_response_count(reponse_data_values.get("Survey ID"))
    }
    
    # Read the template
    with open(f"utilities/{email_template}.txt", "r") as file:
        template_content = file.read()

    # Fill in the variables
    email_text = template_content.format(**email_vars)

    # Update linebreaks to work with Qualtrics
    email_text = email_text.replace("\n", "<br>")

    return email_address, email_subject, email_text