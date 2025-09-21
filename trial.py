import streamlit as st
import pandas as pd
import plotly.express as px
import tempfile
import os
import json
import sys
import io
from datetime import datetime, date

# PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import database
try:
    from database import get_database
except ImportError as e:
    st.error(f"Could not import database module: {e}")
    st.stop()

# Try to get Gemini API key
try:
    from database_config import GEMINI_API_KEY
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except:
    GEMINI_API_KEY = None
    GEMINI_AVAILABLE = False
    st.sidebar.warning("Gemini AI not configured - Receipt scanning and AI tax mapping disabled")

# Configure page
st.set_page_config(page_title="FinSight AI", page_icon="💰", layout="wide")

CATEGORIES = ['Food', 'Transportation', 'Entertainment', 'Utilities', 'Shopping', 'Healthcare', 'Other']

def init_gemini():
    """Initialize Gemini AI"""
    if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel('gemini-2.0-flash-exp')
    except Exception as e:
        st.error(f"Gemini initialization error: {e}")
        return None

# -------------------------
# Receipt Data Extraction
# -------------------------
def extract_receipt_data(image_path):
    """Extract data from receipt"""
    model = init_gemini()
    if not model:
        return None
    try:
        uploaded_file = genai.upload_file(image_path)
        prompt = """
        Extract from this receipt and return ONLY valid JSON:
        {
            "vendor": "store name",
            "date": "YYYY-MM-DD", 
            "total_amount": 0.00,
            "category": "Food",
            "items": [{"name": "item", "price": 0.00}]
        }
        Categories: Food, Transportation, Entertainment, Utilities, Shopping, Healthcare, Other
        """
        response = model.generate_content([uploaded_file, prompt])
        json_text = response.text.strip()
        if json_text.startswith("```json"):
            json_text = json_text[7:-3]
        elif json_text.startswith("```"):
            json_text = json_text[3:-3]
        return json.loads(json_text)
    except Exception as e:
        st.error(f"Error processing receipt: {e}")
        return None

# -------------------------
# Tax Return Generator
# -------------------------
def map_transactions_to_itr_schema(transactions, schema):
    """Basic mapper: maps transactions to ITR JSON fields"""
    itr_data = schema.copy()
    total_salary = sum(float(t['amount']) for t in transactions if t['category'] == "Other")
    healthcare_exp = sum(float(t['amount']) for t in transactions if t['category'] == "Healthcare")

    if "IncomeDetails" in itr_data:
        itr_data["IncomeDetails"]["Salary"] = total_salary
    if "Deduction" in itr_data:
        itr_data["Deduction"]["80D"] = healthcare_exp

    return itr_data

def ai_map_transactions(transactions, schema):
    """Use Gemini to auto-classify transactions into schema"""
    model = init_gemini()
    if not model:
        return None
    try:
        prompt = f"""
        Map these transactions into the given ITR schema fields.
        Transactions: {json.dumps(transactions, indent=2)}
        Schema: {json.dumps(schema, indent=2)}
        Return ONLY valid JSON, filled with mapped values.
        """
        response = model.generate_content([prompt])
        json_text = response.text.strip()
        if json_text.startswith("```json"):
            json_text = json_text[7:-3]
        elif json_text.startswith("```"):
            json_text = json_text[3:-3]
        return json.loads(json_text)
    except Exception as e:
        st.error(f"AI tax mapping error: {e}")
        return None

