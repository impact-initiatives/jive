import os
import re
import time
import requests
from typing import Optional
from logger import get_logger

logger = get_logger("jive.impact_repo_client")

REPO_SESSION_TTL_SECONDS = int(os.getenv("REPO_SESSION_TTL_SECONDS", "43200"))  # 12 hours

class ImpactRepoClient:
    def __init__(self):
        self.username = os.getenv("REPO_USERNAME")
        self.password = os.getenv("REPO_PASSWORD")
        self.session = None
        self.session_created_at = None

    def get_authenticated_session(self) -> requests.Session:
        """Return an authenticated Session for the IMPACT Repository (WordPress cookie auth).
        
        Sessions are cached but automatically re-authenticated after REPO_SESSION_TTL_SECONDS
        (default 12h) to prevent stale WordPress cookie failures on long-running workers.
        """
        if self.session is not None:
            elapsed = time.monotonic() - (self.session_created_at or 0)
            if elapsed < REPO_SESSION_TTL_SECONDS:
                return self.session
            logger.info("Repository session expired after %ds — re-authenticating", int(elapsed))
            self.session = None

        if not self.username or not self.password:
            raise EnvironmentError("REPO_USERNAME and REPO_PASSWORD environment variables must be set")

        base_url = "https://repository.impact-initiatives.org"
        logger.info("Creating authenticated session for IMPACT Repository", extra={"username": self.username.split("@")[0]})
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        
        # Prime testcookie
        session.get(f"{base_url}/wp-login.php", timeout=15)
        
        # Submit login form
        response = session.post(
            f"{base_url}/wp-login.php",
            data={
                "log": self.username,
                "pwd": self.password,
                "wp-submit": "Log In",
                "redirect_to": f"{base_url}/resources/",
                "testcookie": "1",
            },
            timeout=15,
            allow_redirects=True,
        )
        response.raise_for_status()
        
        self.session = session
        self.session_created_at = time.monotonic()
        logger.info("Authenticated session created for IMPACT Repository successfully")
        return session

    def scrape_excel_url(self, page_url: str) -> Optional[str]:
        """Scrape a repository page to find the direct .xlsx download link."""
        logger.info("Scraping IMPACT Repository page for Excel link", extra={"page_url": page_url})
        try:
            session = self.get_authenticated_session()
            response = session.get(page_url, timeout=15)
            response.raise_for_status()
            
            match = re.search(
                r'href="(https://repository\.impact-initiatives\.org/[^"]+\.xlsx?)"',
                response.text,
            )
            if match:
                excel_url = match.group(1)
                logger.info("Excel download link found on repository page", extra={"excel_url": excel_url})
                return excel_url
            
            logger.warning("No .xlsx or .xls link found on repository page", extra={"page_url": page_url})
            return None
        except Exception as e:
            logger.error("Failed to scrape Excel URL from repository page", exc_info=e, extra={"page_url": page_url})
            return None
