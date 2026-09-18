# Requirements — MVP Cooking Flow

**Spec:** `mvp-cooking-flow`
**Status:** Draft — pending Nicholas review
**Invariants in scope:** all four from `AGENTS.md`

---

## Scope

This spec covers exactly the seven-step MVP demo path:

1. Save goals, equipment, and preferences
2. Create a cooking session with ingredients and nutrition information
3. Generate one suitable recipe
4. Correct ingredient quantities during cooking
5. Calculate batch totals and serving sizes
6. Log a portion and update daily totals
7. Save the remaining portions

Everything else — weekly planning, grocery reminders, barcode scanning, social features, broader recipe library — is out of scope for this spec and must not be implemented as a side-effect.

---

## EARS Requirements

### 1 — Profile: goals, equipment, preferences

**REQ-1.1** WHEN a user provides a calorie target and a protein target, the system SHALL store them persistently against the user's profile.

**REQ-1.2** WHEN a user provides an equipment list (e.g., "I have an air fryer and an Instant Pot"), the system SHALL store it persistently against the user's profile.

**REQ-1.3** WHEN a user states a preference (e.g., "I don't eat pork", "low sodium"), the system SHALL store it persistently against the user's profile tagged as a saved preference.

**REQ-1.4** WHERE a cooking session is in progress, IF the user states a temporary preference or equipment override (e.g., "I'm cooking at a friend's house — they only have a skillet"), the system SHALL apply that override for the duration of the session WITHOUT mutating the user's saved profile.

**REQ-1.5** WHEN a user retrieves their profile, the system SHALL return current calorie target, protein target, equipment list, and saved preferences.

---

### 2 — Cooking session creation

**REQ-2.1** WHEN a user starts a cooking session, the system SHALL create a persistent `CookingSession` entity with a unique ID, associating it with the user.

**REQ-2.2** WHEN a user adds an ingredient to an active session, the system SHALL record the ingredient name, quantity, unit, and associated `Macros` (calories, protein_g, and the `estimated` flag).

**REQ-2.3** WHERE an ingredient's nutrition data comes from a confirmed lookup (USDA or product database), the system SHALL record `estimated=false` for that ingredient's macros.

**REQ-2.4** WHERE an ingredient's nutrition data cannot be confirmed (no match, or the user provides a manual estimate), the system SHALL record `estimated=true` for that ingredient's macros.

**REQ-2.5** WHERE a product lookup returns multiple candidate matches, the system SHALL return all candidates to the caller (name, source, macros per 100 g, confidence score) and MUST NOT silently select one. The session ingredient SHALL NOT be finalised until the user confirms a match.

**REQ-2.6** WHEN a user adds an ingredient, the system SHALL mark it as `AVAILABLE` state.

---

### 3 — Recipe generation

**REQ-3.1** WHEN a user requests a recipe suggestion, the system SHALL pass the session's current ingredients (names, quantities), the effective equipment list (saved profile overridden by any session-level overrides), and the effective preferences (saved profile overridden by any session-level overrides) to the LLM.

**REQ-3.2** The system SHALL NOT pass raw nutrition numbers to the LLM for recipe generation. Nutrition computation is performed by `nutrition.py` after the recipe is selected.

**REQ-3.3** WHEN a user rejects a suggested recipe, the system SHALL NOT mark any of its constituent ingredients as disliked or modify the user's preference profile.

**REQ-3.4** WHEN a recipe is accepted, the system SHALL record which session ingredients are designated for this recipe batch.

---

### 4 — Mid-cook quantity correction

**REQ-4.1** WHEN a user corrects an ingredient quantity during an active session (e.g., "actually I only used 150 g of rice, not 200 g"), the system SHALL call `scale_ingredient` from `nutrition.py` to recompute that ingredient's macros contribution.

**REQ-4.2** WHEN a quantity correction is applied, the system SHALL NOT recompute all other ingredients — only the corrected one is rescaled and the batch total is re-summed.

