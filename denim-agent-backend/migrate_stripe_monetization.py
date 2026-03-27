import sqlite3

def run_migration():
    db_path = "denim_leads.db"
    print(f"Connecting to {db_path}...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Rename tier to subscription_tier
        print("Renaming 'tier' to 'subscription_tier'...")
        cursor.execute("ALTER TABLE user RENAME COLUMN tier TO subscription_tier")
    except sqlite3.OperationalError as e:
        print(f"Skipping rename (maybe already renamed): {e}")

    try:
        # Add stripe_customer_id
        print("Adding 'stripe_customer_id' column...")
        cursor.execute("ALTER TABLE user ADD COLUMN stripe_customer_id VARCHAR")
        cursor.execute("CREATE UNIQUE INDEX ix_user_stripe_customer_id ON user (stripe_customer_id)")
    except sqlite3.OperationalError as e:
        print(f"Skipping stripe_customer_id (maybe already exists): {e}")

    try:
        # Add credits
        print("Adding 'credits' column...")
        cursor.execute("ALTER TABLE user ADD COLUMN credits INTEGER DEFAULT 0 NOT NULL")
    except sqlite3.OperationalError as e:
        print(f"Skipping credits (maybe already exists): {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    run_migration()
