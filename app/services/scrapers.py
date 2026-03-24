from __future__ import annotations

from typing import Any
from playwright.sync_api import sync_playwright


class SportsbookScraper:
    """Example scraper hook.

    Replace selectors and targets with a source you are allowed to scrape.
    """

    def fetch_example_lines(self, url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            for card in page.locator("[data-prop-card]").all():
                rows.append({
                    "player": card.get_attribute("data-player"),
                    "market": card.get_attribute("data-market"),
                    "line": card.get_attribute("data-line"),
                })
            browser.close()
        return rows
