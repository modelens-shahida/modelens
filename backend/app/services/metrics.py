from prometheus_client import Counter

campaigns_total = Counter("campaigns_total", "Total campaigns processed")
campaigns_success = Counter("campaigns_success", "Total campaigns generated successfully")
campaigns_failed = Counter("campaigns_failed", "Total campaigns failed")
campaigns_retries = Counter("campaigns_retries", "Total campaign generation retries")
