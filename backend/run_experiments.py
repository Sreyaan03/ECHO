import os
import csv
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict

from opinion_engine.opinion_engine import OpinionEngine, Topology, TopologyParams

def run_experiment(
    parameter_name: str,
    parameter_values: List[float],
    n_trials: int = 3,
    ticks_per_trial: int = 50,
    n_agents: int = 300
) -> Dict[float, List[float]]:
    """
    Runs a parameter sweep experiment on the OpinionEngine.
    Returns a dict mapping parameter values to a list of final polarization scores for each trial.
    """
    print(f"Starting experiment: Sweeping '{parameter_name}' over {parameter_values}")
    print(f"Trials per value: {n_trials} | Ticks per trial: {ticks_per_trial} | Agents: {n_agents}")
    
    results = {}
    
    for val in parameter_values:
        print(f"\n--- Testing {parameter_name} = {val:.2f} ---")
        trial_scores = []
        
        for trial in range(n_trials):
            # Base parameters
            kwargs = {
                "n_agents": n_agents,
                "topology": Topology.SCALE_FREE,
                "w_pol": 0.4,
                "w_econ": 0.3,
                "w_rel": 0.3,
                "d_tolerance": 0.5,
                "gamma": 0.1,
                "fatigue_limit": 5,
                "p_fact_checkers": 0.05,
                "seed": 42 + trial  # Different seed per trial
            }
            
            # Override the sweep parameter
            kwargs[parameter_name] = val
            
            engine = OpinionEngine(**kwargs)
            
            # Run simulation
            for _ in range(ticks_per_trial):
                engine.step()
                
            final_polarization = engine.get_telemetry()["polarization"]
            trial_scores.append(final_polarization)
            print(f"  Trial {trial+1}: Polarization = {final_polarization:.3f}")
            
        results[val] = trial_scores
        
    return results

def save_results(results: Dict[float, List[float]], param_name: str):
    """Saves results to CSV and generates a Matplotlib graph."""
    os.makedirs("../docs", exist_ok=True)
    
    # 1. Save CSV
    csv_path = f"../docs/experiment_{param_name}_results.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([param_name, "Trial 1", "Trial 2", "Trial 3", "Mean Polarization"])
        for val, scores in results.items():
            mean_score = np.mean(scores)
            writer.writerow([val] + scores + [mean_score])
    print(f"\nData saved to {csv_path}")
    
    # 2. Generate Plot
    plt.figure(figsize=(10, 6))
    
    x_vals = []
    y_means = []
    y_stds = []
    
    for val, scores in results.items():
        x_vals.append(val)
        y_means.append(np.mean(scores))
        y_stds.append(np.std(scores))
        
    # Plot line with error bands
    plt.plot(x_vals, y_means, 'b-', marker='o', label='Mean Polarization')
    plt.fill_between(x_vals, 
                     np.array(y_means) - np.array(y_stds), 
                     np.array(y_means) + np.array(y_stds), 
                     color='b', alpha=0.2, label='Std Dev')
    
    plt.title(f"Impact of {param_name} on Network Polarization", fontsize=14)
    plt.xlabel(param_name, fontsize=12)
    plt.ylabel("Final Polarization (Std Dev of Beliefs)", fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()
    
    # Save Plot
    plot_path = f"../docs/experiment_{param_name}_plot.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"Plot saved to {plot_path}")

if __name__ == "__main__":
    # Example Experiment: Test the effectiveness of Fact-Checkers
    # Varying fact-checker density from 0% to 20%
    sweep_values = [0.0, 0.05, 0.10, 0.15, 0.20]
    
    # Run the sweep
    experiment_results = run_experiment(
        parameter_name="p_fact_checkers",
        parameter_values=sweep_values,
        n_trials=3,
        ticks_per_trial=40,
        n_agents=200
    )
    
    # Save output
    save_results(experiment_results, param_name="p_fact_checkers")
    print("Experiment suite completed.")
