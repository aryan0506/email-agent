# AI Email Agent 📧🤖  

This AI-powered email agent automates email management by reading unread emails, determining urgency, drafting replies, and sending notifications for every action.  

## 🚀 Features  
✅ Reads unread emails  
✅ Classifies emails as **Urgent** or **Neutral**  
✅ Drafts replies for urgent emails  
✅ Marks neutral emails as read  
✅ Sends notifications to a secure message box  

## 🔧 Tech Stack  
- **Backend**: Python (FastAPI)  
- **AI Model**: Google Gemini LLM  
- **Libraries**: `requests`, `Pydantic AI`, `imaplib`, `smtplib`  
- **Security**: Custom notification app instead of Telegram  

## 🛠️ Setup  
1. Clone the repository:  
   ```bash
   git clone https://github.com/your-repo/email-agent.git
   cd email-agent
   ```  
2. Install dependencies:  
   ```bash
   pip install -r requirements.txt
   ```  
3. Configure your **email credentials** in `.env`.  
4. Run the agent:  
   ```bash
   python main.py
   ```  

## 📬 How It Works  
1. The agent **logs into your email** and fetches unread messages.  
2. It **analyzes email content** using an AI model.  
3. If urgent, it **generates a draft reply** and notifies you.  
4. If neutral, it **marks the email as read**.  
