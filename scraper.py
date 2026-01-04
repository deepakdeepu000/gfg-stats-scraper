
"""
GeeksforGeeks Profile Scraper API (Optimized)

This module provides asynchronous functions to scrape user profile data.
It uses a SHARED global browser instance to handle concurrent requests efficiently.
"""

import re
import asyncio
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, Playwright

# Constants
GFG_BASE_URL = "https://www.geeksforgeeks.org/profile"
TIMEOUT_STD = 45000  
TIMEOUT_SHORT = 30000

# Global State for Reusing Browser
_PLAYWRIGHT: Optional[Playwright] = None
_BROWSER: Optional[Browser] = None
_LOCK = asyncio.Lock()

_REQUEST_COUNT = 0
_MAX_REQUESTS_PER_BROWSER = 100

async def get_browser() -> Browser:
    global _PLAYWRIGHT, _BROWSER, _REQUEST_COUNT
    
    async with _LOCK:
        # Recreate browser after threshold to prevent memory buildup
        if _BROWSER and _REQUEST_COUNT >= _MAX_REQUESTS_PER_BROWSER:
            await _BROWSER.close()
            _BROWSER = None
            _REQUEST_COUNT = 0
        
        if _BROWSER is None:
            print("🚀 Launching Global Browser...")
            _PLAYWRIGHT = await async_playwright().start()
            _BROWSER = await _PLAYWRIGHT.firefox.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
        _REQUEST_COUNT += 1
    return _BROWSER

async def close_browser():
    """Call this on app shutdown to clean up resources."""
    global _PLAYWRIGHT, _BROWSER
    
    print("🛑 Shutting down Global Browser...")
    async with _LOCK:  # <--- FIX: Acquire lock to prevent race with get_browser
        if _BROWSER:
            try:
                await _BROWSER.close()
            except Exception as e:
                # Ignore errors if browser is already closed/crashed
                print(f"⚠️ Browser close error (ignored): {e}")
            finally:
                _BROWSER = None
        
        if _PLAYWRIGHT:
            try:
                await _PLAYWRIGHT.stop()
            except Exception:
                pass
            _PLAYWRIGHT = None
            
    print("✅ Global Browser Stopped")


# --- Scraper Functions ---

async def fetch_user_profile(username: str) -> Dict[str, Any]:
    url = f"{GFG_BASE_URL}/{username}"
    browser = await get_browser()
    
    # Create lightweight context (like a new tab)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()

    try:
        await page.goto(url, wait_until="networkidle", timeout=TIMEOUT_SHORT)
        
        # Check if user exists (redirects often imply invalid user)
        if "auth" in page.url:
             return {"error": "User not found or profile private", "userName": username}

        data = {
            "userName": username,
            "fullName": "",
            "designation": "",
            "codingScore": 0,
            "problemsSolved": 0,
            "instituteRank": 0,
            "articlesPublished": 0,
            "potdStreak": 0,
            "longestStreak": 0,
            "potdsSolved": 0
        }

        # Safe extraction helper
        async def get_text(selector):
            if await page.locator(selector).count() > 0:
                return await page.locator(selector).first.text_content()
            return ""

        data["fullName"] = await get_text(".NewProfile_name__N_Nlw") or username
        data["designation"] = await get_text(".NewProfile_designation__fujtZ")

        # Extract Score Cards
        cards = page.locator(".ScoreContainer_score-card__zI4vG")
        count = await cards.count()
        
        for i in range(count):
            card = cards.nth(i)
            label = await card.locator(".ScoreContainer_label__aVpLE").text_content()
            val_text = await card.locator(".ScoreContainer_value__7yy7h").text_content()
            
            if not label or not val_text: continue
            
            val = val_text.strip()
            if val == "__": continue
            
            try:
                num = int(val)
                if "Coding Score" in label: data["codingScore"] = num
                elif "Problems Solved" in label: data["problemsSolved"] = num
                elif "Institute Rank" in label: data["instituteRank"] = num
                elif "Articles Published" in label: data["articlesPublished"] = num
            except: pass

        # Extract POTD
        streak_items = page.locator(".PotdContainer_statItem__YU3BX")
        s_count = await streak_items.count()
        for i in range(s_count):
            item = streak_items.nth(i)
            lbl = await item.locator(".PotdContainer_statLabel__tc6R1").text_content()
            val = await item.locator(".PotdContainer_statValue__nt1dr").text_content()
            
            if lbl and val:
                try:
                    num = int(val.strip().split()[0]) # "120 / 500" -> 120
                    if "Longest Streak" in lbl: data["longestStreak"] = num
                    elif "POTDs Solved" in lbl: data["potdsSolved"] = num
                except: pass

        return data

    except Exception as e:
        return {"error": str(e), "userName": username}
    finally:
        await page.close()
        await context.close()

