import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from agent.platforms.twitter.modes.social.reply_generator import SocialReplyGenerator
from agent.core.interaction_intelligence import ResponseType

class TestSocialReplyReviewer(unittest.TestCase):
    def setUp(self):
        self.persona_config = MagicMock()
        self.persona_config.name = 'Chef Choi'
        self.persona_config.speech_style = {'tone': 'warm'}
        self.persona_config.get.side_effect = lambda k, d=None: {'name': 'Chef Choi'}.get(k, d)
        
        self.generator = SocialReplyGenerator(self.persona_config)

    @patch('agent.platforms.twitter.modes.social.reply_generator.llm_client')
    @patch('agent.platforms.twitter.modes.social.reviewer.llm_client')
    def test_review_integration(self, mock_reviewer_llm, mock_gen_llm):
        # 1. Generator Draft Mock
        mock_gen_llm.generate.return_value = "I love cooking too!"

        # 2. Reviewer Mock (Refines English to Korean)
        review_response = {
            "is_good": False,
            "issue": "Language check",
            "refined_text": "저도 요리를 정말 좋아합니다. 특히 조림 요리는... 참 매력적이죠."
        }
        mock_reviewer_llm.generate.return_value = json.dumps(review_response)

        # 3. Call generate
        target_tweet = {'user': 'fan', 'text': 'Cooking is fun!'}
        perception = {'response_type': ResponseType.SHORT}
        context = {}
        
        result = self.generator.generate(target_tweet, perception, context)

        # 4. Verify
        print(f"Draft: 'I love cooking too!'")
        print(f"Refined: '{result}'")
        
        self.assertEqual(result, "저도 요리를 정말 좋아합니다. 특히 조림 요리는... 참 매력적이죠.")
        # Ensure reviewer was called
        mock_reviewer_llm.generate.assert_called()

    @patch('agent.platforms.twitter.modes.social.reply_generator.llm_client')
    def test_diversity_check(self, mock_gen_llm):
        """Test that diversity logic rejects repetitive content"""
        # Scenario: "Delicious!" is recently used, generator tries to use "Delicious!" again
        
        # 1. Mock Analysis of recent posts (found repetition)
        self.generator._analyze_recent_posts = MagicMock(return_value={
            'topics': ['Delicious'], 
            'expressions': ['Delicious']
        })
        
        # 2. Mock Generator (fails diversity first, then succeeds)
        # First attempt: "Delicious!" (Banned)
        # Second attempt: "It's tasty!" (OK)
        # Note: In real logic, it would print [DIVERSITY] and retry.
        # We need to simulate _validate_and_regenerate loop.
        mock_gen_llm.generate.side_effect = ["Delicious!", "It's tasty!"]
        
        # 3. Call generate with recent replies
        target_tweet = {'user': 'fan', 'text': 'Food looks good'}
        perception = {'response_type': ResponseType.SHORT}
        recent_replies = ["Delicious!"]
        
        # We need to mock reviewer too or ensure it passes "It's tasty!"
        self.generator.reviewer.review_reply = MagicMock(side_effect=lambda t, d: d)
        
        # We also need to mock formatter to pass constraints
        self.generator.formatter.apply_constraints = lambda x: x
        self.generator.formatter.check_forbidden = lambda x: None

        result = self.generator.generate(target_tweet, perception, {}, recent_replies=recent_replies)
        
        print(f"Generated diverse reply: {result}")
        self.assertEqual(result, "It's tasty!")


if __name__ == '__main__':
    unittest.main()
