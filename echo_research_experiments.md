# Computational Sociology Simulations with ECHO

Based on the latest 2024 and 2025 research papers in LLM-powered computational sociology, generative agents, and opinion dynamics, here are three highly rigorous, academically relevant simulations you can run right now in the ECHO Sandbox.

***

## 1. The Algorithmic Nudge Experiment
**Inspired by:** *"Decoding Echo Chambers: LLM-Powered Simulations Revealing Polarization in Social Networks" (Wang et al., 2025)*

**The Hypothesis:** This paper tests whether "bridging" algorithms (which expose users to moderate, out-group opinions) can effectively reduce polarization compared to organic, engagement-driven feeds.

**How to run it in ECHO:**
1. **Setup:** Set the Topology to **Small World** and Belief Distribution to **Bimodal (Polarized Extremes)**. Set Political Weight to a high value (0.8).
2. **Control Run:** Leave `Alg Feed: OFF`. Click Play and let it run for 30 ticks. Observe the **Polarization Over Time** chart (the standard deviation will likely stay high or increase) and the **Belief Spectrum Histogram**.
3. **Experimental Run:** Hit Reset. Now, turn `Alg Feed: ON` (if implemented, or simulate by injecting moderate narratives of Bias `0.0` repeatedly). 
4. **Insight Generated:** You can map the exact rate of polarization decay (the curve on the chart) when bridging narratives are introduced versus when the echo chamber is left to its own devices.

## 2. Persona-Driven Polarization vs. Structural Influence
**Inspired by:** *"Polarization of Autonomous Generative AI Agents Under Echo Chambers" (Ohagi, 2024)*

**The Hypothesis:** Ohagi's research explores whether LLM agents polarize simply because of their programmed "Confirmation Bias" (their personas), or if the *structure* of the network is the primary driver of echo chambers.

**How to run it in ECHO:**
1. **Setup A (Structural Isolation):** Use the **Stochastic Block Model** with 4 blocks and extremely low out-block probability (`p_out: 0.01`). 
2. **Setup B (Hyper-Connected):** Use the **Scale-Free** network.
3. **Execution:** For both setups, use the exact same **Seeding Payload** in the Inspector Panel (e.g., inject a neutral narrative: *"I think the new tax policy has both pros and cons."*).
4. **Insight Generated:** Compare the "Mutated Narratives Log" between the two setups. Do the Scale-Free hubs successfully keep the conversation moderate, or do the Mega-Influencers still twist the narrative into polarized extremes just because their internal stubbornness requires it?

## 3. Bot-Farm Contagion and Network Fracture
**Inspired by:** *"Understanding Online Polarization Through Human-Agent Interaction in a Synthetic LLM-Based Social Network" (Donkers & Ziegler, 2025)*

**The Hypothesis:** This research looks at how synthetic emotionality and hostile actors (bots) force mass migration and the fracturing of group identity.

**How to run it in ECHO:**
1. **Setup:** Use a **Uniform Distribution** of beliefs (a generally peaceful, neutral society).
2. **The Injection:** In the Simulation Controls, set **Bot Farm Injection** to `15%`. 
3. **Execution:** Hit Play. The bots will continuously flood the network with maximum-extremism payloads (Belief `-1.0` or `1.0`).
4. **Insight Generated:** Watch the `Edges Severed` counter. You are measuring the **"Fracture Threshold."** How many ticks does it take for 15% bots to cause a mass Arousal Entropy Shock and force the organic users to sever their ties? You can plot this mathematically to find the tipping point where a network becomes "dead" due to bot flooding.

***

> [!TIP]
> **Pro-Tip:** If you export the data after running these simulations, you will have the raw matrices (Adj Matrices and Agent States) to generate exactly the kind of heatmaps and line graphs you see in these published papers!
