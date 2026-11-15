# Diagrams

How the project fits together, in small pictures. Each is a Mermaid diagram (drawn by GitHub from the
text below it, in a hand-drawn style). The system loop is also on the [README](../README.md).

## 1. Central, decentralized, distilled: who sees what, who decides

```mermaid
---
config:
  look: handDrawn
  theme: neutral
---
flowchart LR
  subgraph C["Central"]
    direction LR
    c1["The whole scene:<br/>both ducks, box, target"] --> c2["One brain"] --> c3["Commands for<br/>both ducks"]
  end
  subgraph D["Decentralized (D2)"]
    direction LR
    d1["Duck A's view<br/>+ where B is"] --> d2["Brain copy"] --> d3["Duck A's<br/>commands"]
    d4["Duck B's view<br/>+ where A is"] --> d5["Same brain copy"] --> d6["Duck B's<br/>commands"]
  end
  subgraph S["Distilled"]
    direction LR
    s1["Central brain<br/>(trained first)"] -->|"teaches by example"| s2["Decentralized ducks<br/>(then keep training)"]
  end
```

## 2. The training loop: how the reward changes the network

```mermaid
---
config:
  look: handDrawn
  theme: neutral
---
flowchart LR
  A["The network picks a speed<br/>and a turn for each duck<br/>(random weights at first)"] --> B["The ducks try it in the<br/>simulator, up to 100 steps"]
  B --> C["After every step: reward<br/>box closer? box turned right?<br/>a duck fell?"]
  C --> D["PPO nudges the weights:<br/>do more of what scored well"]
  D --> A
```

## 3. The curriculum ladder: from easy starts to the full task

```mermaid
---
config:
  look: handDrawn
  theme: neutral
---
flowchart LR
  L1["1. Fixed start<br/>(done)"] --> L2["2. Random box pose<br/>stage 1 (done)"]
  L2 --> L3a["3a. Steering<br/>turn the box either way<br/>(in progress)"]
  L2 --> L3b["3b. Rendezvous<br/>ducks start apart<br/>(starting)"]
  L3a --> L4["4. One combined<br/>curriculum"]
  L3b --> L4
  L4 --> L5["5. Full task<br/>ducks and box start anywhere,<br/>any angle"]
  L5 --> L6["6. Distill into per-duck<br/>controllers, compare with<br/>D2 from scratch"]
```

## 4. The chirp experiment: what each duck knows, and when

```mermaid
---
config:
  look: handDrawn
  theme: neutral
---
flowchart LR
  subgraph T["D2 today"]
    direction TB
    t1["Partner's exact position<br/>and heading<br/>every 0.2 s"]
  end
  subgraph K["With chirps (planned)"]
    direction TB
    k1["Every few seconds,<br/>the partner chirps"] --> k2["A rough direction<br/>(tens of degrees off),<br/>maybe a rough distance"]
    k2 --> k3["Held until the next chirp.<br/>Heading is not heard."]
  end
  A["Always known, both cases:<br/>box, target, own speed"] --- T
  A --- K
```

## 5. Data flow: from settings to results

```mermaid
---
config:
  look: handDrawn
  theme: neutral
---
flowchart LR
  cfg["Config file<br/>(every setting)"] --> q["Training queue<br/>(one run after another)"]
  q --> runs["runs/<br/>checkpoints, videos, logs<br/>(kept out of git)"]
  runs --> ev["Test on the<br/>50-start test set"]
  ts["Test sets<br/>(never trained on)"] --> ev
  ev --> res["Results in the<br/>experiment folder"]
  res --> docs["README, ROADMAP<br/>and timeline"]
```
