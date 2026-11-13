# MicroDuck CoPush: Cooperative Object Manipulation with Multi-Agent RL

**Team:** 3 CGAI (Cornell Generative AI) engineers  
**Timeline:** October 30 – December 11, 2026  
**Primary platform:** MuJoCo + Pollen Robotics MicroDuck  
**Project type:** Multi-agent robot learning, simulation, control, and evaluation

## Project Objective

Develop a simulation in which two MicroDucks cooperatively push a shared rectangular box toward a desired position and orientation.

Initially, both robots will use existing pretrained walking policies, controlled by a simple scripted coordinator. Once this baseline works, we will investigate training a higher-level reinforcement learning policy to coordinate the ducks.

The central question is:

**Can a learned cooperative controller position a shared object more accurately and reliably than independent or scripted robot controllers?**

### Minimum viable deliverable

Two simulated MicroDucks physically push one box at least 0.3 m without falling, with automated recording of object displacement and robot stability.

### Target semester deliverable

Two ducks move and align a box to a specified target, with a trained high-level RL controller and quantitative comparisons against scripted baselines.

### Stretch goal

The controller generalizes to different box masses, starting orientations, and target poses.


---

## 1. Existing Resources

### A. Single-Duck Box Pushing — Robert Policies

https://huggingface.co/pisdeburra/robert-policies

This project is our closest starting point.

It provides:

- Forward and backward PPO-trained pushing policies.
- ONNX models and training checkpoints.
- Box physics and reported training configurations.
- A reward emphasizing box movement together with the robot, while discouraging uncontrolled acceleration.
- Baseline experiments demonstrating that push-specific locomotion training can improve object transport.

The original setup uses a 28 × 10 × 9 cm box with randomized mass from 50–300 g.

**Our use:** Reproduce a single-duck pushing result, study its reward design, and investigate using its trained walking policy as a baseline.

Do not assume that its training setup will transfer directly to two ducks or a differently shaped box.

### B. MultiDuckComposer — MicroDuck Circus

https://github.com/ros-claw/microduck

Provides:

- Multiple MicroDuck bodies in the same MuJoCo physics world.
- Namespaced robot joints and actuators.
- Shared-object simulation with real collisions.
- Independent execution of pretrained ONNX policies.

**Our use:** Reuse or adapt the multi-robot composition infrastructure rather than reimplementing the robot model.

### C. Official MicroDuck RL

https://github.com/pollen-robotics/microduck_rl

https://github.com/pollen-robotics/microduck_rl/blob/develop/AGENTS.md

Provides:

- MuJoCo robot models.
- PPO training with `rsl_rl`.
- Walking observations and reward functions.
- Domain randomization.
- Checkpoint and ONNX policy workflows.

**Our use:** Keep locomotion policies frozen for the initial experiment and investigate a higher-level cooperative control policy.

### D. Official MicroDuck Simulator

https://github.com/pollen-robotics/microduck/blob/main/docs/robot/simulation.md

The simulator supports multiple ducks in the same physics world. We can initially use this to verify that both robots can be controlled independently.


---

## 2. Technical Architecture

Our system will have three layers.

**High-level cooperative controller**

Receives:

- Both robots' positions and orientations.
- The box's current position and orientation.
- The box's desired target pose.
- Optionally, recent velocities and contact information.

Produces individual movement commands:

$$
a_t=[v_{x,1},v_{y,1},\omega_1,v_{x,2},v_{y,2},\omega_2]
$$

**Low-level locomotion**

Each duck uses its existing pretrained walking policy to translate velocity commands into joint-level control.

**MuJoCo physics**

Simulates both robots, the box, floor contact, collisions, friction, and object movement.

### Initial control methodology

First, implement a centralized scripted controller. Later, replace it with a centralized PPO policy producing the six movement commands.

A centralized joint-action PPO policy is simpler to implement than fully decentralized multi-agent learning. We will consider shared policies with decentralized observations only after the centralized approach works.

The initial high-level controller will run around 5 Hz, while the existing low-level walking policies run at 50 Hz.

We must verify supported command ranges and runtime clamping before selecting action bounds.


---

## 3. Division of Work

| Engineer | Workstream | Primary responsibility |
|---|---|---|
| Person 1 | Physics and simulation | Build the two-duck shared-object environment |
| Person 2 | Control and RL | Develop coordination baselines and train the high-level policy |
| Person 3 | Evaluation and benchmarking | Design trials, collect metrics, analyze results, and produce demos |

### Person 1 — Simulation and Contact Physics

