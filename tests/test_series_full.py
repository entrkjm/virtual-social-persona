"""
Test Signature Series Pipeline
기획 -> 생성 -> 이미지 -> 비평 -> 게시 전체 테스트
"""
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from agent.persona.persona_loader import PersonaLoader
from agent.series.engine import SeriesEngine
from config.settings import settings

def test_series():
    print("=== Test Start: Signature Series System ===")
    
    # 1. Load Persona
    print("1. Loading Persona 'chef_choi'...")
    loader = PersonaLoader()
    persona = loader.load_persona("chef_choi")
    
    # 2. Init Engine
    print("2. Initializing SeriesEngine...")
    engine = SeriesEngine(persona)
    
    # 3. Select Target Series (World Braised)
    twitter_config = persona.signature_series.get('twitter')
    if not twitter_config:
        print("Error: No twitter config found")
        return

    target_series = twitter_config['series'][0] # world_braised
    print(f"3. Target Series: {target_series['name']} ({target_series['id']})")
    
    # 4. Execute
    print("4. Executing Pipeline...")
    try:
        # execute_specific_series will handles:
        # Planner (Curation) -> Writer -> Generator -> Critic -> Adapter
        result = engine.execute_specific_series('twitter', target_series)
        
        if result:
            print(f"\n✅ SUCCESS! Tweet Posted.")
            print(f"Tweet ID: {result.get('id')}")
            print(f"URL: https://twitter.com/user/status/{result.get('id')}")
        else:
            print("\n❌ FAILED. No result returned.")
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_series()
