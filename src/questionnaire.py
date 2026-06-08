QUESTIONNAIRES = {
    "duplicate_charge": [
        "Did you make this purchase more than once?",
        "Have you contacted the merchant?",
        "What response did the merchant provide?"
    ],
    "services_not_rendered": [
        "What service were you expecting?",
        "Was the service canceled, delayed, or never provided?",
        "Have you contacted the merchant?"
    ],
    "incorrect_amount": [
        "What amount did you expect to be charged?",
        "Do you have a receipt or invoice?",
        "Have you contacted the merchant?"
    ],
    "unauthorized_fraud": [
        "Did you authorize this transaction?",
        "Is your card still in your possession?",
        "Do you recognize the merchant?",
        "Has anyone else had access to your card?"
    ],
    "goods_not_received": [
        "What item did you purchase?",
        "What was the expected delivery date?",
        "Do you have tracking information?",
        "Have you contacted the merchant?"
    ]
}


def classify_dispute_type(customer_input: str, checkbox_data: dict) -> str:
    text = customer_input.lower()

    if checkbox_data.get("charged_twice") or "twice" in text or "duplicate" in text:
        return "duplicate_charge"

    if checkbox_data.get("not_authorized") or "unauthorized" in text or "fraud" in text:
        return "unauthorized_fraud"

    if checkbox_data.get("service_not_received") or "service" in text:
        return "services_not_rendered"

    if checkbox_data.get("wrong_amount") or "wrong amount" in text or "overcharged" in text:
        return "incorrect_amount"

    if checkbox_data.get("goods_not_received") or "not received" in text:
        return "goods_not_received"

    return "general_dispute"


def get_questionnaire(dispute_type: str):
    return QUESTIONNAIRES.get(dispute_type, [
        "What is your concern with this charge?",
        "Have you contacted the merchant?",
        "Do you have supporting documentation?"
    ])