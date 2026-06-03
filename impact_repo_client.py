import os
import re
import time
import logging
import requests
from pathlib import Path
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from logger import get_logger

logger = get_logger("jive.impact_repo_client")

REPO_SESSION_TTL_SECONDS = int(os.getenv("REPO_SESSION_TTL_SECONDS", "43200"))  # 12 hours

class ImpactRepoClient:
    def __init__(self):
        self.username = os.getenv("REPO_USERNAME")
        self.password = os.getenv("REPO_PASSWORD")
        self.session = None
        self.session_created_at = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
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
        
        # WordPress returns HTTP 200 even on failed login — verify cookies
        logged_in = any(name.startswith("wordpress_logged_in") for name in session.cookies.keys())
        if not logged_in:
            raise EnvironmentError(
                "WordPress login failed — no auth cookie received. "
                "Check REPO_USERNAME and REPO_PASSWORD in .env"
            )
        
        self.session = session
        self.session_created_at = time.monotonic()
        logger.info("Authenticated session created for IMPACT Repository successfully")
        return session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
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
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise  # Let tenacity retry these
        except Exception as e:
            logger.error("Failed to scrape Excel URL from repository page", exc_info=e, extra={"page_url": page_url})
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def download_excel(self, url: str, output_path: Path) -> bool:
        """Download an Excel file using the authenticated WordPress session."""
        session = self.get_authenticated_session()
        logger.info("Downloading Excel file from IMPACT Repository", extra={"url": url, "output": str(output_path)})
        max_bytes = int(os.getenv("JIVE_MAX_ATTACHMENT_MB", "250")) * 1024 * 1024
        response = session.get(url, stream=True, timeout=(5, 300))
        response.raise_for_status()

        downloaded_bytes = 0
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                downloaded_bytes += len(chunk)
                if downloaded_bytes > max_bytes:
                    logger.error("Download exceeded maximum allowed size", extra={"url": url, "max_mb": os.getenv("JIVE_MAX_ATTACHMENT_MB", "250")})
                    response.close()
                    output_path.unlink(missing_ok=True)
                    return False
                f.write(chunk)
        return True
