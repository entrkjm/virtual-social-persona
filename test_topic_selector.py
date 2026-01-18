import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from agent.core.topic_selector import TopicSelector

def test_topic_selector():
    print("Testing TopicSelector...")
    selector = TopicSelector()
    
    # Mock keywords
    core_kw = ["kimchi", "bulgogi"]
    time_kw = ["breakfast", "soup"]
    curiosity = ["fusion", "spicy"]
    trends = ["trend1", "trend2"]
    
    print("\n[Input Keywords]")
    print(f"Core: {core_kw}")
    print(f"Time: {time_kw}")
    
    # Test 1: Selection
    print("\n[Test 1] Running Selection...")
    try:
        query, source = selector.select(
            core_keywords=core_kw,
            time_keywords=time_kw,
            curiosity_keywords=curiosity,
            trend_keywords=trends
        )
        print(f"Selected Source: {source}")
        print(f"Enhanced Query: {query}")
        
        # Verify structure
        if "OR" in query and "-filter" in query:
            print("✅ Query structure is VALID.")
        else:
            print("❌ Query structure is INVALID.")
            
    except Exception as e:
        print(f"❌ Selection failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Randomness & Cooldown
    print("\n[Test 2] Running 5 iterations...")
    for i in range(5):
        q, s = selector.select(core_kw, time_kw, curiosity, trends)
        print(f"#{i+1}: [{s}] {q}")

if __name__ == "__main__":
    test_topic_selector()
