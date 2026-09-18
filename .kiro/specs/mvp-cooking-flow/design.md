# Design — MVP Cooking Flow

**Spec:** `mvp-cooking-flow`
**Status:** Draft — pending Nicholas review

---

## 1. Domain model

### 1.1 Entities

All entities are stored in Postgres. UUIDs are used for all primary keys.

#### `User`

The authenticated user. Auth model is pending (open decision §7 of handoff). This entity is a placeholder that gives every other entity a foreign key target.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `created_at` | timestamp tz | |

#### `Profile`

One per user, updated in place.

| Field | Type | Notes |
|---|---|---|
| `user_id` | UUID FK → User | unique |
| `calorie_target` | float | kcal/day |
| `protein_target_g` | float | g/day |
| `updated_at` | timestamp tz | |

#### `Equipment`

One-to-many: a user owns a list of equipment. "Permanent" — survives beyond any session.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → User | |
| `name` | text | e.g. "air fryer", "Instant Pot" |
| `created_at` | timestamp tz | |

#### `Preference`

Saved preferences — permanent, one-to-many per user.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → User | |
| `text` | text | Free-form: "no pork", "low sodium" |
| `created_at` | timestamp tz | |

Note: rejecting a recipe does NOT write a `Preference` row. (REQ-3.3)

#### `PantryItem`

Tracks what the user has available. The `state` field implements the Available → Prepared → Consumed distinction.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → User | |
| `name` | text | e.g. "chicken breast" |
| `quantity_g` | float | always stored in grams (REQ-X.4) |
| `calories_per_100g` | float | from confirmed lookup or user input |
| `protein_g_per_100g` | float | |
| `nutrition_source` | `NutritionSource` enum | `USDA`, `OPENFOODFACTS`, `USER_LABEL`, `ESTIMATED` |
| `estimated` | bool | true if source is `ESTIMATED` or unconfirmed |
| `state` | `ItemState` enum | `AVAILABLE` only — pantry items are always available |
| `created_at` | timestamp tz | |

`PantryItem` rows are not consumed directly. They are referenced by `SessionIngredient`, which carries the state transitions.

#### `CookingSession`

A single cooking event. Stateless-MCP-safe: every stateful tool accepts `session_id` as an argument (REQ-X.3).

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → User | |
| `status` | `SessionStatus` enum | `ACTIVE`, `FINALIZED`, `ABANDONED` |
| `equipment_override` | `text[]` | null → use saved equipment; non-null → session-only override (REQ-1.4) |
| `preference_overrides` | `text[]` | null → use saved preferences; non-null → session-only additions (REQ-1.4) |
| `created_at` | timestamp tz | |
| `finalized_at` | timestamp tz | null until finalized |

The `equipment_override` and `preference_overrides` columns implement the permanent-vs-session mechanism: a session write goes here, never to the `Equipment`/`Preference` tables.

#### `SessionIngredient`

The main state-bearing entity. Tracks one ingredient's lifecycle through a session.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK → CookingSession | |
| `pantry_item_id` | UUID FK → PantryItem | nullable — ingredient may be ad-hoc |
| `name` | text | denormalised for display |
| `quantity_g` | float | confirmed or corrected quantity |
| `calories` | float | computed by `nutrition.py`; not stored raw |
| `protein_g` | float | computed by `nutrition.py` |
| `estimated` | bool | from Macros.estimated |
| `state` | `ItemState` enum | `AVAILABLE` → `PREPARED` |
| `correction_factor` | float | 1.0 default; updated by `adjust_session_ingredient` |

**State transitions for `SessionIngredient`:**
- Created → `AVAILABLE`
- `finalize_batch` → `PREPARED` (for all ingredients in the batch)
- There is no `CONSUMED` on `SessionIngredient`. Consumed state lives on `Portion`.

#### `RecipeBatch`

