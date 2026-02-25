from app.services.financial_intelligence import get_financial_intelligence

service = get_financial_intelligence()
print("Oyo 2026 budget:", service.search_financials("Oyo 2026 budget").get("metadata", {}).get("total_returned"))
print("Oyo 2026:", service.search_financials("Oyo 2026").get("metadata", {}).get("total_returned"))
