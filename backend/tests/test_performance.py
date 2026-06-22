import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from opinion_engine.opinion_engine import OpinionEngine, Topology

def test_engine_performance_limits():
    """
    Load test: Ensure that a large graph (N=5000) does not time out and completes within a reasonable threshold.
    Note: N=5000 is used instead of 10000 so the test runs reasonably fast locally during development,
    but still proves vectorized efficiency.
    """
    print("\nStarting Performance Limit Test (N=5000)...")
    start = time.time()
    
    engine = OpinionEngine(n_agents=5000, topology=Topology.SMALL_WORLD, seed=42)
    engine.step()
    
    duration = time.time() - start
    print(f"Time taken for N=5000 tick: {duration:.3f}s")
    
    # Assert that a tick on a 5000 node graph takes less than 3 seconds
    assert duration < 3.0, f"Performance test failed! Took {duration:.3f}s"
    print(">> PASSED: Engine performance limits are acceptable.")

def test_zero_gravity():
    """
    Edge case: If all nodes have identical beliefs and 0% arousal, the network should stay static.
    """
    print("\nStarting 'Zero Gravity' Edge Case Test...")
    engine = OpinionEngine(n_agents=100, seed=42)
    
    # Set all agents to have identical beliefs, low arousal, high literacy
    for i in range(100):
        engine._agents[i, 3] = 0.5  # Belief
        engine._agents[i, 5] = 0.0  # Arousal
        engine._agents[i, 6] = 1.0  # Literacy
        
    engine.step()
    
    # Polarization should be extremely close to 0
    telemetry = engine.get_telemetry()
    assert telemetry["polarization"] < 0.01, f"Expected 0 polarization, got {telemetry['polarization']}"
    print(">> PASSED: Zero Gravity test completed.")

if __name__ == "__main__":
    test_engine_performance_limits()
    test_zero_gravity()