**Goal:** Create a reliable simulation in which two ducks can physically interact with one box.

Tasks:

1. Study `MultiDuckComposer` and the official scene files.
2. Spawn two ducks in one world.
3. Verify independent control of each duck.
4. Add a movable rectangular box with a free joint.
5. Configure reasonable box mass, dimensions, friction, and collision geometry.
6. Expose the ground-truth poses of both robots and the box.
7. Implement reproducible scene resets.
8. Verify the box moves only through genuine physical contact.

Deliverables:

- `copush_scene.xml`, or equivalent composed model.
- `simulation.py`
- `reset_scene()` and `get_state()`.
- A short video showing two ducks and a movable box.

**Definition of done:** Both ducks remain upright in the shared scene, commands affect the correct robot, and box displacement results from collision forces rather than scripted teleportation.

### Person 2 — Coordination and Reinforcement Learning

**Goal:** Learn how to command both ducks to cooperatively move the box.

Tasks:

1. Study the single-duck Shoe Push policy.
2. Implement an open-loop baseline where both ducks receive fixed commands.
3. Build a simple feedback controller that adjusts movement according to box position and orientation errors.
4. Define the high-level RL observation and action spaces.
5. Implement a reward based on object progress, orientation error, and stability.
6. Run a small PPO smoke test.
7. Train a coordinator once the scripted task is functional.
8. Evaluate whether learned coordination improves over the baselines.

Deliverables:

- `scripted_controller.py`
- `copush_env.py` or an mjlab task configuration.
- `rewards.py`
- First RL checkpoint and training curves.

**Definition of done:** The same scene can run with fixed commands, scripted feedback, or a learned controller.

### Person 3 — Evaluation and Visualization

**Goal:** Make performance measurable and comparable across experiments.

Tasks:

1. Define task-success and failure criteria.
2. Implement trial logging for both robots and the box.
3. Measure object position error, orientation error, displacement, and falls.
4. Define training and held-out test scenarios.
5. Create a reproducible evaluation runner.
6. Generate trajectory plots and baseline comparisons.
7. Record MuJoCo videos with the target pose marked visually.
8. Prepare the final technical report.

Deliverables:

- `evaluate.py`
- `metrics.py`
- `plot_results.py`
- Per-trial CSV results.
- Benchmark report and demo video.

**Definition of done:** Given a controller and a set of test scenarios, one command produces quantitative results and plots.

### Shared interface to agree on first

All three engineers should use the same state format:

```python
state = {
    "duck_a": {"position": ..., "yaw": ..., "velocity": ...},
    "duck_b": {"position": ..., "yaw": ..., "velocity": ...},
    "box": {"position": ..., "yaw": ..., "velocity": ...},
    "goal": {"position": ..., "yaw": ...},
}
```

And the same controller interface:

```python
actions = controller.get_actions(state)
```

Actions should contain separate velocity commands for duck A and duck B.

This allows the simulation, control, and evaluation components to be developed independently.


---

## 4. Weekly Milestones

### Week 1 — October 30 – November 5

**Goal: Get two ducks into one shared MuJoCo world.**

Person 1:

- Inspect the multi-duck simulator implementation.
- Run two independently controlled ducks.
- Begin adding box geometry.

Person 2:

- Reproduce the single-duck pushing behavior or run the released pushing ONNX policy.
- Understand the action and observation interfaces.
- Implement a simple dual-duck command sender.

Person 3:

- Define the initial experiment metrics.
- Build a CSV recorder and mock-data evaluation tests.
- Create the first plotting template.

**Checkpoint M1:** Two ducks in one shared world, independently controllable, with both remaining healthy for a 10-second test.

**Demo:** Short recording of both robots receiving different movement commands.

### Week 2 — November 6–12

**Goal: Make the robots physically push the box.**

Person 1:

- Complete box collisions and contact physics.
- Implement independent scene resets.
- Test box motion across a few masses and friction values.

Person 2:

- Implement fixed-command and scripted pushing baselines.
- Try different initial duck placements.
- Tune commands without changing RL policy weights.

Person 3:

- Test displacement and fall detection.
- Build the first box trajectory visualization.
- Record five to ten repeatable trials.

**Checkpoint M2:** The box moves at least 0.15 m due to a duck's physical contact.

**Checkpoint M3:** Two ducks jointly push the same box at least 0.30 m in at least one valid trial.

**Demo for Tapo:** Two ducks pushing a shared object, plus a plot showing measured box displacement.

These milestones establish feasibility; they do not yet demonstrate learned cooperation.

### Week 3 — November 13–19