A finalized cooking result. Created by `finalize_batch`.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK → CookingSession | |
| `total_calories` | float | from `total()` |
| `total_protein_g` | float | from `total()` |
| `estimated` | bool | from summed Macros |
| `portions_intended` | int | user-specified (≥1) |
| `calories_per_portion` | float | from `split_batch()` |
| `protein_g_per_portion` | float | from `split_batch()` |
| `created_at` | timestamp tz | |

#### `Portion`

One serving of a `RecipeBatch`. Created by `finalize_batch`, one row per portion.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `batch_id` | UUID FK → RecipeBatch | |
| `user_id` | UUID FK → User | denormalised for query convenience |
| `calories` | float | per-portion from `split_batch()` |
| `protein_g` | float | |
| `estimated` | bool | inherits from batch |
| `state` | `ItemState` enum | `PREPARED` → `CONSUMED` |
| `created_at` | timestamp tz | |

**State transitions for `Portion`:**
- Created by `finalize_batch` → `PREPARED`
- `log_meal` → `CONSUMED`
- `void_meal_log` → back to `PREPARED` (REQ-6.5)

#### `MealLog`

An immutable record that a portion was eaten. Never deleted.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → User | |
| `portion_id` | UUID FK → Portion | unique when `voided=false`; see idempotency note |
| `calories_at_log` | float | snapshot at log time |
| `protein_g_at_log` | float | snapshot |
| `estimated` | bool | snapshot |
| `logged_at` | timestamp tz | |
| `voided` | bool | default false; set by `void_meal_log` |
| `voided_at` | timestamp tz | null until voided |

Idempotency: a unique partial index on `(portion_id)` WHERE `voided=false` enforces REQ-6.4 at the database level — a second `log_meal` for the same portion raises a constraint violation that the application catches and returns as `ALREADY_CONSUMED`.

---

### 1.2 Enums

```python
class ItemState(str, Enum):
    AVAILABLE = "AVAILABLE"   # in pantry or added to session, not yet cooked
    PREPARED  = "PREPARED"    # cooked into a batch; portion exists but not eaten
    CONSUMED  = "CONSUMED"    # portion logged as eaten

class SessionStatus(str, Enum):
    ACTIVE    = "ACTIVE"
    FINALIZED = "FINALIZED"
    ABANDONED = "ABANDONED"

class NutritionSource(str, Enum):
    USDA           = "USDA"            # confirmed lookup from USDA FoodData Central
    OPENFOODFACTS  = "OPENFOODFACTS"   # confirmed from Open Food Facts
    USER_LABEL     = "USER_LABEL"      # user read the label themselves
    ESTIMATED      = "ESTIMATED"       # no confirmed match — user provided a guess
```

---

### 1.3 Nutrition provenance decision

The `nutrition.py` boolean `estimated` is sufficient for MVP. Rationale:

The invariant requires that uncertainty is **visible**, not that every provenance tier is stored. Three tiers (`USDA`, `USER_LABEL`, `ESTIMATED`) are modelled in `NutritionSource` on `PantryItem` and `SessionIngredient` for display purposes. The boolean on `Macros` — which propagates through all arithmetic — is what enforces invariant 3 in `nutrition.py`.

**Decision: do NOT change `nutrition.py`'s `Macros` type.** The existing `estimated: bool` is the correct propagation primitive. `NutritionSource` is the richer display-layer field. These are separate concerns.

If a future spec requires per-ingredient provenance chains (e.g., "which number in this batch was a guess?"), that is a new field on `SessionIngredient`, not a change to `Macros`.

---

## 2. State machine

```
SessionIngredient:  AVAILABLE  ──── finalize_batch ────► PREPARED
                        ▲
                        │ (created by add_session_ingredient)

Portion:            PREPARED   ──── log_meal ───────────► CONSUMED
                        ▲               │
                        └── void_meal_log ◄──────────────┘
```

