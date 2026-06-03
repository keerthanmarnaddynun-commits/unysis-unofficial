"""Module 3: Rule-based legal decision engine."""

from __future__ import annotations

import logging

from schemas import (
    AcousticForensics,
    DeepfakeExplanation,
    LegalCaseType,
    LegalRoutingDecision,
    ResolvedIdentity,
    RiskIndicators,
    StatutoryCharge,
    VisualForensics,
)

logger = logging.getLogger(__name__)


def _subject_name(identity: ResolvedIdentity) -> str:
    return identity.display_name or (identity.profile.full_name if identity.profile else "Unknown")


class LegalDecisionEngine:
    """Routes document pipeline based on identity and forensic metrics."""

    def _append_explanation(self, base: str, explanation: DeepfakeExplanation | None) -> str:
        if not explanation or not explanation.findings:
            return base
        snippets = "; ".join(f.plain_language[:100] for f in explanation.findings[:3])
        return f"{base} Deepfake grounds: {snippets}"

    def evaluate(
        self,
        identity: ResolvedIdentity,
        visual: VisualForensics,
        acoustic: AcousticForensics,
        risk: RiskIndicators,
        explanation: DeepfakeExplanation | None = None,
    ) -> LegalRoutingDecision:
        if not identity.matched:
            return self._unresolved_route(visual, acoustic, risk, explanation)

        if identity.is_eci_official:
            return self._case_a_eci_official(identity, visual, acoustic, explanation)

        if identity.electoral and identity.electoral.active_candidacy_mcc:
            return self._case_b_active_candidate(identity, visual, acoustic, explanation)

        return self._case_c_general_public(identity, visual, acoustic, risk, explanation)

    def _case_a_eci_official(
        self,
        identity: ResolvedIdentity,
        visual: VisualForensics,
        acoustic: AcousticForensics,
        explanation: DeepfakeExplanation | None = None,
    ) -> LegalRoutingDecision:
        charges = [
            StatutoryCharge(
                statute="Model Code of Conduct",
                section="—",
                description="Violation of Model Code of Conduct during election period",
            ),
            StatutoryCharge(
                statute="Constitution of India",
                section="Article 324",
                description="Obstruction of constitutional election duties of the Election Commission",
            ),
            StatutoryCharge(
                statute="Bharatiya Nyaya Sanhita, 2023",
                section="319",
                description="Cheating by personation using synthetically generated impersonation",
            ),
        ]
        return LegalRoutingDecision(
            case_type=LegalCaseType.ECI_OFFICIAL,
            charges=charges,
            documents_to_generate=[
                "bsa_section_63_part_a",
                "bsa_section_63_part_b",
                "eci_contempt_notice_art_324",
                "it_rules_2026_intermediary_takedown_3h",
            ],
            takedown_hours=3,
            routing_rationale=self._append_explanation(
                (
                    f"Target identified as ECI official ({_subject_name(identity)}). "
                    f"Forensic manipulation probability: visual={visual.spatial_cnn_manipulation_probability:.2%}, "
                    f"acoustic TTS={acoustic.tts_synthetic_probability:.2%}."
                ),
                explanation,
            ),
        )

    def _case_b_active_candidate(
        self,
        identity: ResolvedIdentity,
        visual: VisualForensics,
        acoustic: AcousticForensics,
        explanation: DeepfakeExplanation | None = None,
    ) -> LegalRoutingDecision:
        constituency = identity.electoral.constituency if identity.electoral else "N/A"
        charges = [
            StatutoryCharge(
                statute="Representation of the People Act, 1951",
                section="123(4)",
                description="Corrupt practice to prejudice an election through false statements",
            ),
            StatutoryCharge(
                statute="Bharatiya Nyaya Sanhita, 2023",
                section="356",
                description="Criminal defamation through morphed/synthetic media",
            ),
            StatutoryCharge(
                statute="Bharatiya Nyaya Sanhita, 2023",
                section="336",
                description="Forgery of electronic records to cheat",
            ),
        ]
        return LegalRoutingDecision(
            case_type=LegalCaseType.ACTIVE_CANDIDATE,
            charges=charges,
            documents_to_generate=[
                "bsa_section_63_part_a",
                "bsa_section_63_part_b",
                "rpa_eci_corrupt_practice_complaint",
                "it_rules_2026_intermediary_takedown_3h",
                "draft_fir_bns",
            ],
            takedown_hours=3,
            routing_rationale=self._append_explanation(
                (
                    f"Active electoral candidate under MCC in {constituency} ({_subject_name(identity)}). "
                    f"Deepfake indicators exceed evidentiary threshold."
                ),
                explanation,
            ),
        )

    def _case_c_general_public(
        self,
        identity: ResolvedIdentity,
        visual: VisualForensics,
        acoustic: AcousticForensics,
        risk: RiskIndicators,
        explanation: DeepfakeExplanation | None = None,
    ) -> LegalRoutingDecision:
        urgent_ncii = risk.ncii_indicator or risk.sexual_harassment_indicator
        takedown_hours = 2 if urgent_ncii else 3

        docs = [
            "bsa_section_63_part_a",
            "bsa_section_63_part_b",
            "cyber_crime_fir_bns",
        ]
        if urgent_ncii:
            docs.append("it_rules_2026_intermediary_takedown_2h")
        else:
            docs.append("it_rules_2026_intermediary_takedown_3h")

        charges = [
            StatutoryCharge(
                statute="Bharatiya Nyaya Sanhita, 2023",
                section="319",
                description="Cheating by personation",
            ),
            StatutoryCharge(
                statute="Bharatiya Nyaya Sanhita, 2023",
                section="336",
                description="Forgery of electronic records",
            ),
            StatutoryCharge(
                statute="Bharatiya Nyaya Sanhita, 2023",
                section="356",
                description="Criminal defamation",
            ),
        ]
        rationale = (
            f"General political/public figure ({_subject_name(identity)}) — "
            "standard cyber crime and intermediary notices."
        )
        if urgent_ncii:
            rationale += " URGENT: NCII / sexual harassment indicators — 2-hour takedown window applied."

        return LegalRoutingDecision(
            case_type=LegalCaseType.GENERAL_PUBLIC_FIGURE,
            charges=charges,
            documents_to_generate=docs,
            takedown_hours=takedown_hours,
            routing_rationale=self._append_explanation(rationale, explanation),
        )

    def _unresolved_route(
        self,
        visual: VisualForensics,
        acoustic: AcousticForensics,
        risk: RiskIndicators,
        explanation: DeepfakeExplanation | None = None,
    ) -> LegalRoutingDecision:
        urgent_ncii = risk.ncii_indicator or risk.sexual_harassment_indicator
        takedown_hours = 2 if urgent_ncii else 3
        return LegalRoutingDecision(
            case_type=LegalCaseType.UNRESOLVED_IDENTITY,
            charges=[
                StatutoryCharge(
                    statute="Bharatiya Nyaya Sanhita, 2023",
                    section="336",
                    description="Forgery of electronic records (identity unresolved)",
                ),
            ],
            documents_to_generate=[
                "bsa_section_63_part_a",
                "bsa_section_63_part_b",
                "cyber_crime_fir_bns",
                f"it_rules_2026_intermediary_takedown_{takedown_hours}h",
            ],
            takedown_hours=takedown_hours,
            routing_rationale=self._append_explanation(
                "Biometric identity below similarity threshold — generic cyber crime package.",
                explanation,
            ),
        )
