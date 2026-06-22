import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server import app

client = TestClient(app)

def test_initialize_endpoint():
    print("\nTesting /api/initialize endpoint...")
    response = client.post(
        "/api/initialize",
        json={"n_agents": 50, "topology": "small_world"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["agents"]) == 50
    assert "telemetry" in data
    print(">> PASSED: Initialize endpoint successfully created the graph.")

def test_step_endpoint():
    print("\nTesting /api/step endpoint...")
    # First initialize
    client.post("/api/initialize", json={"n_agents": 20})
    
    # Then step
    response = client.post("/api/step")
    assert response.status_code == 200
    data = response.json()
    assert "tick" in data
    assert "polarization" in data
    assert data["tick"] == 1
    print(">> PASSED: Step endpoint successfully advanced the simulation.")

def test_step_without_initialization():
    print("\nTesting /api/step error handling...")
    # Reset state implicitly by restarting client (not perfectly isolated but works for testing error string)
    # Actually, we need to manually clear the server state if we want to test uninitialized
    import server
    server.engine = None
    
    response = client.post("/api/step")
    assert response.status_code == 400
    data = response.json()
    assert "Simulation not initialized" in data["detail"]
    print(">> PASSED: Step endpoint correctly caught uninitialized state.")

if __name__ == "__main__":
    test_initialize_endpoint()
    test_step_endpoint()
    test_step_without_initialization()
