# Visibility check: runs/decentral-p2-d2/model.zip

Front camera field of view 120 deg, range 0.8 m (placeholders). One deterministic episode per start of `experiments/test_sets/stage1.json`. Percent of steps in which a duck sees its partner.

| run | what the policy acts on | box blocks the view | duck A sees B | duck B sees A | both see each other | episodes won |
|---|---|---|---|---|---|---|
| exact | exact partner info (D2 as trained) | no | 6.5% | 5.1% | 0.1% | 37/50 |
| exact | exact partner info (D2 as trained) | yes | 6.3% | 2.7% | 0.0% | 37/50 |
| vision | vision, chirps out of view | no | 2.5% | 3.3% | 0.0% | 17/50 |
| vision+box | vision, chirps out of view | yes | 2.4% | 2.2% | 0.0% | 17/50 |
