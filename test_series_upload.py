import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.getcwd())
print(f"[Debug] Python: {sys.executable}")

print("Importing PersonaLoader...", flush=True)
from agent.persona.persona_loader import PersonaLoader
print("Importing SeriesEngine...", flush=True)
from agent.platforms.twitter.modes.series.engine import SeriesEngine
print("Importing Series TwitterAdapter...", flush=True)
from agent.platforms.twitter.modes.series.adapters.twitter import TwitterAdapter
print("Imports done.", flush=True)

async def run_test():
    pass # placeholder to remove async

def run_test():
    print("[Test] Starting...", flush=True)
    print("[Test] Loading Persona 'chef_choi'...", flush=True)
    # Load Persona
    loader = PersonaLoader()
    persona = loader.load_persona("chef_choi")
    print(f"[Test] Loaded: {persona.name}", flush=True)
    
    # Initialize Engine
    print("[Test] Initializing Engine...", flush=True)
    engine = SeriesEngine(persona)
    
    # Initialize REAL Series Adapter (No args needed likely)
    adapter = TwitterAdapter()
    
    # Inject Real Adapter
    engine.adapters['twitter'] = adapter
    
    # Inject Mock Planner to set topic (optional, or let it decide)
    class MockPlanner:
        def plan_next_episode(self, platform, series_config):
            return {
                'topic': '묵은지 김치찜',
                'angle': 'Tradition'
            }
        def get_last_used_at(self, platform, series):
            return None
            
    engine.planner = MockPlanner()
    
    # Define Series Config manually
    series_config = {
        'id': 'world_braised',
        'name': '세계의 조림',
        'description': '한국의 맛을 담은 조림 요리 소개',
        'frequency': '1d',
        'time_variance': '1h'
    }
    
    print("[Test] Executing Series Upload: 세계의 조림 (world_braised)")
    try:
        # execute_specific_series is synchronous in current impl? 
        # Checking engine.py... yes it seems synchronous or internally handles it?
        # Actually adapter.publish is async? Let's check adapter.
        # Adapter methods are often async. But engine might call them differently.
        # Let's assume engine.execute_specific_series calls adapter.publish.
        # If adapter.publish is async, engine needs to await it. 
        # But looking at previous code, engine seems synchronous.
        # Retry with synchronous call first.
        engine.execute_specific_series('twitter', series_config)
        print("[Test] DONE - Check Twitter!")
    except Exception as e:
        print(f"[Test] Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
