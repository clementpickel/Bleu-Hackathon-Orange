"""Normalize model names, version strings, and dates"""
import re
from datetime import datetime
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class Normalizer:
    """Normalize extracted data for consistency"""
    
    # Common vendor name mappings
    VENDOR_ALIASES = {
        "cisco": ["cisco systems", "cisco inc"],
        "vmware": ["vmware inc", "vmware, inc"],
        "aruba": ["aruba networks", "hpe aruba"],
        "juniper": ["juniper networks"],
        "fortinet": ["fortinet inc"],
    }
    
    def normalize_vendor_name(self, vendor: Optional[str]) -> Optional[str]:
        """Normalize vendor names to canonical form"""
        if not vendor:
            return None
        
        vendor_lower = vendor.lower().strip()
        
        # Check aliases
        for canonical, aliases in self.VENDOR_ALIASES.items():
            if vendor_lower == canonical or vendor_lower in aliases:
                return canonical.title()
        
        # Return title case
        return vendor.strip().title()
    
    def normalize_model_name(self, model: Optional[str]) -> Optional[str]:
        """Normalize model names"""
        if not model:
            return None
        
        # Remove extra whitespace
        model = re.sub(r'\s+', ' ', model.strip())
        
        # Uppercase common patterns
        model = re.sub(r'\b(eg|vco|sd-wan|vpn)\b', lambda m: m.group(1).upper(), model, flags=re.IGNORECASE)
        
        return model
    
    def normalize_version_string(self, version: Optional[str]) -> Optional[str]:
        """
        Normalize version string to semantic version format.
        
        Examples:
            "v4.2.1" -> "4.2.1"
            "4.2" -> "4.2.0"
            "Release 5.0.1" -> "5.0.1"
        """
        if not version:
            return None
        
        version = version.strip()
        
        # Remove common prefixes
        version = re.sub(r'^(v|ver|version|release|r)\s*', '', version, flags=re.IGNORECASE)
        
        # Extract semantic version pattern
        match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?(?:\.(\d+))?', version)
        if match:
            major, minor, patch, build = match.groups()
            
            # Build semantic version
            parts = [major, minor]
            if patch:
                parts.append(patch)
            else:
                parts.append('0')
            
            if build:
                parts.append(build)
            
            return '.'.join(parts)
        
        # If no match, return original
        return version
    
    def parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parse various date formats and return ISO format (YYYY-MM-DD).
        
        Supports:
            - ISO: 2024-06-30
            - US: 06/30/2024
            - EU: 30/06/2024
            - Month-Year: June 2024, Jun 2024
            - Full: June 30, 2024
        """
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # Already ISO format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        
        # Try various formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%B %Y',
            '%b %Y',
            '%Y-%m',
            '%m-%Y',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # Try to extract year-month at least
        match = re.search(r'(\d{4})', date_str)
        if match:
            year = match.group(1)
            # Try to find month
            month_match = re.search(r'\b(0?[1-9]|1[0-2])\b', date_str)
            if month_match:
                month = month_match.group(1).zfill(2)
                return f"{year}-{month}-01"
            return f"{year}-01-01"
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def normalize_eol_status(self, status: Optional[str]) -> str:
        """Normalize EOL status to standard values"""
        if not status:
            return "UNKNOWN"
        
        status_lower = status.lower().strip()
        
        if status_lower in ["eol", "end of life", "deprecated", "discontinued", "unsupported"]:
            return "EOL"
        elif status_lower in ["supported", "active", "current", "maintained"]:
            return "SUPPORTED"
        else:
            return "UNKNOWN"
    
    def compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two version strings.
        
        Returns:
            -1 if v1 < v2
             0 if v1 == v2
             1 if v1 > v2
        """
        def version_tuple(v: str) -> Tuple:
            """Convert version string to tuple of integers"""
            parts = re.findall(r'\d+', v)
            return tuple(int(p) for p in parts)
        
        try:
            t1 = version_tuple(v1)
            t2 = version_tuple(v2)
            
            if t1 < t2:
                return -1
            elif t1 > t2:
                return 1
            else:
                return 0
        except Exception as e:
            logger.warning(f"Version comparison failed for {v1} vs {v2}: {e}")
            return 0