**REQ-4.3** WHEN a corrected ingredient's original macros were `estimated=false` and the correction factor is derived from a confirmed quantity, the system SHALL keep `estimated=false`. If the correction factor is itself an estimate, the system SHALL set `estimated=true`.

---

### 5 — Batch totals and serving sizes

**REQ-5.1** WHEN a user finalises a batch, the system SHALL sum all session ingredient macros using `total()` from `nutrition.py` and store the result as a `RecipeBatch` entity.

**REQ-5.2** WHEN a batch is finalised, the system SHALL record the number of intended portions (provided by the user or defaulting to 1) and call `split_batch()` to compute per-portion macros.

**REQ-5.3** WHEN a batch is finalised, the system SHALL transition all ingredients designated for that batch from `AVAILABLE` state to `PREPARED` state.

**REQ-5.4** The `RecipeBatch` entity SHALL carry the `estimated` flag from the summed macros. If any ingredient was estimated, the batch is estimated.

**REQ-5.5** WHEN a batch is finalised, the remaining (unclaimed) portions SHALL be persisted as `Portion` entities, each with state `PREPARED`.

---

### 6 — Logging a portion

**REQ-6.1** WHEN a user logs a meal (e.g., "I just ate one portion of the chicken rice"), the system SHALL create a `MealLog` entry recording: user ID, portion ID, timestamp, and the macros at time of eating.

**REQ-6.2** WHEN a meal is logged, the system SHALL transition the consumed `Portion` from `PREPARED` to `CONSUMED` state.

**REQ-6.3** WHEN a meal is logged, the system SHALL call `remaining_against_targets` from `nutrition.py` using the updated daily consumed totals, and return the result to the caller.

**REQ-6.4** WHEN a user logs a meal, if the same `portion_id` has already been logged as `CONSUMED`, the system SHALL return an error (`ALREADY_CONSUMED`) and MUST NOT create a duplicate `MealLog` entry. (Idempotency guard — voice may deliver the same utterance twice.)

**REQ-6.5** WHEN a user states that a logged meal was entered in error (e.g., "I didn't actually eat that"), the system SHALL:
  - Set the `MealLog` entry's `voided=true` field.
  - Transition the associated `Portion` back to `PREPARED` state.
  - NOT delete the `MealLog` record (audit trail preserved).

**REQ-6.6** The system SHALL NOT count voided `MealLog` entries in daily totals.

---

### 7 — Saving remaining portions

**REQ-7.1** WHEN a cooking session is marked complete, all `Portion` entities associated with its batch that remain in `PREPARED` state SHALL be retained in the database for future logging.

**REQ-7.2** WHEN a user asks how many portions remain from a previous batch, the system SHALL count `Portion` entities in `PREPARED` state for that batch and return the count alongside per-portion macros.

**REQ-7.3** `Portion` entities in `PREPARED` state SHALL be available for logging in future sessions (i.e., they are not session-scoped — they persist until consumed or explicitly discarded).

---

## Cross-cutting requirements

**REQ-X.1** WHERE any returned value contains a macro that was computed from an estimated input, the API response SHALL include `estimated: true` at the top level of that response. This flag MUST NOT be stripped before reaching the frontend.

**REQ-X.2** The system SHALL NOT perform any arithmetic in application code outside of `nutrition.py` and the SQLAlchemy/Alembic query layer. All macro summation, scaling, and target comparisons call the functions in `nutrition.py`.

**REQ-X.3** All MCP stateful tools SHALL accept an explicit `session_id` (UUID string) where session context is required. Tools MUST NOT rely on MCP transport session state — the backend runs stateless behind a load balancer (App Runner multi-instance). See design.md §4.

**REQ-X.4** All data SHALL be stored in canonical SI units: grams for mass, Celsius for temperature. Display-unit conversion (oz, lbs, °F) is the frontend's responsibility. The backend never stores imperial values.

**REQ-X.5** WHEN an operation would violate an `Available → Prepared → Consumed` state transition (e.g., logging a meal from an ingredient not yet in a batch), the system SHALL return an error with a `STATE_VIOLATION` code and MUST NOT silently apply the operation.
