"""Pytest configuration"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def sample_pdf_text():
    """Sample PDF text for testing"""
    return """
    Release Notes for Acme EG-400 Gateway
    Version 4.2.1
    
    End of Life Notice
    
    Version 4.2.1 will reach end of life on June 30, 2024. This version
    will no longer receive security updates or technical support after this date.
    
    Recommended Action
    
    Users are strongly encouraged to upgrade to version 5.0.2, which is the
    current supported release. The upgrade path requires first installing
    intermediate version 4.3.5 as a mandatory step.
    
    Compatibility Information
    
    Version 4.2.1 is compatible with versions 4.2.0, 4.2.2, and 4.3.x series.
    Direct upgrade from 4.2.1 to 5.0.x is not supported without intermediate steps.
    
    For more information, contact technical support.
    """


@pytest.fixture
def sample_extraction_result():
    """Sample extraction result for testing"""
    return {
        'extracted_data': {
            'vendor': 'Acme',
            'product_family': 'Enterprise Gateway',
            'model': 'EG-400',
            'model_aliases': [],
            'software_version': '4.2.1',
            'eol_status': 'EOL',
            'eol_date': '2024-06-30',
            'replacement_models': [],
            'compatible_versions': ['4.2.0', '4.2.2', '4.3.5'],
            'upgrade_instructions': 'Upgrade to 5.0.2 via intermediate version 4.3.5',
            'notes': 'End of life notice',
            'source_chunk_id': 'test_chunk_1',
            'evidence': {
                'eol_date': ['June 30, 2024'],
                'software_version': ['4.2.1']
            }
        },
        'confidence': 0.85,
        'method': 'hybrid'
    }
