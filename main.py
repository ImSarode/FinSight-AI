import streamlit as st
import pandas as pd
import plotly.express as px
import tempfile
import os
import json
import sys
from datetime import datetime, date

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
    st.sidebar.warning("Gemini AI not configured - Receipt scanning disabled")

# Configure page
st.set_page_config(page_title="FinSight AI", page_icon="💰", layout="wide")

CATEGORIES = ['Inventory Purchase', 'Staff Welfare', 'Marketing & Promotion', 'Utilities', 'Owner\'s Draw', 'Executive Lunch', 'Logistics', 'IT & Software', 'Business Travel', 'Loan Repayment', 'Store Supplies', 'Shipping & Delivery', 'Office Supplies', 'Staff Uniforms', 'Transportation', 'Promotional Items', 'Miscellaneous', 'Store Maintenance', 'Shopping', 'Staff Training', 'Taxes & Licenses', 'Marketing' ]

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
        Categories: Store Supplies, Shipping & Delivery, Store Maintenance, Miscellaneous, Marketing & Promotion, Staff Training, Transportation
        """
        
        response = model.generate_content([uploaded_file, prompt])
        
        # Parse JSON
        json_text = response.text.strip()
        if json_text.startswith("```json"):
            json_text = json_text[7:-3]
        elif json_text.startswith("```"):
            json_text = json_text[3:-3]
        
        return json.loads(json_text)
        
    except Exception as e:
        st.error(f"Error processing receipt: {e}")
        return None

def show_dashboard():
    """Show dashboard with database data"""
    st.header("📊 Dashboard")
    
    db = get_database()
    
    # Get transactions from database
    transactions = db.get_transactions(limit=None)
    
    if not transactions:
        st.info("💡 No transactions yet. Add a transaction manually or upload a receipt to get started!")
        
        # Add sample data button
        if st.button("🎲 Add Sample Data", type="secondary"):
            sample_transactions = [
                ("Starbucks", 12.50, "Food", date.today(), "Coffee and pastry"),
                ("Uber", 23.75, "Transportation", date.today(), "Ride to downtown"),
                ("Amazon", 45.99, "Shopping", date.today(), "Books and supplies"),
                ("Netflix", 15.99, "Entertainment", date.today(), "Monthly subscription"),
            ]
            
            for vendor, amount, category, trans_date, desc in sample_transactions:
                db.insert_transaction(vendor, amount, category, trans_date, desc, "sample_data")
            
            st.success("Sample data added!")
            st.rerun()
        
        return
    
    # Convert to DataFrame and handle data types
    df = pd.DataFrame(transactions)
    
    # Convert amount column to float to handle Decimal types
    df['amount'] = df['amount'].astype(float)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_spent = df['amount'].sum()
        st.metric("💰 Total Spent", f"₹{total_spent:.2f}")
    
    with col2:
        avg_transaction = df['amount'].mean()
        st.metric("📈 Avg Transaction", f"₹{avg_transaction:.2f}")
    
    with col3:
        transaction_count = len(df)
        st.metric("🧾 Transactions", transaction_count)
    
    with col4:
        categories_used = df['category'].nunique()
        st.metric("🏷️ Categories", categories_used)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Category pie chart
        category_data = df.groupby('category')['amount'].sum().reset_index()
        if not category_data.empty:
            fig_pie = px.pie(category_data, values='amount', names='category', 
                           title='💸 Spending by Category')
            st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Budget comparison from database
        budget_summary = db.get_budget_summary()
        if budget_summary:
            budget_df = pd.DataFrame(budget_summary)
            fig_budget = px.bar(budget_df, x='category', y=['monthly_limit', 'spent'],
                              title='🎯 Budget vs Spending', barmode='group')
            st.plotly_chart(fig_budget, use_container_width=True)
        else:
            st.info("💡 Set budgets in the Budget Manager to see comparison chart!")
    
    # Recent transactions
    st.subheader("📋 Recent Transactions")
    display_df = df[['vendor', 'amount', 'category', 'transaction_date', 'source_type']].copy()
    display_df['amount'] = display_df['amount'].apply(lambda x: f"₹{x:.2f}")
    st.dataframe(display_df.head(10), use_container_width=True)

def show_manual_entry():
    """Show manual transaction entry"""
    st.header("✏️ Manual Entry")
    
    db = get_database()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.form("manual_transaction_form"):
            st.subheader("Add New Transaction")
            
            vendor = st.text_input("🏪 Vendor/Store Name", placeholder="e.g., Starbucks, Amazon, Uber")
            amount = st.number_input("💵 Amount (₹)", min_value=0.0, step=0.01, format="%.2f")
            category = st.selectbox("🏷️ Category", CATEGORIES)
            transaction_date = st.date_input("📅 Date", value=date.today())
            description = st.text_area("📝 Description (Optional)", placeholder="Additional notes about this transaction")
            
            submitted = st.form_submit_button("💾 Save Transaction", type="primary")
            
            if submitted:
                if vendor and amount > 0:
                    transaction_id = db.insert_transaction(
                        vendor=vendor,
                        amount=amount,
                        category=category,
                        transaction_date=transaction_date,
                        description=description,
                        source_type="manual_entry"
                    )
                    
                    if transaction_id:
                        st.success(f"✅ Transaction saved successfully! ID: {transaction_id}")
                        st.balloons()
                        
                        # Budget alert
                        budget_summary = db.get_budget_summary()
                        for budget in budget_summary:
                            if budget['category'] == category:
                                spent = float(budget['spent']) + amount
                                limit = float(budget['monthly_limit'])
                                
                                if spent > limit:
                                    st.warning(f"⚠️ Budget exceeded for {category}! Spent: ₹{spent:.2f}, Budget: ₹{limit:.2f}")
                                elif spent > limit * 0.8:
                                    st.info(f"💡 You're at {(spent/limit)*100:.1f}% of your {category} budget")
                                break
                    else:
                        st.error("❌ Failed to save transaction. Please try again.")
                else:
                    st.error("❌ Please provide both vendor name and amount.")
    
    with col2:
        st.subheader("📊 Quick Stats")
        transactions = db.get_transactions(limit=5)
        if transactions:
            st.write("**Recent Transactions:**")
            for t in transactions[:3]:
                st.write(f"• {t['vendor']}: ₹{t['amount']:.2f}")
        
        # Show categories
        st.write("**Available Categories:**")
        for cat in CATEGORIES:
            st.write(f"• {cat}")

def show_scanner():
    """Show receipt scanner"""
    st.header("📷 Receipt Scanner")
    
    if not GEMINI_AVAILABLE:
        st.warning("🚫 Receipt scanning is not available. Gemini AI is not configured.")
        st.info("💡 You can still add transactions manually using the Manual Entry page.")
        return
    
    db = get_database()
    
    uploaded_file = st.file_uploader("📤 Upload Receipt Image", type=['jpg', 'jpeg', 'png'])
    
    if uploaded_file:
        col1, col2 = st.columns(2)
        
        with col1:
            st.image(uploaded_file, caption="📄 Uploaded Receipt", use_container_width=True)
        
        with col2:
            with st.spinner("🤖 Processing with AI..."):
                # Save temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_file.write(uploaded_file.getbuffer())
                    tmp_file_path = tmp_file.name
                
                # Process
                receipt_data = extract_receipt_data(tmp_file_path)
                
                if receipt_data:
                    st.success("✅ Receipt processed successfully!")
                    
                    # Form for editing
                    with st.form("receipt_form"):
                        st.subheader("📝 Review & Edit")
                        vendor = st.text_input("🏪 Vendor", value=receipt_data.get('vendor', ''))
                        
                        # Safe handling of total_amount
                        total_amount = receipt_data.get('total_amount', 0)
                        if total_amount is None or total_amount == '':
                            total_amount = 0.0
                        try:
                            amount_value = float(total_amount)
                        except (ValueError, TypeError):
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
                        
                        # FIXED: Added submit button
                        submitted = st.form_submit_button("💾 Save Transaction", type="primary")
                        
                        if submitted:
                            if vendor and amount > 0:
                                transaction_id = db.insert_transaction(
                                    vendor=vendor,
                                    amount=amount,
                                    category=category,
                                    transaction_date=transaction_date,
                                    description=description,
                                    source_type="receipt_scan",
                                    raw_data=json.dumps(receipt_data)
                                )
                                
                                if transaction_id:
                                    st.success(f"✅ Transaction saved! ID: {transaction_id}")
                                    st.balloons()
                                else:
                                    st.error("❌ Failed to save transaction.")
                            else:
                                st.error("❌ Please provide vendor name and amount.")
                else:
                    st.error("❌ Could not process receipt. Please try manual entry.")
                
                # Cleanup
                os.unlink(tmp_file_path)

def show_budget_manager():
    """Show budget manager"""
    st.header("🎯 Budget Manager")
    
    db = get_database()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Set Budgets")
        
        with st.form("budget_form"):
            category = st.selectbox("🏷️ Category", CATEGORIES)
            monthly_limit = st.number_input("💵 Monthly Budget Limit (₹)", min_value=0.0, step=10.0, value=100.0)
            
            if st.form_submit_button("💾 Save Budget", type="primary"):
                if db.upsert_budget(category, monthly_limit):
                    st.success(f"✅ Budget saved for {category}: ₹{monthly_limit:.2f}")
                    st.rerun()
    
    with col2:
        st.subheader("📊 Budget Status")
        
        budget_summary = db.get_budget_summary()
        
        if not budget_summary:
            st.info("💡 No budgets set yet. Create your first budget!")
            return
        
        for budget in budget_summary:
            category = budget['category']
            limit = float(budget['monthly_limit'])  # Convert Decimal to float
            spent = float(budget['spent'])  # Convert Decimal to float
            remaining = limit - spent
            percentage = (spent / limit * 100) if limit > 0 else 0
            
            # Color coding
            if percentage > 100:
                status = "🔴 Over Budget"
            elif percentage > 80:
                status = "🟡 Warning"
            else:
                status = "🟢 On Track"
            
            st.metric(f"{category} {status}", 
                     f"₹{spent:.2f} / ₹{limit:.2f}",
                     f"₹{remaining:.2f} remaining")
            
            # FIXED: Convert to float for progress bar
            progress = min(float(percentage) / 100.0, 1.0)
            st.progress(progress)

def main():
    """Main app"""
    st.title("💰 FinSight AI - Personal Finance Tracker")
    
    # Database connection status
    db = get_database()
    if db.test_connection():
        st.sidebar.success("✅ Database Connected")
    else:
        st.sidebar.error("❌ Database Connection Failed")
        st.error("Cannot connect to database. Please check your database_config.py file.")
        st.stop()
    
    # Sidebar navigation
    st.sidebar.title("🧭 Navigation")
    page = st.sidebar.selectbox("Choose Page", [
        "📊 Dashboard", 
        "✏️ Manual Entry", 
        "📷 Receipt Scanner", 
        "🎯 Budget Manager"
    ])
    
    if page == "📊 Dashboard":
        show_dashboard()
    elif page == "✏️ Manual Entry":
        show_manual_entry()
    elif page == "📷 Receipt Scanner":
        show_scanner()
    elif page == "🎯 Budget Manager":
        show_budget_manager()
    
    # Sidebar stats
    st.sidebar.markdown("---")
    st.sidebar.subheader("📈 Quick Stats")
    transactions = db.get_transactions(limit=None)
    transaction_count = len(transactions)
    # Convert Decimal to float for calculations
    total_spent = sum(float(t['amount']) for t in transactions) if transactions else 0.0
    st.sidebar.info(f"🧾 Transactions: {transaction_count}\n💰 Total Spent: ₹{total_spent:.2f}")

if __name__ == "__main__":
    main()