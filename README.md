# 💰 FinSight AI - Personal Finance Tracker

FinSight AI is a **personal finance tracker** built with [Streamlit](https://streamlit.io/), [Pandas](https://pandas.pydata.org/), and [Plotly](https://plotly.com/).  
It helps you **track spending, manage budgets, and scan receipts using Google Gemini AI**.  

---

## 🚀 Features

- **📊 Dashboard** – View total spending, transaction trends, and category breakdowns with interactive charts.  
- **✏️ Manual Entry** – Add transactions manually with vendor, amount, category, and notes.  
- **📷 Receipt Scanner (AI-powered)** – Upload receipts and automatically extract transaction details using Gemini AI.  
- **🎯 Budget Manager** – Set and track monthly category budgets with warnings for overspending.  
- **🔗 Database Integration** – Stores and retrieves transactions with support for budgets.  

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit  
- **Backend:** Python (custom database module)  
- **AI Integration:** Google Gemini API  
- **Visualization:** Plotly Express  
- **Data Handling:** Pandas  

---

## 📂 Project Structure

finsight-ai/
│── app.py # Main Streamlit app (this file)
│── database.py # Database connection & queries
│── database_config.py # Database credentials & Gemini API key
│── requirements.txt # Python dependencies
│── README.md # Project documentation


---

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/finsight-ai.git
cd finsight-ai
```

2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows
```

3. Install Dependencies
```bash
pip install -r requirements.txt
```

4. Configure Database & API

Create a file named database_config.py in the root directory.
Add the following:

# database_config.py
```bash
# Example database credentials
DB_HOST = "localhost"
DB_USER = "your_user"
DB_PASSWORD = "your_password"
DB_NAME = "finsight"

# Gemini API Key
GEMINI_API_KEY = "your_gemini_api_key"
```

5. Run the App
```bash
streamlit run app.py
```