**Key rules:**
- `log_meal` requires the `Portion` to be in `PREPARED` state. Any other state returns `STATE_VIOLATION`.
- `finalize_batch` requires the `CookingSession` to be in `ACTIVE` status. Any other status returns `SESSION_NOT_ACTIVE`.
- `void_meal_log` requires `MealLog.voided = false`. Already-voided entries return `ALREADY_VOIDED`.
- There is no direct `AVAILABLE → CONSUMED` path. Cooking is mandatory.

---

## 3. Permanent vs session-scoped state — the mechanism

Session overrides are stored in columns on `CookingSession`, not as mutations to profile tables.

When a tool needs the effective equipment list:
1. If `CookingSession.equipment_override IS NOT NULL`, use that list.
2. Otherwise, query `Equipment` for the user.

When a tool needs the effective preferences:
1. Start with the user's saved `Preference` rows.
2. Append any entries in `CookingSession.preference_overrides`.
3. The combined list is the effective preference set for this session.

Session overrides never write to `Equipment` or `Preference`. Closing a session discards the overrides. This satisfies REQ-1.4 and invariant 4.

---

## 4. Stateless MCP + token-derived identity

Every stateful tool that operates on a `CookingSession` accepts `session_id: str` (UUID) as a required argument. The server is stateless — no in-process session cache, no MCP transport session state (REQ-X.3).

**`user_id` is NEVER a tool parameter.** It is derived server-side from the validated OAuth Bearer token via a FastAPI dependency (`get_current_user_id`). Alexa+ performs account-linking via OAuth 2.1 `authorization_code` + PKCE; the issued Bearer token encodes the user identity. Direct API / frontend callers go through the same OAuth flow.

The conversation flow:
1. Client completes OAuth account-linking → receives Bearer token
2. `start_cooking_session` (auth header carries token) → server derives `user_id` → returns `session_id`
3. All subsequent session tools receive `session_id` as an argument; `user_id` resolved from token
4. `log_meal` / `get_today` use token-derived `user_id` + caller-supplied `portion_id` / `meal_log_id`

## 4a. OAuth endpoints (required by Alexa+ MCP)

The server must expose these before `alexa-ai deploy` can succeed:

| Endpoint | Purpose |
|---|---|
| `GET /.well-known/oauth-authorization-server` | RFC 8414 metadata; must list `client_credentials` + `S256` |
| `GET /.well-known/oauth-protected-resource` | RFC 9728 Protected Resource Metadata |
| `POST /oauth/token` | Issues Bearer tokens for M2M (`client_credentials`) and user (`authorization_code` + PKCE) |
| `GET /oauth/authorize` | Authorization endpoint for PKCE flow |

Alexa+ requirements:
- `401` responses must NOT include a `WWW-Authenticate` header
- Dynamic Client Registration (DCR), OIDC, and Step-Up Authorization are NOT supported
- Token lifetime ≤ 3600s for M2M; refresh tokens allowed for user flow

---

## 5. MCP tool contract

All tools return flat dicts with snake_case keys, matching the style of the existing tools in `mcp_server.py`. Every response includes `estimated: bool` when macros are involved.

### 5.1 Profile tools

---

#### `get_profile`

Returns the user's saved goals, equipment, and preferences. `user_id` derived from Bearer token.

**Arguments:** none

**Returns:**
```json
{
  "calorie_target": 2000.0,
  "protein_target_g": 150.0,
  "equipment": ["air fryer", "Instant Pot"],
  "preferences": ["no pork", "low sodium"]
}
```

**Errors:** `USER_NOT_FOUND`, `UNAUTHORIZED`

---

#### `update_profile`

Updates calorie/protein targets.

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `calorie_target` | `float` | no | ≥0 |
| `protein_target_g` | `float` | no | ≥0 |

**Returns:**
```json
{
  "calorie_target": 2000.0,
  "protein_target_g": 150.0,
  "updated": true
}
```

**Errors:** `USER_NOT_FOUND`, `INVALID_VALUE`, `UNAUTHORIZED`

---

### 5.2 Preferences

---

#### `set_preference`

