import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
import os

# Try to load from .env first, then fallback to config file
try:
    from dotenv import load_dotenv
    load_dotenv()
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'invoice_data'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD'),
        'port': os.getenv('DB_PORT', '5432')
    }
    # If password is not loaded from .env, use config file
    if not DB_CONFIG['password']:
        from database_config import DATABASE_CONFIG
        DB_CONFIG = DATABASE_CONFIG
        print("Using database_config.py for database connection")
except:
    # Fallback to config file
    from database_config import DATABASE_CONFIG
    DB_CONFIG = DATABASE_CONFIG
    print("Using database_config.py for database connection")

class DatabaseManager:
    def __init__(self):
        self.db_config = DB_CONFIG.copy()
        
        # Validate that password is set
        if not self.db_config['password']:
            error_msg = "Database password not found. Please check database_config.py file."
            print(f"Error: {error_msg}")
            if 'st' in globals():
                st.error(error_msg)
    
    def get_connection(self):
        """Get database connection"""
        try:
            return psycopg2.connect(**self.db_config)
        except psycopg2.Error as e:
            error_msg = f"Database connection error: {e}"
            print(error_msg)
            if 'st' in globals():
                st.error(error_msg)
            return None
    
    def test_connection(self):
        """Test database connection"""
        conn = self.get_connection()
        if conn:
            conn.close()
            return True
        return False
    
    def init_tables(self):
        """Initialize database tables"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
                
            with conn:
                with conn.cursor() as cur:
                    # Users table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            email VARCHAR(255),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Transactions table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS transactions (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER DEFAULT 1,
                            vendor VARCHAR(255),
                            amount DECIMAL(10,2),
                            category VARCHAR(100),
                            transaction_date DATE,
                            description TEXT,
                            is_recurring BOOLEAN DEFAULT FALSE,
                            source_type VARCHAR(50) DEFAULT 'receipt_scan',
                            raw_data JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # Budgets table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS budgets (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER DEFAULT 1,
                            category VARCHAR(100),
                            monthly_limit DECIMAL(10,2),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(user_id, category)
                        )
                    """)
                    
                    # Insert default user if not exists
                    cur.execute("""
                        INSERT INTO users (name, email) 
                        VALUES ('Demo User', 'demo@example.com') 
                        ON CONFLICT DO NOTHING
                    """)
                    
                    conn.commit()
                    print("Database tables initialized successfully!")
                    if 'st' in globals():
                        st.success("Database tables initialized successfully!")
                    return True
        except Exception as e:
            error_msg = f"Error initializing tables: {e}"
            print(error_msg)
            if 'st' in globals():
                st.error(error_msg)
            return False
        finally:
            if conn:
                conn.close()
    
    def insert_transaction(self, vendor, amount, category, transaction_date, description="", source_type="receipt_scan", raw_data=None):
        """Insert a new transaction"""
        try:
            conn = self.get_connection()
            if not conn:
                return None
                
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO transactions 
                        (vendor, amount, category, transaction_date, description, source_type, raw_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (vendor, amount, category, transaction_date, description, source_type, raw_data))
                    
                    transaction_id = cur.fetchone()[0]
                    conn.commit()
                    return transaction_id
        except Exception as e:
            error_msg = f"Error inserting transaction: {e}"
            print(error_msg)
            if 'st' in globals():
                st.error(error_msg)
            return None
        finally:
            if conn:
                conn.close()
    
    def get_transactions(self, limit=None):
        """Get all transactions"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
                
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    query = "SELECT * FROM transactions ORDER BY transaction_date DESC"
                    if limit:
                        query += f" LIMIT {limit}"
                    
                    cur.execute(query)
                    result = cur.fetchall()
                    return result
        except Exception as e:
            error_msg = f"Error fetching transactions: {e}"
            print(error_msg)
            if 'st' in globals():
                st.error(error_msg)
            return []
        finally:
            if conn:
                conn.close()
    
    def get_budget_summary(self):
        """Get budget summary with spending"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
                
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT 
                            b.category,
                            b.monthly_limit,
                            COALESCE(SUM(t.amount), 0) as spent
                        FROM budgets b
                        LEFT JOIN transactions t ON b.category = t.category
                            AND EXTRACT(MONTH FROM t.transaction_date) = EXTRACT(MONTH FROM CURRENT_DATE)
                            AND EXTRACT(YEAR FROM t.transaction_date) = EXTRACT(YEAR FROM CURRENT_DATE)
                        GROUP BY b.category, b.monthly_limit
                        ORDER BY b.category
                    """)
                    result = cur.fetchall()
                    return result
        except Exception as e:
            error_msg = f"Error fetching budget summary: {e}"
            print(error_msg)
            if 'st' in globals():
                st.error(error_msg)
            return []
        finally:
            if conn:
                conn.close()
    
    def upsert_budget(self, category, monthly_limit):
        """Insert or update budget"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
                
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO budgets (category, monthly_limit)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id, category) 
                        DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit
                    """, (category, monthly_limit))
                    conn.commit()
                    return True
        except Exception as e:
            error_msg = f"Error updating budget: {e}"
            print(error_msg)
            if 'st' in globals():
                st.error(error_msg)
            return False
        finally:
            if conn:
                conn.close()

# Global database instance
_database_instance = None

def get_database():
    """Get cached database instance"""
    global _database_instance
    if _database_instance is None:
        _database_instance = DatabaseManager()
        if _database_instance.test_connection():
            _database_instance.init_tables()  # Initialize tables on first load
    return _database_instance