async def get_gfg_data(username: str) -> Dict[str, Any]:
    url = f"{GFG_BASE_URL}/{username}?tab=activity"
    
    browser = await get_browser()
    context = await browser.new_context(
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=TIMEOUT_SHORT)
        
        navbar = page.locator('.ProblemNavbar_head__6ptDV')
        if await navbar.count() == 0:
            return {"error": "Stats not found", "userName": username}

        text = await navbar.text_content()
        numbers = re.findall(r'\((\d+)\)', text)
        tags = ["School", "Basic", "Easy", "Medium", "Hard"]
        
        if len(numbers) >= 5:
            stats = {tags[i]: int(numbers[i]) for i in range(5)}
            stats["userName"] = username
            stats["totalProblemsSolved"] = sum(int(v) if isinstance(v, str) else v for v in stats.values() if isinstance(v, (int, str)) and str(v).isdigit())
            return stats
            
        return {"error": "Incomplete stats", "userName": username}

    except Exception as e:
        return {"error": str(e), "userName": username}
    finally:
        await page.close()
        await context.close()

async def fetch_problem_list(username: str) -> Dict[str, Any]:
    """
    Scrapes the detailed list of solved problems for each difficulty level.
    This function interacts with UI tabs to load dynamic content.

    Args:
        username (str): The GeeksforGeeks username.

    Returns:
        Dict: A dictionary mapping difficulty levels to lists of problem objects.
    """
    url = f"{GFG_BASE_URL}/{username}?tab=activity"

    async with async_playwright() as p:
        try:
            # browser, page = await _get_browser_page(p)
            browser = await get_browser() 
            context = await browser.new_context()       
            page = await context.new_page()
            # Use domcontentloaded for faster initial render, we wait for specific elements later
            await page.goto(url, wait_until="networkidle", timeout=TIMEOUT_STD)

            difficulties = ["SCHOOL", "BASIC", "EASY", "MEDIUM", "HARD"]
            all_problems = {}
            total_problems = {}
            
            # Check if the main navbar exists before iterating
            if await page.locator(".ProblemNavbar_head__6ptDV").count() == 0:
                 return {"error": "Activity tab content not found", "userName": username}

            for diff in difficulties:
                # Selector for the specific difficulty tab (e.g., "MEDIUM (50)")
                tab_selector = f".ProblemNavbar_head_nav__OqbEt:has-text('{diff}')"
                tab = page.locator(tab_selector)
                
                # Default to 0 if tab not found
                count = 0
                if await tab.count() > 0:
                    tab_text = await tab.inner_text()
                    # Extract count from text like "MEDIUM (12)"
                    match = re.search(r'\((\d+)\)', tab_text)
                    if match:
                        count = int(match.group(1))
                
                total_problems[diff.capitalize()] = count

                # If count is 0, skip clicking and extraction
                if count == 0:
                    all_problems[diff.capitalize()] = []
                    continue

                # Click the tab to load the problem list
                await tab.click()

                # Selector for the list of problems
                list_selector = "ul.SolvedProblemsContainer_problemList__8Ua09"
                
                try:
                    # Wait for the list to appear in the DOM
                    await page.wait_for_selector(list_selector, timeout=TIMEOUT_SHORT)
                    
                    # Optimization: Use page.evaluate to extract all links in one JS execution.
                    # This is significantly faster than iterating through locators in Python.
                    problems = await page.evaluate("""
                        (selector) => {
                            const container = document.querySelector(selector);
                            if (!container) return [];
                            const links = container.querySelectorAll("li a");
                            return Array.from(links).map(a => ({
                                question: a.innerText.trim(),
                                questionUrl: a.href
                            }));
                        }
                    """, list_selector)
                    
                    all_problems[diff.capitalize()] = problems

                except Exception:
                    # Fallback if list selector doesn't appear (e.g., UI glitch or loading error)
                    print(f"Warning: Could not load problem list for {diff}")
                    all_problems[diff.capitalize()] = []

            return {
                "userName": username,
                "problemsByDifficulty": total_problems,
                "Problems": all_problems
            }

        except Exception as e:
            return {"error": f"Failed to fetch problem list: {str(e)}", "userName": username}
        finally:
             await context.close() 
