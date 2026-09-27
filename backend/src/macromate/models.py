"""SQLAlchemy models for the MVP cooking flow.

Implements `.kiro/specs/mvp-cooking-flow/design.md` section 1.

The three-state lifecycle from AGENTS.md invariant 1 is carried by two
entities, not one: `SessionIngredient` moves AVAILABLE -> PREPARED, and
`Portion` moves PREPARED -> CONSUMED. There is deliberately no direct
AVAILABLE -> CONSUMED path -- cooking is mandatory.

UUID primary keys carry both a Python-side and a server-side default. The
Python default gives objects an id before flush, which relationship wiring
needs; the server default keeps the column correct for inserts that bypass the
ORM (migrations, raw SQL, psql).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------
# Enums (design.md section 1.2)
# --------------------------------------------------------------------------


class ItemState(str, enum.Enum):
    AVAILABLE = "AVAILABLE"  # in pantry or added to a session, not yet cooked
    PREPARED = "PREPARED"  # cooked into a batch; portion exists but not eaten
    CONSUMED = "CONSUMED"  # portion logged as eaten


class SessionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FINALIZED = "FINALIZED"
    ABANDONED = "ABANDONED"


class NutritionSource(str, enum.Enum):
    USDA = "USDA"  # confirmed lookup from USDA FoodData Central
    OPENFOODFACTS = "OPENFOODFACTS"  # confirmed from Open Food Facts
    USER_LABEL = "USER_LABEL"  # user read the label themselves
    ESTIMATED = "ESTIMATED"  # no confirmed match -- user provided a guess


# --------------------------------------------------------------------------
# Column helpers
# --------------------------------------------------------------------------

_UUID_PK_SERVER_DEFAULT = text("uuid_generate_v4()")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=_UUID_PK_SERVER_DEFAULT,
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# --------------------------------------------------------------------------
# Entities
# --------------------------------------------------------------------------


class User(Base):
    """The authenticated user. `user_id` is always derived from the Bearer
    token server-side, never accepted as a tool argument (design.md section 4).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = _created_at()

    profile: Mapped[Profile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    equipment: Mapped[list[Equipment]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preferences: Mapped[list[Preference]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    pantry_items: Mapped[list[PantryItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[CookingSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Profile(Base):
    """Daily targets. One per user, updated in place.

    `user_id` is the primary key -- design.md section 1.1 gives Profile no
    separate id and marks user_id unique, which is exactly a one-to-one.
    """

    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    calorie_target: Mapped[float] = mapped_column(Float, nullable=False)
    protein_target_g: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Equipment(Base):
    """Permanent equipment. Session-only equipment lives in
    `CookingSession.equipment_override` and never reaches this table
    (design.md section 3).
    """

    __tablename__ = "equipment"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    user: Mapped[User] = relationship(back_populates="equipment")


class Preference(Base):
    """Saved preferences. Rejecting a recipe does NOT write a row here
    (REQ-3.3) -- inferred dislikes are not preferences.
    """

    __tablename__ = "preferences"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    user: Mapped[User] = relationship(back_populates="preferences")


class PantryItem(Base):
    """Food the user has. Always AVAILABLE -- pantry rows are never consumed
    directly. `SessionIngredient` carries the state transitions.
    """

    __tablename__ = "pantry_items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_g: Mapped[float] = mapped_column(Float, nullable=False)
    calories_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    nutrition_source: Mapped[NutritionSource] = mapped_column(
        SAEnum(NutritionSource, name="nutrition_source"), nullable=False
    )
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    state: Mapped[ItemState] = mapped_column(
        SAEnum(ItemState, name="item_state"),
        nullable=False,
        default=ItemState.AVAILABLE,
        server_default=ItemState.AVAILABLE.value,
    )
    created_at: Mapped[datetime] = _created_at()

    user: Mapped[User] = relationship(back_populates="pantry_items")


class CookingSession(Base):
    """A single cooking event.

    The two override columns are the permanent-vs-session mechanism
    (design.md section 3): a session-scoped write lands here and is discarded
    when the session closes, so it can never mutate the saved profile.

    NULL and empty-list mean different things. NULL means "no override, fall
    back to the saved list". An empty array means "explicitly nothing".
    """

    __tablename__ = "cooking_sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[SessionStatus] = mapped_column(
        SAEnum(SessionStatus, name="session_status"),
        nullable=False,
        default=SessionStatus.ACTIVE,
        server_default=SessionStatus.ACTIVE.value,
    )
    equipment_override: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    preference_overrides: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    created_at: Mapped[datetime] = _created_at()
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
    ingredients: Mapped[list[SessionIngredient]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    batches: Mapped[list[RecipeBatch]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class SessionIngredient(Base):
    """One ingredient's lifecycle within a session: AVAILABLE -> PREPARED.

    `calories` and `protein_g` are always computed by `nutrition.py`, never
    inline (AGENTS.md invariant 2).
    """

    __tablename__ = "session_ingredients"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cooking_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable: an ingredient can be ad-hoc, with no matching pantry row.
    pantry_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("pantry_items.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_g: Mapped[float] = mapped_column(Float, nullable=False)
    calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    state: Mapped[ItemState] = mapped_column(
        SAEnum(ItemState, name="item_state"),
        nullable=False,
        default=ItemState.AVAILABLE,
        server_default=ItemState.AVAILABLE.value,
    )
    correction_factor: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default=text("1.0")
    )

    session: Mapped[CookingSession] = relationship(back_populates="ingredients")


class RecipeBatch(Base):
    """A finalized cooking result. Created by `finalize_batch`."""

    __tablename__ = "recipe_batches"

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cooking_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    total_calories: Mapped[float] = mapped_column(Float, nullable=False)
    total_protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    portions_intended: Mapped[int] = mapped_column(Integer, nullable=False)
    calories_per_portion: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g_per_portion: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    session: Mapped[CookingSession] = relationship(back_populates="batches")
    portions: Mapped[list[Portion]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class Portion(Base):
    """One serving of a batch: PREPARED -> CONSUMED.

    Cooking a batch creates portions in PREPARED. Only `log_meal` moves a
    portion to CONSUMED, which is what makes "preparing food is not eating it"
    true in the data rather than only in the docs.
    """

    __tablename__ = "portions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    batch_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("recipe_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalised from batch -> session -> user for query convenience.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    state: Mapped[ItemState] = mapped_column(
        SAEnum(ItemState, name="item_state"),
        nullable=False,
        default=ItemState.PREPARED,
        server_default=ItemState.PREPARED.value,
    )
    created_at: Mapped[datetime] = _created_at()

    batch: Mapped[RecipeBatch] = relationship(back_populates="portions")
    meal_logs: Mapped[list[MealLog]] = relationship(back_populates="portion")


class MealLog(Base):
    """An immutable record that a portion was eaten. Never deleted; voided.

    Macros are snapshotted at log time so that a later correction upstream
    cannot silently rewrite history.

    Idempotency (REQ-6.4) is enforced by a unique partial index on
    `(portion_id) WHERE voided = false`, created by hand in the migration --
    Alembic does not autogenerate partial indexes. Voiding a log frees the
    portion to be logged again, which is what makes correction-by-voice
    possible without an undo button.
    """

    __tablename__ = "meal_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portion_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("portions.id", ondelete="CASCADE"), nullable=False
    )
    calories_at_log: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g_at_log: Mapped[float] = mapped_column(Float, nullable=False)
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    logged_at: Mapped[datetime] = _created_at()
    voided: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    portion: Mapped[Portion] = relationship(back_populates="meal_logs")


#: Name of the partial unique index created by hand in the initial migration.
MEAL_LOG_ACTIVE_PORTION_INDEX = "uq_meal_logs_active_portion"
