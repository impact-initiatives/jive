import logging
import re
import time
import urllib.parse
from pathlib import Path

import requests
from requests.sessions import Session
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import get_settings
from .logger import get_logger

logger = get_logger("jive.impact_repo_client")
settings = get_settings()


def _sanitize_url(url: str) -> str:
    """Remove query parameters from a URL to prevent token leakage in logs."""
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))


class ImpactRepoClient:
    def __init__(self):
        self.session: None | Session = None
        self.session_created_at: None | float = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_authenticated_session(self) -> requests.Session:
        """Return an authenticated Session for the IMPACT Repository (WordPress cookie auth).

        Sessions are cached but automatically re-authenticated after REPO_SESSION_TTL_SECONDS
        (default 12h) to prevent stale WordPress cookie failures on long-running workers.
        """
        if self.session is not None:
            elapsed = time.monotonic() - (self.session_created_at or 0)
            if elapsed < settings.repository_session_ttl:
                return self.session
            logger.info("Repository session expired after %ds — re-authenticating", int(elapsed))
            self.session = None

        if not settings.repository_username or not settings.repository_password:
            raise OSError("REPO_USERNAME and REPO_PASSWORD environment variables must be set")

        base_url = "https://repository.impact-initiatives.org"
        logger.info(
            "Creating authenticated session for IMPACT Repository",
            extra={"username": settings.repository_username.split("@")[0]},
        )

        session: Session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

        # Prime testcookie
        _ = session.get(f"{base_url}/wp-login.php", timeout=(3.05, 15))

        # Submit login form
        response = session.post(
            f"{base_url}/wp-login.php",
            data={
                "log": settings.repository_username,
                "pwd": settings.repository_password,
                "wp-submit": "Log In",
                "redirect_to": f"{base_url}/resources/",
                "testcookie": "1",
            },
            timeout=(3.05, 15),
            allow_redirects=True,
        )
        response.raise_for_status()

        # WordPress returns HTTP 200 even on failed login — verify cookies
        logged_in = any(str(name).startswith("wordpress_logged_in") for name in session.cookies)
        if not logged_in:
            raise OSError(
                "WordPress login failed — no auth cookie received. "
                + "Check REPO_USERNAME and REPO_PASSWORD in .env"
            )

        self.session = session
        self.session_created_at = time.monotonic()
        logger.info("Authenticated session created for IMPACT Repository successfully")
        return session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def scrape_excel_url(self, page_url: str) -> str | None:
        """Scrape a repository page to find the direct .xlsx download link."""
        logger.info("Scraping IMPACT Repository page for Excel link", extra={"page_url": page_url})
        try:
            session = self.get_authenticated_session()
            response = session.get(page_url, timeout=(3.05, 30))
            response.raise_for_status()

            match = re.search(
                r'href="(https://repository\.impact-initiatives\.org/[^"]+\.xlsx?)"',
                response.text,
            )
            if match:
                excel_url = match.group(1)
                logger.info(
                    "Excel download link found on repository page", extra={"excel_url": excel_url}
                )
                return excel_url

            logger.warning(
                "No .xlsx or .xls link found on repository page", extra={"page_url": page_url}
            )
            return None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            raise  # Let tenacity retry these
        except Exception as e:
            logger.error(
                "Failed to scrape Excel URL from repository page",
                exc_info=e,
                extra={"page_url": page_url},
            )
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def download_excel(self, url: str, output_path: Path) -> bool:
        """Download an Excel file using the authenticated WordPress session."""
        session = self.get_authenticated_session()
        parsed_url = urllib.parse.urlparse(url)

        if parsed_url.scheme != "https" or parsed_url.netloc not in settings.allowed_domains:
            logger.error(
                "SSRF Protection: URL domain not in allowed list",
                extra={"url": _sanitize_url(url), "domain": parsed_url.netloc},
            )
            return False

        logger.info(
            "Downloading Excel file from IMPACT Repository",
            extra={"url": _sanitize_url(url), "output": str(output_path)},
        )
        max_bytes = settings.max_attachment_size * 1024 * 1024
        response = session.get(url, stream=True, timeout=(3.05, 300))
        response.raise_for_status()

        downloaded_bytes = 0
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                downloaded_bytes += len(chunk)
                if downloaded_bytes > max_bytes:
                    logger.error(
                        "Download exceeded maximum allowed size",
                        extra={
                            "url": _sanitize_url(url),
                            "max_mb": settings.max_attachment_size,
                        },
                    )
                    response.close()
                    output_path.unlink(missing_ok=True)
                    return False
                _ = f.write(chunk)
        return True
