---
description: "Use when integrating with existing code, calling functions, or referencing schemas. Prevents hallucinated methods, config fields, pipeline stages, or interfaces that don't exist."
---

# Do Not Invent APIs

Never assume an API, schema, config field, or interface exists. **Verify first.**

## Rules

1. **Before calling a function you haven't used before**, read its definition or docstring. Check:
   - Parameter names and types
   - Return type
   - Side effects (does it mutate state? emit events? log?)

2. **Before referencing a config field**, read the config model (`baet.config.models`) to verify the field exists and understand its type.

3. **Before accessing a class attribute**, read the class definition. Do not assume properties, methods, or nested attributes exist.

4. **Before integrating with a pipeline or registry**, read the existing code to understand the expected interface. Do not invent new pipeline stages or registry keys.

5. **Before referencing a database column, file path, or data schema**, verify it exists in the data models, `DatasetRef`, or file system.

6. **If you can't find it, ask.** If a symbol or field you need doesn't exist after searching, say so. Do not create a plausible-sounding name and hope it works.

## Common Hallucination Targets in This Codebase

- **Config fields**: `baet.config.models` defines the schema. Do not add fields to config dicts without updating the model.
- **Event types**: `baet.core.events.EventType` is a closed enum. Do not create new event types without adding them to the enum.
- **Order fields**: `baet.core.orders.Order` is a frozen dataclass. Do not assume fields that aren't defined.
- **Risk policies**: Subclass `RiskPolicy` from `baet.risk.policy`. Do not create parallel risk interfaces.
- **ML pipeline stages**: `baet.ml` has specific classes (`LeakageDetector`, `PurgedKFold`, `TripleBarrierLabeler`). Do not invent new pipeline stages.

## Anti-Patterns

- "Let me add a `config.ml.learning_rate` field" — verify the config model first.
- "I'll call `order.submit()`" — check what methods `Order` actually has.
- "The `FeatureStore` probably has a `get_feature_matrix()` method" — read the file.
- "I'll create a `DataValidator` class for the pipeline" — check if one already exists.
