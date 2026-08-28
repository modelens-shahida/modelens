try:
    from prometheus_client import Counter
except ImportError:
    class DummyCounter:
        def __init__(self, *args, **kwargs):
            pass
        def inc(self, amount=1):
            pass
    def Counter(*args, **kwargs):
        return DummyCounter()

campaigns_total = Counter("campaigns_total", "Total campaigns processed")
campaigns_success = Counter("campaigns_success", "Total campaigns generated successfully")
campaigns_failed = Counter("campaigns_failed", "Total campaigns failed")
campaigns_retries = Counter("campaigns_retries", "Total campaign generation retries")
