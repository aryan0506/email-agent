import imaplib
import os
from dotenv import load_dotenv
import email
import json
import google.generativeai as genai
from pydantic import BaseModel, ValidationError
from email.mime.text import MIMEText
from email.utils import formatdate
from notification_agent import send_notification


# ==============================
# 🔹 Step 1: Define Pydantic Model
# ==============================
class EmailAnalysis(BaseModel):
    summary: str
    intent: str
    urgency: str
    action_items: list[str]
    category: str
    sentiment: str


# ==============================
# 🔹 Step 2: Load Environment Variables
# ==============================
load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("APP_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ==============================
# 🔹 Step 3: Initialize Gemini API
# ==============================
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


# ============================================================================================================================================
# Function to create a draft in Gmail's Drafts folder using IMAP
# ============================================================================================================================================
def create_draft_imap(mail, sender_email, recipient_email, subject, message_text):
    """
    Create a draft by appending a message to the Gmail Drafts folder using IMAP.
    """
    # Create a MIMEText message with the provided text
    msg = MIMEText(message_text)
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)

    # Convert message to a string in RFC822 format
    raw_message = msg.as_string()

    # Gmail's Drafts folder is typically named "[Gmail]/Drafts"
    folder = "[Gmail]/Drafts"

    # Use the APPEND command to add the message to the drafts folder.
    # The '\\Draft' flag indicates that the message is a draft.
    status, data = mail.append(folder, "\\Draft", None, raw_message.encode("utf-8"))

    if status == "OK":
        print("✅ Draft created successfully via IMAP!")
        send_notification("Draft created successfully!")
    else:
        print("⚠ Error creating draft:", data)
        send_notification("Error creating draft!")


# ==============================
# 🔹 Step 4: Connect to Gmail via IMAP
# ==============================
mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)