**Goal: Build reliable scripted cooperative positioning.**

Person 1:

- Refine contact geometry to reduce unintended collisions.
- Add randomized initial box poses.
- Validate reproducible starting conditions.

Person 2:

- Implement a feedback controller for box position and heading.
- Coordinate unequal robot speeds to rotate the box.
- Add success-based stopping.

Person 3:

- Create 10–20 evaluation scenarios.
- Compare one-duck, identical-command, and scripted coordination baselines.
- Generate trajectory and error plots.

**Checkpoint M4:** Two ducks use feedback to move a box toward a position target.

**Checkpoint M5:** Demonstrate at least one successful combined translation-and-rotation maneuver.

This week should identify whether the task can be controlled well enough to justify RL training.

### Week 4 — November 20–26

**Goal: Implement the first RL environment.**

Person 1:

- Make the simulator compatible with repeated episodic training.
- Implement box and duck resets.
- Check whether the scene can support GPU-parallel training, or whether a smaller headless CPU environment is needed for prototyping.

Person 2:

- Define a centralized PPO action space.
- Implement observations and reward functions.
- Run a small training smoke test.

Person 3:

- Build automated evaluation across checkpoints.
- Validate the reward against obvious failure cases.
- Monitor for reward hacking, such as unnecessary box impacts or robots exploiting a fall state.

**Checkpoint M6:** PPO training initializes, episodes reset, metrics are recorded, and reward functions produce finite values.

No expectation of competent learned pushing yet.

### Week 5 — November 27 – December 3

**Goal: Train a working cooperative controller.**

Person 1:

- Debug physics or training-environment problems.
- Add limited box mass and friction variation if the fixed task works.

Person 2:

- Train the centralized coordinator on the simplest straight-pushing scenario.
- Progress to a small set of pose targets only after basic movement works.
- Save checkpoints and training configurations.

Person 3:

- Evaluate checkpoints against the scripted baseline.
- Record success rates, pose errors, and failure patterns.
- Identify which training modifications produce measurable changes.

**Checkpoint M7:** A trained RL policy causes meaningful box progress in held-out simulations without exploiting the reward.

**Stretch:** Learned policy reaches a target pose in a meaningful fraction of test trials.

### Week 6 — December 4–10

**Goal: Finish a reproducible comparison and demonstration.**

Person 1:

- Clean the simulation setup.
- Document installation and reproducibility.
- Pin dependencies and model versions.

Person 2:

- Select the best checkpoint.
- Run final comparisons.
- Document the learning objective and training decisions.

Person 3:

- Run final held-out benchmarks.
- Generate plots and a polished demonstration video.
- Write the experimental findings and limitations.

**Checkpoint M8:** A documented benchmark compares at least three controller types under the same test conditions.

**Final deliverables:**

- Source code repository.
- Two-duck MuJoCo simulation.
- Scripted coordination baseline.
- RL task and checkpoint, if training succeeds.
- Reproducible evaluation scripts.
- Results plots.
- Final technical report and short demo video.

December 11 onward is reserved for final integration and presentation, not major new features.


---

## 5. Benchmark Design

### Task A — Straight-line pushing

Start with a box directly in front of both ducks.

**Goal:** Move it forward by 0.5 m.

Metrics:

- Forward displacement.
- Lateral drift.
- Number of robot falls.
- Successful trials / total trials.

First milestone: demonstrate 0.30 m of box travel.

Target benchmark: at least 8/10 successful scripted trials under a fixed easy configuration.

### Task B — Box orientation control

Place the box at an initial angle and request a different orientation.

**Goal:** Rotate the box approximately 30 degrees without excessive translation.

Metrics:

- Final angular error.
- Unwanted translation.
- Falls and contact loss.
- Time required.

First milestone: one controlled 15–30 degree rotation.

Target benchmark: orientation within 20 degrees of the requested heading.

### Task C — Combined position and orientation

Specify a goal position and yaw.

**Goal:** Move the box 0.5 m while achieving a target orientation offset of approximately 30 degrees.

A successful episode requires:

- Box center within 0.15 m of goal.
- Orientation error within 20 degrees.
- Both robots upright.
- No artificial object attachment or repositioning.
- Goal maintained for at least 1 second.

Initial episode limit: 20 seconds.

Target: scripted success on at least 6/10 simple trials before investing heavily in RL.

### Task D — Generalization

Evaluate on box configurations not used during training.

Suggested test dimensions:

- Different box masses.
- Different starting orientations.
- Small variations in floor friction.
- Different goal positions.

Train and test seeds must be separated.