Adds or removes a preference. Scope controls whether it is permanent or session-only.

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `text` | `str` | yes | e.g. "no pork" |
| `action` | `str` | yes | `"add"` or `"remove"` |
| `scope` | `str` | no | `"permanent"` (default) or `"session"` |
| `session_id` | `str` (UUID) | conditional | Required when `scope="session"` |

**Returns:**
```json
{
  "preference": "no pork",
  "action": "add",
  "scope": "permanent"
}
```

**Errors:** `USER_NOT_FOUND`, `SESSION_NOT_FOUND`, `PREFERENCE_NOT_FOUND` (remove only), `INVALID_SCOPE`, `UNAUTHORIZED`

---

### 5.3 Equipment

---

#### `update_equipment`

Adds or removes an equipment item, permanent or session-only.

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `name` | `str` | yes | Equipment name |
| `action` | `str` | yes | `"add"` or `"remove"` |
| `scope` | `str` | no | `"permanent"` (default) or `"session"` |
| `session_id` | `str` (UUID) | conditional | Required when `scope="session"` |

**Returns:**
```json
{
  "equipment": "air fryer",
  "action": "add",
  "scope": "permanent"
}
```

**Errors:** `USER_NOT_FOUND`, `SESSION_NOT_FOUND`, `EQUIPMENT_NOT_FOUND` (remove only), `UNAUTHORIZED`

---

### 5.4 Pantry

---

#### `list_pantry`

Returns all `AVAILABLE` pantry items for the authenticated user.

**Arguments:** none

