"""
SQLAlchemy models matching the research database schema defined in
Data Architecture Spec v0.2.

No PII fields. No operational fields (is_volunteer, email_consent excluded per spec).
All models use pseudo_id as the primary identifier.
"""

from datetime import datetime
from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, SmallInteger,
    String, Text, TIMESTAMP, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
import uuid


class Base(DeclarativeBase):
    pass


class ImportBatch(Base):
    __tablename__ = "import_batches"

    batch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imported_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    imported_by = Column(Text, nullable=False)       # Entra ID object ID — never a real name
    source_filename = Column(Text, nullable=False)
    total_records = Column(Integer, nullable=False)
    imported_records = Column(Integer, nullable=False)
    skipped_records = Column(Integer, nullable=False)
    rejected_records = Column(Integer, nullable=False)
    notes = Column(Text)

    members_first_seen = relationship("Member", foreign_keys="Member.first_seen_batch", back_populates="first_batch")
    members_last_updated = relationship("Member", foreign_keys="Member.last_updated_batch", back_populates="last_batch")


class Member(Base):
    __tablename__ = "members"

    pseudo_id = Column(Text, primary_key=True)          # HMAC-SHA256 derived — see spec Section 5
    age_band = Column(Text)                              # e.g. '30_39', 'under_18', None
    gender = Column(Text)                                # 'male', 'female', None
    country = Column(Text, nullable=False)
    region = Column(Text)
    outward_code = Column(Text)                          # Outward postcode only
    member_since_year = Column(SmallInteger)             # Year only — no full date
    referral_source = Column(ARRAY(Text))                # Structured values only

    first_seen_batch = Column(UUID(as_uuid=True), ForeignKey("import_batches.batch_id"), nullable=False)
    last_updated_batch = Column(UUID(as_uuid=True), ForeignKey("import_batches.batch_id"), nullable=False)

    first_batch = relationship("ImportBatch", foreign_keys=[first_seen_batch], back_populates="members_first_seen")
    last_batch = relationship("ImportBatch", foreign_keys=[last_updated_batch], back_populates="members_last_updated")

    statuses = relationship("MemberStatus", back_populates="member", cascade="all, delete-orphan")
    leak_types = relationship("CSFLeakType", back_populates="member", cascade="all, delete-orphan")
    causes = relationship("CauseOfLeak", back_populates="member", cascade="all, delete-orphan")


class MemberStatus(Base):
    __tablename__ = "member_statuses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pseudo_id = Column(Text, ForeignKey("members.pseudo_id"), nullable=False)
    status_value = Column(Text, nullable=False)
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("import_batches.batch_id"), nullable=False)

    __table_args__ = (UniqueConstraint("pseudo_id", "status_value"),)

    member = relationship("Member", back_populates="statuses")

    # Valid values — enforced at pipeline layer, documented here for reference
    VALID_VALUES = frozenset({
        "csfLeakSuffererDiagnosed",
        "csfLeakSuffererSuspected",
        "formerCsfLeakSufferer",
        "familyFriendOfSufferer",
        "medicalProfessional",
        "other",
    })


class CSFLeakType(Base):
    __tablename__ = "csf_leak_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pseudo_id = Column(Text, ForeignKey("members.pseudo_id"), nullable=False)
    leak_type = Column(Text, nullable=False)
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("import_batches.batch_id"), nullable=False)

    __table_args__ = (UniqueConstraint("pseudo_id", "leak_type"),)

    member = relationship("Member", back_populates="leak_types")

    VALID_VALUES = frozenset({
        "spinal", "cranial", "spinalAndCranial", "unknown", "notRelevant",
    })


class CauseOfLeak(Base):
    __tablename__ = "causes_of_leak"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pseudo_id = Column(Text, ForeignKey("members.pseudo_id"), nullable=False)
    cause = Column(Text, nullable=False)
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("import_batches.batch_id"), nullable=False)

    __table_args__ = (UniqueConstraint("pseudo_id", "cause"),)

    member = relationship("Member", back_populates="causes")

    VALID_VALUES = frozenset({
        "spinalSurgery", "cranialSurgery", "lumbarPuncture",
        "epiduralAnaesthesia", "spinalAnaesthesia", "otherIatrogenicCause",
        "ehlersDanlosSyndrome", "marfanSyndrome",
        "otherHeritableDisorderOfConnectiveTissue",
        "idiopathicIntracranialHypertension", "boneSpur",
        "cystTarlovPerineuralMeningeal", "trauma", "other", "unknown",
        "preferNotToSay",
    })


class ErasureRegister(Base):
    """
    Records pseudo_ids that have been erased under GDPR Article 17.

    The import pipeline checks this table before any upsert. If a pseudo_id is
    present here the record is skipped and logged as 'subject_erased'. This
    prevents erased members from re-entering the research DB on future imports.

    See Data Architecture Spec v0.3 Section 6 and 8.
    """

    __tablename__ = "erasure_register"

    pseudo_id = Column(Text, primary_key=True)
    erased_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    erased_by = Column(Text, nullable=False)          # Entra ID object ID of admin who actioned erasure
    erasure_reason = Column(Text)                     # Optional: e.g. 'Article 17 request', 'deceased'