try:
    mail.login(EMAIL, PASSWORD)
    print("✅ Login successful!")
    send_notification(" ✅Login successful!")

    # Select the inbox
    mail.select("inbox")
    print("📥 Inbox selected!")
    send_notification("📥 Inbox selected!")

    # Search for unread emails
    status, email_ids = mail.search(None, "UNSEEN")
    email_ids = email_ids[0].split()

    if not email_ids:
        print("📭 No unread emails found.")
        send_notification("📭 No unread emails found.")
    else:
        # Process the 5 most recent unread emails
        for email_id in email_ids[::-1][:5]:
            # Fetch the email
            status, data = mail.fetch(email_id, "(RFC822)")
            print("Fetched data for email_id", email_id, ":", data)  # Debug print

            # Loop through data to find the valid email bytes
            raw_email = None
            for item in data:
                if isinstance(item, tuple) and isinstance(item[1], bytes):
                    raw_email = item[1]
                    break
            if raw_email is None:
                print("⚠ Could not find valid email data for email_id", email_id)
                continue  # Skip to next email

            # Parse the email using the valid raw bytes
            msg = email.message_from_bytes(raw_email)

            # Extract email details
            email_data = {
                "from": msg["From"],
                "subject": msg["Subject"],
                "to": msg.get("To"),  # Using .get() avoids KeyError if missing
                "body": next(
                    (
                        part.get_payload(decode=True).decode()
                        for part in msg.walk()
                        if part.get_content_type() == "text/plain"
                        and part.get_payload(decode=True) is not None
                    ),
                    (
                        msg.get_payload(decode=True).decode()
                        if msg.get_payload(decode=True) is not None
                        else "No content available"
                    ),
                )[
                    :500
                ],  # Limit body to first 500 characters for readability
            }

            # Print extracted email details for each email
            print(json.dumps(email_data, indent=4))
            send_notification(
                f"Processing email from: {email_data['from']} | Subject: {email_data['subject']}"
            )

            # ==============================
            # 🔹 Step 5: Analyze Email using Gemini
            # ==============================
            prompt = f"""
            You are an AI email assistant. Your task is to analyze the following email and extract key information.

            ### Email Details:
            {json.dumps(email_data, indent=4)}

            ### Instructions:
            1. **Summarize** the email in a few sentences.
            2. **Identify the sender's intent** (e.g., inquiry, request, alert, spam, personal, business, etc.).
            3. **Detect urgency** (Urgent, Important, Normal, Low Priority).
            4. **Extract key action items** (if any).
            5. **Categorize** the email into one of these categories: 
               - Work-related
               - Personal
               - Promotional/Marketing
               - Spam
               - Financial
               - Subscription/Newsletter
            6. **Sentiment Analysis**: Identify if the email is Positive, Neutral, or Negative.

            ### Output Format (JSON):
            Provide the response strictly in JSON format:
            ```json
            {{
              "summary": "Brief summary of the email.",
              "intent": "Identified intent of the email.",
              "urgency": "Urgent / Important / Normal / Low Priority",
              "action_items": ["Task 1", "Task 2", "..."],
              "category": "Work-related / Personal / Promotional / Spam / Financial / Newsletter",
              "sentiment": "Positive / Neutral / Negative"
            }}
            ```
            """
            result = model.generate_content(prompt)
            llm_response = result.text.strip()
            print("🤖 Gemini Analysis:", llm_response)

            # ==============================
            # 🔹 Step 6: Validate and Parse JSON using Pydantic
            # ==============================
            try:
                cleaned_response = llm_response.strip("```json").strip("```").strip()
                email_analysis = EmailAnalysis.model_validate_json(cleaned_response)
                print("✅ Valid Response:", email_analysis.dict())

                # ==============================
                # 🔹 Step 7: Generate Actions based on Email Analysis
                # ==============================
                action_prompt = f"""
                You are an AI assistant. Based on the following email analysis, generate the best next actions:

                ### Email Analysis:
                {email_analysis.model_dump_json(indent=4)}

                ### Instructions:
                1. Generate clear next actions the user should take based on intent, urgency, and category.
                2. Ensure the actions are **practical and executable**.
                3. If no action is required, return: `"No action required"`.

                ### Output Format (JSON):
                Provide the response strictly in JSON format:
                ```json
                {{
                  "next_actions": ["Action 1", "Action 2", "..."]
                }}
                ```
                """
                action_result = model.generate_content(action_prompt)
                action_response = action_result.text.strip()

                try:
                    action_data = json.loads(action_response)
                    print("🔹 **Suggested Actions:**")
                    for idx, action in enumerate(action_data["next_actions"], 1):
                        print(f"{idx}. {action}")
                except json.JSONDecodeError:
                    print(
                        "⚠ Error: Gemini returned an invalid response. Debugging required."
                    )
                    print(action_response)
            except ValidationError as e:
                print("❌ Validation Error:", e)

            # ==============================
            # 🔹 Step 8: Based on Urgency, Create Draft or Mark as Read
            # ==============================
            if email_analysis.urgency.lower() == "urgent":
                print(
                    "🚨 Urgent email detected! Generating personalized draft reply using LLM..."
                )
                draft_prompt = f"""
                You are Aryan Dwivedi, a professional and personable individual.
                Compose a personalized email draft reply in a warm and friendly tone.
                Your reply should include:
                - A greeting addressing the sender.
                - A brief reference to the email's content summarized as: "{email_analysis.summary}".
                - A polite note indicating that you will respond soon.
                - A courteous sign-off using your name "Aryan Dwivedi".

                Email Details:
                From: {email_data['from']}
                Subject: {email_data['subject']}

                Draft reply in plain text:
                """
                draft_result = model.generate_content(draft_prompt)
                draft_body = draft_result.text.strip()
                print("Draft generated by LLM:")
                print(draft_body)
                create_draft_imap(
                    mail,
                    EMAIL,
                    email_data["from"],
                    "Re: " + email_data["subject"],
                    draft_body,
                )
            elif email_analysis.urgency.lower() == "normal":
                print("✅ Neutral email detected. Marking as read.")
                mail.store(email_id, "+FLAGS", "\\Seen")
                send_notification(f"Email from {email_data['from']} marked as read.")

except imaplib.IMAP4.error:
    print("❌ Login failed! Check your credentials.")
    send_notification("❌ Login failed! Check your credentials.")
finally:
    mail.logout()
    print("📤 Logged out.")
    send_notification("📤 Logged out.")