**Returns:**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "chicken breast",
      "quantity_g": 500.0,
      "calories_per_100g": 165.0,
      "protein_g_per_100g": 31.0,
      "nutrition_source": "USDA",
      "estimated": false
    }
  ],
  "count": 1
}
```

**Errors:** `USER_NOT_FOUND`, `UNAUTHORIZED`

---

#### `update_pantry`

Adds, updates quantity, or removes a pantry item.

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `name` | `str` | yes | |
| `action` | `str` | yes | `"add"`, `"update_quantity"`, or `"remove"` |
| `quantity_g` | `float` | conditional | Required for `add` and `update_quantity`. ≥0 |
| `calories_per_100g` | `float` | conditional | Required for `add` |
| `protein_g_per_100g` | `float` | conditional | Required for `add` |
| `nutrition_source` | `str` | no | `"USDA"`, `"OPENFOODFACTS"`, `"USER_LABEL"`, `"ESTIMATED"`. Defaults to `"ESTIMATED"` |

**Returns:**
```json
{
  "id": "uuid",
  "name": "chicken breast",
  "quantity_g": 500.0,
  "nutrition_source": "USDA",
  "estimated": false,
  "action": "add"
}
```

**Errors:** `USER_NOT_FOUND`, `ITEM_NOT_FOUND` (update/remove only), `INVALID_VALUE`, `UNAUTHORIZED`

---

### 5.5 Nutrition lookup

---

#### `search_nutrition`

Searches USDA FoodData Central and Open Food Facts for a food item.

Returns candidates when multiple matches exist. Caller must not finalize an ingredient until the user picks one (REQ-2.5, invariant 3).

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `query` | `str` | yes | Food name or barcode |

**Returns — single confirmed match:**
```json
{
  "matched": true,
  "ambiguous": false,
  "candidate": {
    "name": "Chicken Breast, Raw",
    "source": "USDA",
    "fdcId": "171477",
    "calories_per_100g": 120.0,
    "protein_g_per_100g": 22.5,
    "estimated": false
  }
}
```

**Returns — ambiguous (multiple candidates):**
```json
{
  "matched": true,
  "ambiguous": true,
  "candidates": [
    {
      "rank": 1,
      "name": "Chicken Breast, Raw",
      "source": "USDA",
      "fdcId": "171477",
      "calories_per_100g": 120.0,
      "protein_g_per_100g": 22.5,
      "estimated": false
    },
    {
      "rank": 2,
      "name": "Chicken Breast, Boneless Skinless (Perdue)",
      "source": "OPENFOODFACTS",
      "fdcId": null,
      "calories_per_100g": 110.0,
      "protein_g_per_100g": 23.0,
      "estimated": false
    }
  ]
}
```

**Returns — no match:**
```json
{
  "matched": false,
  "ambiguous": false,
  "candidates": []
}
```

**Errors:** `LOOKUP_UNAVAILABLE` (external API unreachable)

---

### 5.6 Session tools

---

#### `start_cooking_session`

Creates a new `CookingSession` for the authenticated user.

**Arguments:** none

**Returns:**
```json
{
  "session_id": "uuid",
  "status": "ACTIVE",
  "created_at": "2026-09-18T07:00:00Z"
}
```

**Errors:** `USER_NOT_FOUND`, `UNAUTHORIZED`

---

#### `add_session_ingredient`

Adds one ingredient to an active session. Ingredient starts in `AVAILABLE` state.

Macros are computed by the server using `Macros(calories=..., protein_g=...)` — the caller passes per-100g values and quantity; the server calls `nutrition.py` to get the ingredient's contribution. **The LLM never computes this.**

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `session_id` | `str` (UUID) | yes | |
| `name` | `str` | yes | Display name |
| `quantity_g` | `float` | yes | ≥0 |
| `calories_per_100g` | `float` | yes | ≥0 |
| `protein_g_per_100g` | `float` | yes | ≥0 |
| `estimated` | `bool` | no | Default false |

**Returns:**
```json
{
  "ingredient_id": "uuid",
  "name": "chicken breast",
  "quantity_g": 400.0,
  "calories": 480.0,
  "protein_g": 90.0,
  "estimated": false,
  "state": "AVAILABLE"
}
```

**Errors:** `SESSION_NOT_FOUND`, `SESSION_NOT_ACTIVE`, `INVALID_VALUE`

---

#### `adjust_session_ingredient`

Corrects an ingredient's quantity mid-cook. Calls `scale_ingredient` from `nutrition.py`.

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `session_id` | `str` (UUID) | yes | |
| `ingredient_id` | `str` (UUID) | yes | |
| `new_quantity_g` | `float` | yes | ≥0 |
| `estimated` | `bool` | no | Default: inherit from original |

**Returns:**
```json
{
  "ingredient_id": "uuid",
  "name": "chicken breast",
  "quantity_g": 200.0,
  "calories": 240.0,
  "protein_g": 45.0,
  "estimated": false,
  "correction_factor": 0.5
}
```

**Errors:** `SESSION_NOT_FOUND`, `SESSION_NOT_ACTIVE`, `INGREDIENT_NOT_FOUND`, `INGREDIENT_WRONG_SESSION`, `INVALID_VALUE`

---

### 5.7 Recipe generation

---

#### `suggest_recipe`

Returns context for the LLM to generate a recipe. This tool assembles the structured context; the LLM produces the recipe text.

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `session_id` | `str` (UUID) | yes | |

**Returns:**
```json
{
  "session_id": "uuid",
  "ingredients": [
    {"name": "chicken breast", "quantity_g": 400.0},
    {"name": "brown rice", "quantity_g": 200.0}
  ],
  "effective_equipment": ["air fryer", "rice cooker"],
  "effective_preferences": ["no pork", "low sodium"],
  "calorie_target": 2000.0,
  "protein_target_g": 150.0
}
```

Note: **no macros are included** in this response (REQ-3.2). Macro numbers would leak arithmetic responsibility to the LLM. The LLM uses this for qualitative recipe suggestion only.

**Errors:** `SESSION_NOT_FOUND`, `SESSION_NOT_ACTIVE`, `USER_NOT_FOUND`, `UNAUTHORIZED`

---

### 5.8 Batch finalization

---

#### `finalize_batch`

Sums all session ingredients, computes per-portion macros, creates `RecipeBatch` and `Portion` rows, and transitions all `SessionIngredient` rows to `PREPARED`.

Calls `total()` and `split_batch()` from `nutrition.py`.

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `session_id` | `str` (UUID) | yes | |
| `portions` | `int` | yes | ≥1 |

**Returns:**
```json
{
  "batch_id": "uuid",
  "total_calories": 840.0,
  "total_protein_g": 117.0,
  "portions": 3,
  "calories_per_portion": 280.0,
  "protein_g_per_portion": 39.0,
  "estimated": false,
  "portion_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Errors:** `SESSION_NOT_FOUND`, `SESSION_NOT_ACTIVE`, `NO_INGREDIENTS`, `INVALID_VALUE`

---

### 5.9 Meal logging

---

#### `log_meal`

Records a portion as consumed. Transitions `Portion` to `CONSUMED`. Returns updated daily progress.

Calls `remaining_against_targets` from `nutrition.py`.

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `portion_id` | `str` (UUID) | yes | |

**Returns:**
```json
{
  "meal_log_id": "uuid",
  "portion_id": "uuid",
  "calories_eaten": 280.0,
  "protein_g_eaten": 39.0,
  "estimated": false,
  "daily": {
    "calories_remaining": 1520.0,
    "protein_g_remaining": 111.0,
    "calories_over_target": false,
    "protein_target_met": false,
    "estimated": false
  }
}
```

**Errors:** `USER_NOT_FOUND`, `PORTION_NOT_FOUND`, `ALREADY_CONSUMED`, `STATE_VIOLATION`, `UNAUTHORIZED`

---

#### `void_meal_log`

Marks a meal log as voided. Transitions the `Portion` back to `PREPARED`.

**Arguments:**
| Name | Type | Required | Notes |
|---|---|---|---|
| `meal_log_id` | `str` (UUID) | yes | |

**Returns:**
```json
{
  "meal_log_id": "uuid",
  "voided": true,
  "portion_state": "PREPARED"
}
```

**Errors:** `MEAL_LOG_NOT_FOUND`, `WRONG_USER`, `ALREADY_VOIDED`, `UNAUTHORIZED`

---

#### `get_today`

Returns today's consumption summary and remaining targets for the authenticated user.

Calls `remaining_against_targets` from `nutrition.py` after summing all non-voided `MealLog` entries for today (UTC day boundary).

**Arguments:** none

**Returns:**
```json
{
  "consumed_calories": 480.0,
  "consumed_protein_g": 39.0,
  "estimated": false,
  "daily": {
    "calories_remaining": 1520.0,
    "protein_g_remaining": 111.0,
    "calories_over_target": false,
    "protein_target_met": false,
    "estimated": false
  },
  "meals": [
    {
      "meal_log_id": "uuid",
      "portion_id": "uuid",
      "calories_eaten": 480.0,
      "protein_g_eaten": 39.0,
      "logged_at": "2026-09-18T12:00:00Z",
      "estimated": false
    }
  ]
}
```

**Errors:** `USER_NOT_FOUND`, `UNAUTHORIZED`

---

## 6. Database notes

- SQLAlchemy 2.x declarative models, Alembic for migrations.
- All UUID PKs use `uuid_generate_v4()` or Python `uuid4()`.
- The unique partial index on `MealLog(portion_id) WHERE voided=false` enforces idempotency (REQ-6.4). Alembic migration must create this explicitly.
- `CookingSession.equipment_override` and `preference_overrides` are stored as Postgres `text[]` arrays (SQLAlchemy `ARRAY(Text)`).
- All timestamps are `TIMESTAMPTZ` (UTC stored, timezone-aware in Python as `datetime` with `tzinfo=UTC`).

---

## 7. Out of scope for this spec

- GroceryList entity (handoff §3 says "model only if free" — it is not free given the above surface; deferred)
- Barcode lookup path (noted, design accepted, implementation deferred)
- Auth token → user_id derivation (blocked on open decision 2)
- Next.js frontend (teammate's lane)
- Alexa+ skill integration (blocked on open decision 3)
