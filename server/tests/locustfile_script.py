from locust import HttpUser, task, between

class RedirectUser(HttpUser):
    wait_time = between(0, 0)   # hammer, no think-time

    @task
    def hit_redirect(self):
        # use ONE known-good short code that exists in your DB
        self.client.get(
            "/typeshit",
            allow_redirects=False,          # measure YOUR latency, not the target site's
            name="/[code]",                 # group all as one row in stats
        )