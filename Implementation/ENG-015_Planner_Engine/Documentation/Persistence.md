# Persistence and migration

`semantic_plans.json` has an envelope with schema version, engine version, and plans. Schema 1.0 is accepted; unknown schemas fail closed. Import is the explicit migration boundary and requires model reconstruction, current-Affordance validation, graph validation, and checksum validation. Saves use a same-directory temporary file and atomic replacement.

