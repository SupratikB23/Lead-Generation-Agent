import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class WebsiteScraper:
    def __init__(self, timeout=10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'
        })
        
    def extract_email(self, url: str) -> str:
        """Extract email from website contact/about pages."""
        if not url or not url.startswith('http'):
            return ""
            
        emails = set()
        
        try:
            # Try main page
            resp = self.session.get(url, timeout=self.timeout)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Regex for email
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            emails.update(re.findall(email_pattern, resp.text))
            
            # Check mailto links
            for link in soup.find_all('a', href=True):
                if 'mailto:' in link['href']:
                    emails.add(link['href'].replace('mailto:', '').split('?')[0])
                    
            # Try contact page
            contact_urls = []
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                if any(x in href for x in ['contact', 'about', 'reach']):
                    contact_urls.append(urljoin(url, link['href']))
                    
            for contact_url in contact_urls[:3]:  # Limit to 3 pages
                try:
                    resp = self.session.get(contact_url, timeout=self.timeout)
                    emails.update(re.findall(email_pattern, resp.text))
                except:
                    continue
                    
            # Filter valid emails
            valid_emails = [e for e in emails if not any(x in e.lower() for x in ['example', 'test', 'noreply', 'no-reply', 'sentry'])]
            return valid_emails[0] if valid_emails else ""
            
        except Exception as e:
            return ""
    
    def estimate_revenue(self, url: str, business_type: str) -> str:
        """
        Estimate revenue based on team size mentions, client logos, 
        or industry heuristics. Very rough estimate.
        """
        try:
            resp = self.session.get(url, timeout=self.timeout)
            text = resp.text.lower()
            
            # Look for team size indicators
            team_indicators = {
                '1-10': ['small team', 'boutique', 'startup', 'founder'],
                '11-50': ['growing team', 'mid-sized', 'established'],
                '50-200': ['large team', 'enterprise', 'corporate'],
                '200+': ['fortune', 'global', 'multinational', 'leading']
            }
            
            for size, keywords in team_indicators.items():
                if any(k in text for k in keywords):
                    return size
                    
            return "Unknown"
        except:
            return "Unknown"
    
    def extract_team_info(self, url: str) -> str:
        """Extract team size or member names from website."""
        try:
            resp = self.session.get(url, timeout=self.timeout)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Look for team sections
            team_sections = soup.find_all(['section', 'div'], string=lambda x: x and 'team' in x.lower())
            if team_sections:
                return "Team info found on website"
                
            # Look for LinkedIn links
            linkedin = soup.find('a', href=lambda x: x and 'linkedin.com' in x)
            if linkedin:
                return f"LinkedIn: {linkedin['href']}"
                
            return ""
        except:
            return ""