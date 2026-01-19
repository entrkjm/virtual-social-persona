import unittest
from unittest.mock import MagicMock, patch
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from agent.platforms.twitter.modes.series.adapters.twitter import TwitterAdapter

class TestSeriesConstraints(unittest.TestCase):
    def setUp(self):
        self.adapter = TwitterAdapter()
        # Mock print to keep test output clean
        self.adapter.MAX_LENGTH = 100 # Smaller length for easy testing
        self.adapter.MAX_THREAD_LENGTH = 3

    def test_thread_splitting_and_truncation(self):
        """Test that content is split into threads and truncated if too long"""
        # Create content that would require 5 chunks of 100 chars
        long_content = "A" * 90 + "\n" + "B" * 90 + "\n" + "C" * 90 + "\n" + "D" * 90 + "\n" + "E" * 90
        
        chunks = self.adapter._split_content(long_content)
        
        # Should be truncated to MAX_THREAD_LENGTH (3)
        self.assertEqual(len(chunks), 3, "Should be truncated to 3 tweets")
        
        # Verify content of chunks
        self.assertTrue("A" * 90 in chunks[0])
        self.assertTrue("C" * 90 in chunks[2])
        # D and E should be missing
        self.assertFalse("D" * 90 in "".join(chunks))

    def test_korean_language_check(self):
        """Simple check to verify string contains Korean characters"""
        def is_korean(text):
            korean_count = 0
            for char in text:
                if '\uac00' <= char <= '\ud7a3': # Hangul Syllables
                    korean_count += 1
            return korean_count > 0

        korean_text = "안녕하세요. 이것은 테스트입니다."
        english_text = "Hello, this is a test."
        
        self.assertTrue(is_korean(korean_text), "Should detect Korean")
        self.assertFalse(is_korean(english_text), "Should not detect Korean in English text")

    def test_content_length_limit(self):
        """Verify content fits within overall constraints"""
        # Assuming 500 char limit (from prompt/style.yaml settings)
        # This acts as a validator function we could use in the engine
        
        valid_content = "적당한 길이의 한국어 텍스트입니다." * 10 
        invalid_content = "너무 긴 텍스트입니다." * 100
        
        self.assertTrue(len(valid_content) < 500, "Should be within limits")
        self.assertTrue(len(invalid_content) > 500, "Should detect violation")

if __name__ == '__main__':
    unittest.main()
