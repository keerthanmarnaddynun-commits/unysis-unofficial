"""Hybrid merge of biometric identity with user-declared politician target."""

from __future__ import annotations

import logging

from schemas import (
    ElectoralContext,
    IdentitySource,
    ProfileDetails,
    ResolvedIdentity,
    TargetRole,
    UserTargetInput,
)

logger = logging.getLogger(__name__)


def _role_to_flags(role: TargetRole) -> tuple[bool, bool]:
    if role == TargetRole.ECI_OFFICIAL:
        return True, False
    if role == TargetRole.ACTIVE_CANDIDATE:
        return False, True
    return False, False


def _infer_role_from_biometric(identity: ResolvedIdentity) -> TargetRole | None:
    if identity.is_eci_official:
        return TargetRole.ECI_OFFICIAL
    if identity.electoral and identity.electoral.active_candidacy_mcc:
        return TargetRole.ACTIVE_CANDIDATE
    if identity.matched:
        return TargetRole.PUBLIC_FIGURE
    return None


def merge_identity(
    biometric: ResolvedIdentity,
    user: UserTargetInput | None,
) -> ResolvedIdentity:
    """
    Hybrid rules:
    - User politician_name always becomes display_name (and profile.full_name when set).
    - User role / flags drive routing when provided; else biometric.
    - Biometric scores and identity_id preserved when matched.
    """
    if user is None:
        display = biometric.profile.full_name if biometric.profile else None
        return biometric.model_copy(
            update={
                "display_name": display,
                "identity_source": IdentitySource.BIOMETRIC,
                "biometric_matched": biometric.matched,
            }
        )

    conflicts: list[str] = []
    bio_matched = biometric.matched

    # Start from biometric electoral/profile or empty
    profile = biometric.profile
    electoral = biometric.electoral
    is_eci = biometric.is_eci_official
    active_mcc = electoral.active_candidacy_mcc if electoral else False

    # User name always wins for documents
    user_profile = ProfileDetails(
        full_name=user.politician_name,
        aadhaar_masked=profile.aadhaar_masked if profile else "XXXX-XXXX-XXXX",
        gender=user.gender or (profile.gender if profile else "Not specified"),
    )

    # Routing flags from user
    user_eci: bool | None = user.is_eci_official
    user_mcc: bool | None = user.active_candidacy_mcc
    if user.role is not None:
        role_eci, role_mcc = _role_to_flags(user.role)
        user_eci = role_eci if user_eci is None else user_eci
        user_mcc = role_mcc if user_mcc is None else user_mcc

    bio_role = _infer_role_from_biometric(biometric)
    if user.role is not None and bio_role is not None and user.role != bio_role:
        conflicts.append(
            f"User role '{user.role.value}' differs from biometric inference '{bio_role.value}'"
        )

    if user_eci is not None:
        if bio_matched and is_eci != user_eci:
            conflicts.append(
                f"User is_eci_official={user_eci} differs from biometric is_eci_official={is_eci}"
            )
        is_eci = user_eci

    if user_mcc is not None:
        if bio_matched and active_mcc != user_mcc:
            conflicts.append(
                f"User active_candidacy_mcc={user_mcc} differs from biometric={active_mcc}"
            )
        active_mcc = user_mcc

    electoral = ElectoralContext(
        party_affiliation=user.party_affiliation
        or (electoral.party_affiliation if electoral else None),
        active_candidacy_mcc=active_mcc,
        constituency=user.constituency or (electoral.constituency if electoral else None),
        role=user.role.value if user.role else (electoral.role if electoral else None),
    )

    if user.role == TargetRole.ECI_OFFICIAL:
        electoral = ElectoralContext(
            party_affiliation=electoral.party_affiliation,
            active_candidacy_mcc=False,
            constituency=electoral.constituency,
            role="ECI Official",
        )
    elif user.role == TargetRole.ACTIVE_CANDIDATE:
        electoral = ElectoralContext(
            party_affiliation=electoral.party_affiliation,
            active_candidacy_mcc=True,
            constituency=electoral.constituency,
            role=electoral.role or "Electoral Candidate",
        )

    # User-declared with role → treat as matched for routing
    effective_matched = bio_matched or (user.role is not None) or (user_eci is not None) or (user_mcc is not None)

    if bio_matched and user.politician_name != (biometric.profile.full_name if biometric.profile else ""):
        source = IdentitySource.HYBRID
    elif bio_matched:
        source = IdentitySource.HYBRID if conflicts else IdentitySource.BIOMETRIC
    else:
        source = IdentitySource.USER_OVERRIDE

    if conflicts:
        logger.warning("Identity merge conflicts: %s", conflicts)

    return ResolvedIdentity(
        matched=effective_matched,
        cosine_similarity_face=biometric.cosine_similarity_face,
        cosine_similarity_voice=biometric.cosine_similarity_voice,
        fused_similarity=biometric.fused_similarity,
        profile=user_profile,
        electoral=electoral,
        is_eci_official=is_eci,
        identity_id=biometric.identity_id,
        display_name=user.politician_name,
        identity_source=source,
        biometric_matched=bio_matched,
        merge_conflicts=conflicts,
    )
