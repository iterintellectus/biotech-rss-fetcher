"""
Basic tests for the biotech-rss-notion package.
"""

import unittest
import os
import sys

# Add the src directory to the path so we can import our module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

class TestBasic(unittest.TestCase):
    """Basic tests for the package."""
    
    def test_imports(self):
        """Test that the module can be imported."""
        try:
            import rss_to_notion
            self.assertTrue(True)
        except ImportError:
            self.fail("Failed to import rss_to_notion")
    
    def test_module_constants(self):
        """Test that module constants are defined."""
        import rss_to_notion
        self.assertTrue(hasattr(rss_to_notion, 'RSS_FEEDS'), 
                        "RSS_FEEDS constant not defined in module")

if __name__ == '__main__':
    unittest.main() 