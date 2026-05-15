import re
import json
from typing import List, Dict, Set, Tuple
from dataclasses import asdict
from .maps_scraper import BusinessLead


class DataCleaner:
    """
    Cleans, validates, deduplicates, and enriches scraped business leads.
    """
    
    # Common fake/test domains to filter out
    FAKE_DOMAINS = {
        'example.com', 'test.com', 'sample.com', 'domain.com',
        'email.com', 'mail.com', 'yourdomain.com', 'company.com'
    }
    
    # Common invalid phone patterns
    INVALID_PHONES = {
        '0000000000', '1234567890', '9876543210', '1111111111',
        '9999999999', '000000000', '123456789'
    }
    
    def __init__(self):
        self.removed_count = 0
        self.duplicate_count = 0
        self.cleaned_count = 0
        
    def clean_phone(self, phone: str) -> str:
        """
        Standardize phone number format for India.
        Removes non-numeric chars, adds +91 if needed.
        """
        if not phone:
            return ""
            
        # Remove all non-numeric characters
        digits = re.sub(r'\D', '', phone)
        
        # Skip invalid patterns
        if digits in self.INVALID_PHONES or len(digits) < 10:
            return ""
            
        # Handle Indian numbers
        if len(digits) == 10:
            return f"+91 {digits[:5]} {digits[5:]}"
        elif len(digits) == 12 and digits.startswith('91'):
            return f"+91 {digits[2:7]} {digits[7:]}"
        elif len(digits) == 11 and digits.startswith('0'):
            return f"+91 {digits[1:6]} {digits[6:]}"
            
        return phone  # Return original if can't parse
    
    def clean_email(self, email: str) -> str:
        """
        Validate and clean email addresses.
        """
        if not email:
            return ""
            
        email = email.strip().lower()
        
        # Basic regex validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return ""
            
        # Check for fake domains
        domain = email.split('@')[1]
        if domain in self.FAKE_DOMAINS:
            return ""
            
        # Filter common no-reply addresses
        if any(x in email for x in ['noreply', 'no-reply', 'donotreply', 'info@', 'admin@']):
            # Keep them but mark - actually keep for business context
            pass
            
        return email
    
    def clean_business_name(self, name: str) -> str:
        """
        Clean business names - remove extra whitespace, common suffixes.
        """
        if not name:
            return ""
            
        # Remove extra whitespace
        name = ' '.join(name.split())
        
        # Remove common Google Maps artifacts
        artifacts = ['·', '⋅', '•', '▪', '—', '–']
        for art in artifacts:
            name = name.replace(art, '')
            
        # Clean up common suffixes that clutter names
        suffixes = [' - Google Search', ' Maps', ' | ', ' · ']
        for suffix in suffixes:
            if suffix in name:
                name = name.split(suffix)[0]
                
        return name.strip()
    
    def clean_address(self, address: str, city: str, zone: str) -> str:
        """
        Standardize address format, ensure city/zone are included.
        """
        if not address:
            return ""

        address = address.strip()

        # Strip "Address:" prefix that Google Maps aria-label adds
        address = re.sub(r'^Address[:\s]+', '', address, flags=re.IGNORECASE).strip()

        # Remove "Open now" or "Closed" artifacts
        status_indicators = ['Open now', 'Closed', 'Closes soon', 'Opens soon', '24 hours']
        for indicator in status_indicators:
            if indicator in address:
                # These usually appear at the end
                parts = address.split(indicator)
                address = parts[0].strip()
                
        # Ensure city is in address
        if city and city.lower() not in address.lower():
            address = f"{address}, {city}"
            
        return address
    
    def deduplicate(self, leads: List[BusinessLead]) -> List[BusinessLead]:
        """
        Remove duplicate leads based on business name + address combination.
        Keeps the lead with the most complete data.
        """
        seen: Dict[str, BusinessLead] = {}
        duplicates = 0
        
        for lead in leads:
            # Create deduplication key
            name_clean = self.clean_business_name(lead.business_name).lower()
            addr_clean = (lead.address or "").lower().replace(" ", "")
            
            # Fuzzy match key
            key = f"{name_clean}|{addr_clean[:30]}"
            
            if key in seen:
                duplicates += 1
                existing = seen[key]
                
                # Keep the one with more complete data
                existing_score = sum([
                    bool(existing.phone), bool(existing.email),
                    bool(existing.website), bool(existing.rating)
                ])
                new_score = sum([
                    bool(lead.phone), bool(lead.email),
                    bool(lead.website), bool(lead.rating)
                ])
                
                if new_score > existing_score:
                    seen[key] = lead
            else:
                seen[key] = lead
                
        self.duplicate_count = duplicates
        return list(seen.values())
    
    def validate_lead(self, lead: BusinessLead) -> Tuple[bool, str]:
        """
        Validate if a lead has minimum required data.
        Returns (is_valid, reason).
        """
        if not lead.business_name or len(lead.business_name) < 2:
            return False, "Missing or invalid business name"

        # Keep any lead that has at least one useful piece of data beyond name.
        # Many small Indian businesses on Maps have address/rating but no website.
        has_contact = bool(lead.phone) or bool(lead.email) or bool(lead.website)
        has_location = bool(lead.address) or bool(lead.latitude)
        has_rating = bool(lead.rating)

        if not (has_contact or has_location or has_rating):
            return False, "No useful data beyond business name"

        return True, "Valid"
    
    def clean_single_lead(self, lead: BusinessLead) -> BusinessLead:
        """
        Apply all cleaning operations to a single lead.
        """
        lead.business_name = self.clean_business_name(lead.business_name)
        lead.phone = self.clean_phone(lead.phone)
        lead.email = self.clean_email(lead.email)
        lead.address = self.clean_address(lead.address, lead.city, lead.zone)
        
        # Clean rating - extract just the number
        if lead.rating:
            rating_match = re.search(r'(\d+\.?\d*)', str(lead.rating))
            if rating_match:
                lead.rating = rating_match.group(1)
                
        # Clean review count - extract just the number
        if lead.review_count:
            review_match = re.search(r'(\d+)', str(lead.review_count).replace(',', ''))
            if review_match:
                lead.review_count = review_match.group(1)
                
        self.cleaned_count += 1
        return lead
    
    def clean_all(self, leads: List[BusinessLead]) -> List[BusinessLead]:
        """
        Full pipeline: clean, validate, deduplicate.
        """
        print(f"\n{'='*50}")
        print("🧹 DATA CLEANING PIPELINE")
        print(f"{'='*50}")
        print(f"  Input leads: {len(leads)}")
        
        # Step 1: Clean individual leads
        cleaned = []
        invalid_count = 0
        invalid_reasons: Dict[str, int] = {}
        
        for lead in leads:
            cleaned_lead = self.clean_single_lead(lead)
            is_valid, reason = self.validate_lead(cleaned_lead)
            
            if is_valid:
                cleaned.append(cleaned_lead)
            else:
                invalid_count += 1
                invalid_reasons[reason] = invalid_reasons.get(reason, 0) + 1
                
        print(f"  After cleaning: {len(cleaned)}")
        print(f"  Invalid removed: {invalid_count}")
        for reason, count in invalid_reasons.items():
            print(f"    - {reason}: {count}")
            
        # Step 2: Deduplicate
        deduplicated = self.deduplicate(cleaned)
        print(f"  After deduplication: {len(deduplicated)}")
        print(f"  Duplicates removed: {self.duplicate_count}")
        
        # Step 3: Sort by rating (highest first)
        def sort_key(lead):
            try:
                return float(lead.rating or 0)
            except:
                return 0
                
        deduplicated.sort(key=sort_key, reverse=True)
        
        self.removed_count = len(leads) - len(deduplicated)
        print(f"\n✅ Final clean dataset: {len(deduplicated)} leads")
        print(f"   (Removed {self.removed_count} total)")
        
        return deduplicated
    
    def get_stats(self) -> Dict:
        """
        Return cleaning statistics.
        """
        return {
            'cleaned_count': self.cleaned_count,
            'duplicate_count': self.duplicate_count,
            'removed_count': self.removed_count,
            'final_count': self.cleaned_count - self.removed_count
        }
    
    def export_json(self, leads: List[BusinessLead], filepath: str):
        """
        Export leads to JSON for backup/debugging.
        """
        data = [asdict(lead) for lead in leads]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  💾 JSON backup saved: {filepath}")