from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IDXSeleniumScraper:
    """Scraper using Selenium to handle JavaScript and anti-bot measures"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None

    def _setup_driver(self):
        """Setup Chrome driver with options"""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument('--headless')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        self.driver = webdriver.Chrome(options=chrome_options)

    def scrape_company(self, emiten_code: str) -> Dict:
        """Scrape company using Selenium"""
        url = f"https://www.idx.co.id/en/listed-companies/company-profiles/{emiten_code}"

        try:
            if not self.driver:
                self._setup_driver()
            
            logger.info(f"Loading page for {emiten_code}...")
            self.driver.get(url)

            # Wait for the body to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Get page source
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Extract data
            data = {
                'Emiten_Code': emiten_code,
                'URL': url,
                'Status': 'Success',
                'Profile': self._extract_section(soup, 'Profile'),
                'Director': self._extract_section(soup, 'Director'),
                'Comissioners': self._extract_section(soup, 'Comissioners'),
                'Audit_Committee': self._extract_section(soup, 'Audit Committee'),
                'Shareholders': self._extract_section(soup, 'Shareholders'),
                'Subsidiary': self._extract_section(soup, 'Subsidiary'),
                'Public_Accountant': self._extract_section(soup, 'Public Accountant')
            }

            logger.info(f"✓ Successfully scraped {emiten_code}")
            return data
            
        except Exception as e:
            logger.error(f"✗ Error scraping {emiten_code}: {str(e)}")
            return self._get_error_dict(emiten_code, url, str(e))
    
    def _extract_section(self, soup: BeautifulSoup, keyword: str) -> str:
        try:
            # Find the section related to the keyword
            section_header = soup.find(string=lambda text: text and keyword.lower() in text.lower())
            
            if section_header:
                # Get the nearest parent to the section header
                parent = section_header.find_parent(['h2', 'h3', 'div'])
                # Initialize a list to accumulate the section text
                section_text = []
                
                for sibling in parent.find_next_siblings():
                    if sibling.name in ['h2', 'h3',]:  # Stop if we hit another header
                        break
                    
                    # Get the text while stripping extra spaces
                    text = sibling.get_text(strip=False)

                    if text:
                        # Append the text to the list, ensuring to add a delimiter
                        section_text.append(text + ' | ')  # Add line delimiter here

                # Join all text parts; handle significant spaces by filtering
                combined_text = '|'.join(section_text).strip()
                # Replace instances of multiple spaces with a single '|' as delimiter
                return ' | '.join(filter(None, combined_text.split('  ')))#.strip(' | ')
            
            return "Not found"
        except Exception as e:
            return f"Error: {str(e)}"



    def _get_error_dict(self, emiten_code: str, url: str, error: str) -> Dict:
        return {
            'Emiten_Code': emiten_code,
            'URL': url,
            'Status': f'Error: {error}',
            'Profile': 'N/A',
            'Director': 'N/A',
            'Comissioners': 'N/A',
            'Audit_Committee': 'N/A',
            'Shareholders': 'N/A',
            'Subsidiary': 'N/A',
            'Public_Accountant': 'N/A'
        }

    def scrape_multiple(self, emiten_list: List[str], delay: int = 3) -> pd.DataFrame:
        """Scrape multiple companies"""
        results = []

        try:
            for i, emiten in enumerate(emiten_list, 1):
                logger.info(f"Processing {i}/{len(emiten_list)}: {emiten}")
                data = self.scrape_company(emiten)
                results.append(data)

                if i < len(emiten_list):
                    time.sleep(delay)
        finally:
            if self.driver:
                self.driver.quit()

        return pd.DataFrame(results)