# -------------------------
# PDF Filler - ITR-like layout
# -------------------------
def fill_itr_pdf_layout(filled_itr: dict):
    """
    Generate a structured ITR-like PDF from JSON data.
    Returns bytes for download.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 50
    line_height = 18
    y = height - margin

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, "Income Tax Return - ITR1 (Demo)")
    y -= 30

    # Personal Info
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Personal Information")
    y -= 20
    c.setFont("Helvetica", 10)
    pi = filled_itr.get("PersonalInformation", {})
    c.drawString(margin, y, f"Name: {pi.get('Name', 'John Doe')}")
    y -= line_height
    c.drawString(margin, y, f"PAN: {pi.get('PAN', 'ABCDE1234F')}")
    y -= line_height
    c.drawString(margin, y, f"Date of Birth: {pi.get('DateOfBirth', '1990-01-01')}")
    y -= line_height
    c.drawString(margin, y, f"Address: {pi.get('Address', '123, Sample Street, City')}")
    y -= 30

    # Income
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Income Details")
    y -= 20
    income = filled_itr.get("IncomeDetails", {})
    data = [
        ["Source", "Amount (₹)"],
        ["Salary", income.get("Salary", 0.0)],
        ["Other Income", income.get("OtherIncome", 0.0)]
    ]
    table = Table(data, colWidths=[200, 150])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN',(1,1),(-1,-1),'RIGHT'),
        ('FONT',(0,0),(-1,0),'Helvetica-Bold')
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, margin, y - (len(data)*line_height))
    y -= (len(data)+1)*line_height + 20

    # Deductions
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Deductions")
    y -= 20
    ded = filled_itr.get("Deduction", {})
    data = [
        ["Section", "Amount (₹)"],
        ["80C", ded.get("80C", 0.0)],
        ["80D", ded.get("80D", 0.0)],
        ["Other", ded.get("Other", 0.0)]
    ]
    table = Table(data, colWidths=[200, 150])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN',(1,1),(-1,-1),'RIGHT'),
        ('FONT',(0,0),(-1,0),'Helvetica-Bold')
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, margin, y - (len(data)*line_height))
    y -= (len(data)+1)*line_height + 20

    # Summary
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Summary")
    y -= 20
    total_income = sum(float(income.get(k,0.0)) for k in income)
    total_deduction = sum(float(ded.get(k,0.0)) for k in ded)
    taxable_income = max(total_income - total_deduction, 0.0)
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, f"Total Income: ₹{total_income:.2f}")
    y -= line_height
    c.drawString(margin, y, f"Total Deductions: ₹{total_deduction:.2f}")
    y -= line_height
    c.drawString(margin, y, f"Taxable Income: ₹{taxable_income:.2f}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

# -------------------------
# Tax Generator UI
# -------------------------
def show_tax_generator():
    st.header("🧾 Tax Return Generator")

    db = get_database()
    transactions = db.get_transactions(limit=None)

    if not transactions:
        st.info("💡 No transactions available to generate return.")
        return

    schema_path = os.path.join(current_dir, "schemas", "ITR1_schema.json")
    if not os.path.exists(schema_path):
        st.error("⚠️ ITR1 schema not found. Place it in /schemas/ITR1_schema.json")
        return

    with open(schema_path, "r") as f:
        schema = json.load(f)

    use_ai = st.checkbox("🤖 Use Gemini AI for auto-classification", value=False)

    if use_ai and GEMINI_AVAILABLE:
        filled_itr = ai_map_transactions(transactions, schema)
        if not filled_itr:
            st.warning("AI mapping failed. Falling back to manual mapper.")
            filled_itr = map_transactions_to_itr_schema(transactions, schema)
    else:
        filled_itr = map_transactions_to_itr_schema(transactions, schema)

    # Download JSON
    json_bytes = json.dumps(filled_itr, indent=2).encode("utf-8")
    st.download_button(
        label="💾 Download ITR JSON",
        data=json_bytes,
        file_name="ITR1_filled.json",
        mime="application/json"
    )

    # Download PDF
    pdf_bytes = fill_itr_pdf_layout(filled_itr)
    st.download_button(
        label="📄 Download ITR PDF (ITR Layout Demo)",
        data=pdf_bytes,
        file_name="ITR1_filled.pdf",
        mime="application/pdf"
    )

    st.info("⚠️ Upload JSON to the [Income Tax e-Filing portal](https://www.incometax.gov.in/) OR use PDF for printing/reference.")

def show_dashboard():
    st.header("📊 Dashboard")
    db = get_database()
    transactions = db.get_transactions(limit=50)
    if not transactions:
        st.info("💡 No transactions yet. Add one manually or via receipt scanner!")
        if st.button("🎲 Add Sample Data", type="secondary"):
            sample_transactions = [
                ("Starbucks", 12.50, "Food", date.today(), "Coffee and pastry"),
                ("Uber", 23.75, "Transportation", date.today(), "Ride downtown"),
                ("Amazon", 45.99, "Shopping", date.today(), "Books"),
                ("Netflix", 15.99, "Entertainment", date.today(), "Subscription"),
            ]
            for vendor, amount, category, trans_date, desc in sample_transactions:
                db.insert_transaction(vendor, amount, category, trans_date, desc, "sample_data")
            st.success("Sample data added!")
            st.rerun()
        return

    df = pd.DataFrame(transactions)
    df['amount'] = df['amount'].astype(float)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Total Spent", f"₹{df['amount'].sum():.2f}")
    col2.metric("📈 Avg Transaction", f"₹{df['amount'].mean():.2f}")
    col3.metric("🧾 Transactions", len(df))
    col4.metric("🏷️ Categories", df['category'].nunique())

    col1, col2 = st.columns(2)
    with col1:
        category_data = df.groupby('category')['amount'].sum().reset_index()
        if not category_data.empty:
            st.plotly_chart(px.pie(category_data, values='amount', names='category', title='💸 Spending by Category'), use_container_width=True)
    with col2:
        budget_summary = db.get_budget_summary()
        if budget_summary:
            budget_df = pd.DataFrame(budget_summary)
            st.plotly_chart(px.bar(budget_df, x='category', y=['monthly_limit', 'spent'], title='🎯 Budget vs Spending', barmode='group'), use_container_width=True)
        else:
            st.info("💡 Set budgets in Budget Manager to see comparison.")

    st.subheader("📋 Recent Transactions")
    display_df = df[['vendor', 'amount', 'category', 'transaction_date', 'source_type']].copy()
    display_df['amount'] = display_df['amount'].apply(lambda x: f"₹{x:.2f}")
    st.dataframe(display_df.head(10), use_container_width=True)

def show_manual_entry():
    st.header("✏️ Manual Entry")
    db = get_database()
    col1, col2 = st.columns([2, 1])
    with col1:
        with st.form("manual_transaction_form"):
            vendor = st.text_input("🏪 Vendor/Store Name")
            amount = st.number_input("💵 Amount (₹)", min_value=0.0, step=0.01, format="%.2f")
            category = st.selectbox("🏷️ Category", CATEGORIES)
            transaction_date = st.date_input("📅 Date", value=date.today())
            description = st.text_area("📝 Description (Optional)")
            submitted = st.form_submit_button("💾 Save Transaction", type="primary")
            if submitted:
                if vendor and amount > 0:
                    transaction_id = db.insert_transaction(vendor, amount, category, transaction_date, description, "manual_entry")
                    if transaction_id:
                        st.success(f"✅ Transaction saved! ID: {transaction_id}")
                        st.balloons()
                else:
                    st.error("❌ Please provide vendor name and amount.")
    with col2:
        st.subheader("📊 Quick Stats")
        transactions = db.get_transactions(limit=5)
        if transactions:
            st.write("**Recent Transactions:**")
            for t in transactions[:3]:
                st.write(f"• {t['vendor']}: ₹{t['amount']:.2f}")

def show_scanner():
    st.header("📷 Receipt Scanner")
    if not GEMINI_AVAILABLE:
        st.warning("🚫 Gemini not configured. Use manual entry.")
        return
    db = get_database()
    uploaded_file = st.file_uploader("📤 Upload Receipt", type=['jpg', 'jpeg', 'png'])
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            tmp_file.write(uploaded_file.getbuffer())
            tmp_file_path = tmp_file.name
        with st.spinner("🤖 Processing..."):
            receipt_data = extract_receipt_data(tmp_file_path)
            if receipt_data:
                st.success("✅ Receipt processed!")
                with st.form("receipt_form"):
                    vendor = st.text_input("🏪 Vendor", value=receipt_data.get('vendor', ''))
                    total_amount = receipt_data.get('total_amount', 0) or 0.0
                    try:
                        amount_value = float(total_amount)
                    except:
                        amount_value = 0.0
                    amount = st.number_input("💵 Amount", value=amount_value, min_value=0.0)
                    category = st.selectbox("🏷️ Category", CATEGORIES,
                        index=CATEGORIES.index(receipt_data.get('category', 'Other'))
                        if receipt_data.get('category') in CATEGORIES else 6)
                    try:
                        default_date = datetime.strptime(receipt_data.get('date', ''), '%Y-%m-%d').date()
                    except:
                        default_date = date.today()
                    transaction_date = st.date_input("📅 Date", value=default_date)
                    description = st.text_area("📝 Description", value=f"Receipt from {vendor}")
                    submitted = st.form_submit_button("💾 Save Transaction", type="primary")
                    if submitted and vendor and amount > 0:
                        transaction_id = db.insert_transaction(vendor, amount, category, transaction_date, description, "receipt_scan", raw_data=json.dumps(receipt_data))
                        if transaction_id:
                            st.success(f"✅ Transaction saved! ID: {transaction_id}")
                            st.balloons()
            else:
                st.error("❌ Could not process receipt.")
        os.unlink(tmp_file_path)

def show_budget_manager():
    st.header("🎯 Budget Manager")
    db = get_database()
    col1, col2 = st.columns(2)
    with col1:
        with st.form("budget_form"):
            category = st.selectbox("🏷️ Category", CATEGORIES)
            monthly_limit = st.number_input("💵 Monthly Budget (₹)", min_value=0.0, step=10.0, value=100.0)
            if st.form_submit_button("💾 Save Budget", type="primary"):
                if db.upsert_budget(category, monthly_limit):
                    st.success(f"✅ Budget saved for {category}: ₹{monthly_limit:.2f}")
                    st.rerun()
    with col2:
        st.subheader("📊 Budget Status")
        budget_summary = db.get_budget_summary()
        if not budget_summary:
            st.info("💡 No budgets set yet.")
            return
        for budget in budget_summary:
            category = budget['category']
            limit = float(budget['monthly_limit'])
            spent = float(budget['spent'])
            remaining = limit - spent
            percentage = (spent / limit * 100) if limit > 0 else 0
            if percentage > 100:
                status = "🔴 Over Budget"
            elif percentage > 80:
                status = "🟡 Warning"
            else:
                status = "🟢 On Track"
            st.metric(f"{category} {status}", f"₹{spent:.2f} / ₹{limit:.2f}", f"₹{remaining:.2f} remaining")
            st.progress(min(percentage / 100.0, 1.0))

# -------------------------
# Main
# -------------------------
def main():
    st.title("💰 FinSight AI - Personal Finance Tracker")
    db = get_database()
    if db.test_connection():
        st.sidebar.success("✅ Database Connected")
    else:
        st.sidebar.error("❌ Database Connection Failed")
        st.stop()

    st.sidebar.title("🧭 Navigation")
    page = st.sidebar.selectbox("Choose Page", [
        "📊 Dashboard",
        "✏️ Manual Entry",
        "📷 Receipt Scanner",
        "🎯 Budget Manager",
        "🧾 Tax Return Generator"
    ])

    if page == "📊 Dashboard":
        show_dashboard()
    elif page == "✏️ Manual Entry":
        show_manual_entry()
    elif page == "📷 Receipt Scanner":
        show_scanner()
    elif page == "🎯 Budget Manager":
        show_budget_manager()
    elif page == "🧾 Tax Return Generator":
        show_tax_generator()

    st.sidebar.markdown("---")
    st.sidebar.subheader("📈 Quick Stats")
    transactions = db.get_transactions(limit=None)
    transaction_count = len(transactions)
    total_spent = sum(float(t['amount']) for t in transactions) if transactions else 0.0
    st.sidebar.info(f"🧾 Transactions: {transaction_count}\n💰 Total Spent: ₹{total_spent:.2f}")

if __name__ == "__main__":
    main()