Start with 10 trials per condition, then use at least 30 held-out seeds for the main final comparison if compute permits.

### Core benchmark metrics

| Metric | Mathematical definition |
|---|---|
| Position error | $e_p = \lVert p_{\mathrm{box}} - p_{\mathrm{goal}} \rVert_2$ |
| Orientation error | $e_\theta = \lvert \mathrm{wrap}(\theta_{\mathrm{box}}-\theta_{\mathrm{goal}}) \rvert$ |
| Success rate | Successful episodes / total valid episodes |
| Fall rate | Episodes where either duck falls / total episodes |
| Task completion time | Time until the goal is achieved and held |
| Object progress | Reduction in box-to-goal distance |
| Contact reliability | Fraction of active task time with useful pushing contact |

The final evaluation should use identical object configurations, starting states, episode lengths, and random seeds for each controller.


---

## 6. Baselines and RL Methodology

We will compare four progressively more capable systems.

| Baseline | Controller | Purpose |
|---|---|---|
| B0 | One duck with a pushing policy | Reference performance |
| B1 | Two ducks given identical fixed commands | Tests whether simply adding a second robot helps |
| B2 | Two ducks with scripted feedback coordination | Strong classical-control baseline |
| B3 | Two ducks with learned PPO coordination | Our primary RL experiment |

B0 should be evaluated on the same box/task setup as the others; the published single-duck numbers are reference evidence, not directly comparable to our future results.

### Proposed PPO reward

Define:

$$
e_p(t)=\lVert p_{\mathrm{box}}(t)-p_{\mathrm{goal}} \rVert
$$

$$
e_\theta(t)=\lvert \mathrm{wrap}(\theta_{\mathrm{box}}(t)-\theta_{\mathrm{goal}}) \rvert
$$

A candidate reward is:

$$
R_t =
w_p[e_p(t-1)-e_p(t)]
+
w_\theta[e_\theta(t-1)-e_\theta(t)]
+
w_g R_{\mathrm{goal}}
-
w_f P_{\mathrm{fall}}
-
w_c P_{\mathrm{collision}}
$$

This rewards progress rather than simply rewarding being near the goal at every time step.

We will need to distinguish useful box contact from damaging impacts, so contact penalties should be designed carefully rather than penalizing all contact.

The first policy should train on straight pushing only. Position-plus-orientation control is a curriculum extension.

### Main RL experiment

Compare a learned centralized controller against B2, the scripted feedback controller.

A meaningful success would be either:

- At least a 20-percentage-point increase in task success on held-out scenarios, or
- At least a 20% reduction in final pose error without increasing fall rate.

These are research targets, not guaranteed improvements.

If PPO performs worse, report that result and diagnose whether the limitation comes from the controller, training budget, reward function, or low-level locomotion behavior.


---

## 7. Risks and Fallbacks

**Risk 1: Two ducks cannot push the box reliably.**

Fallback: Start with one duck and a smaller box, verify correct contact physics, then add the second duck.

**Risk 2: Existing walking policies become unstable under pushing loads.**

Fallback: Evaluate the pretrained Shoe Push policy as the locomotion controller. Document differences in actuator and collision models.

**Risk 3: The shared simulation is too slow on a Mac.**

Fallback: Use the Mac for debugging and visualization, and investigate headless simulation or GPU compute for large batches.

**Risk 4: Training becomes too complex.**

Fallback: Complete the scripted coordinator and produce a rigorous benchmark before implementing RL.

**Risk 5: PPO learns to exploit the reward.**

Fallback: Inspect trajectories, measure actual box movement and stability, and revise reward shaping while preserving held-out test scenarios.

**Risk 6: We run out of time.**

Priority order:

1. Working two-duck scene.
2. Physical box pushing.
3. Scripted coordination.
4. Evaluation benchmark.
5. RL training.
6. Generalization.

A reproducible scripted baseline with meaningful contact and pose-control measurements is preferable to an incomplete RL model.


---

## 8. Final Research Presentation

The final presentation should answer:

1. What happens when two independently controlled MicroDucks attempt to manipulate the same object?
2. How can we coordinate their movement without changing their pretrained locomotion policies?
3. Can a learned high-level controller outperform a scripted feedback baseline?
4. What failure modes arise from contact dynamics, locomotion limitations, and coordination?
5. How well does the approach generalize to new object configurations?

The strongest demonstration is a side-by-side comparison of the scripted and learned controllers completing the same box-positioning task.

**Success is not simply getting the box to move. It is showing whether cooperation and learning improve control of the box's final pose.**
