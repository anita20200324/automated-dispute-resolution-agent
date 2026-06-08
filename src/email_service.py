from datetime import datetime


def generate_resolution_email(customer_name, transaction, final_decision, reason):
    return {
        "to": f"{customer_name.replace(' ', '.').lower()}@demo-customer.com",
        "subject": f"Resolution Notice for Dispute {transaction['transaction_id']}",
        "body": f"""
Dear {customer_name},

We have completed our review of your dispute.

Transaction ID: {transaction['transaction_id']}
Merchant: {transaction['merchant']}
Amount: ${float(transaction['amount']):,.2f}
Date: {transaction['date']}

Resolution:
{final_decision}

Reason:
{reason}

If your dispute was denied, you may request copies of the documents used in our investigation.

Thank you,
Global Retail Bank Dispute Resolution Team
""",
        "status": "DRAFT",
        "generated_at": datetime.now().isoformat()
    }


def send_email_mock(email_payload):
    email_payload["status"] = "SENT"
    email_payload["sent_at"] = datetime.now().isoformat()
    return email_payload