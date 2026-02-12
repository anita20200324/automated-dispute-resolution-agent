import pandas as pd
import random
from datetime import datetime, timedelta

# Settings
num_records = 100
merchants = ["Starbucks", "Amazon", "Walmart", "Shell", "Netflix", "Apple Store", "Delta Airlines", "Crypto.com", "Luxury Watches", "Uber"]
customers = [f"CUST-{i:03d}" for i in range(1, 15)] # 15 regular customers
customers.extend(["FRAUD_VELOCITY", "FRAUD_SPIKE"]) # Specific test cases

data = []

for i in range(1, num_records + 1):
    tx_id = f"TXN-{i:03d}"
    
    # Logic for Fraud Spikes
    if i > 90:
        cust = "FRAUD_SPIKE"
        merchant = "Luxury Watches"
        amount = random.uniform(5000, 9000)
    # Logic for Velocity (Same day, same user)
    elif i > 80:
        cust = "FRAUD_VELOCITY"
        merchant = "Crypto.com"
        amount = 2000.00
    else:
        cust = random.choice(customers[:15])
        merchant = random.choice(merchants[:7])
        amount = round(random.uniform(5, 500), 2)

    date = (datetime(2026, 2, 1) + timedelta(days=random.randint(0, 10))).strftime("%Y-%m-%d")
    
    data.append([tx_id, cust, merchant, amount, date, "Standard"])

df = pd.DataFrame(data, columns=["transaction_id", "customer_id", "merchant", "amount", "date", "status"])
df.to_csv("data/transactions.csv", index=False)
print("Successfully generated 100 records in data/transactions.csv")