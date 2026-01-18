import sys
import os

# Add project root to path
sys.path.append(os.getcwd())
print(f"[Debug] Python: {sys.executable}")
# print(f"[Debug] Path: {sys.path}")

from agent.persona.persona_loader import PersonaLoader
from agent.platforms.twitter.modes.series.engine import SeriesEngine

def mock_publish(content, images, series_config):
    print("\n" + "=" * 50)
    print(" [MOCK PUBLISH] FINAL OUTPUT TO PLATFORM")
    print("=" * 50)
    print(f"SERIES  : {series_config['name']}")
    print(f"TOPIC   : {content.splitlines()[0] if content else 'N/A'}")
    print(f"IMAGES  : {images}")
    print("-" * 50)
    sys.stderr.write("FINAL CONTENT:\n")
    sys.stderr.write(content + "\n")
    print("=" * 50 + "\n")
    sys.stdout.flush()
    sys.stderr.flush()
    return "mock_tweet_id_123"

def main():
    print("[Test] Loading Persona 'chef_choi'...")
    # Load Persona
    loader = PersonaLoader()
    persona = loader.load_persona("chef_choi")
    print(f"[Test] Loaded: {persona.name}")
    
    # Initialize Engine
    engine = SeriesEngine(persona)
    
    # Inject Mock Adapter
    class MockAdapter:
        def publish(self, content, images, series_config):
            return mock_publish(content, images, series_config)
            
    engine.adapters['twitter'] = MockAdapter()
    
    # Inject Mock Planner to ensure topic is available
    class MockPlanner:
        def plan_next_episode(self, platform, series_config):
            return {
                'topic': '묵은지 김치찜',
                'angle': 'Tradition'
            }
        def get_last_used_at(self, platform, series):
            return None
            
    engine.planner = MockPlanner()
    
    # Define Series Config manually to inspect specific series
    series_config = {
        'id': 'world_braised',
        'name': '세계의 조림',
        'description': 'Test Description',
        'frequency': '1d',
        'time_variance': '1h'
    }
    
    print("[Test] Executing Series: 세계의 조림 (world_braised)")
    try:
        engine.execute_specific_series('twitter', series_config)
    except Exception as e:
        print(f"[Test] Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
