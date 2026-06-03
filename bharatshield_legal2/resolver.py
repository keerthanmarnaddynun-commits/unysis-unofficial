"""Module 2: Biometric identity resolution via Qdrant."""

from __future__ import annotations

import logging
import math
from typing import Any

from config import settings
from schemas import (
    BiometricEmbeddings,
    ElectoralContext,
    ProfileDetails,
    ResolvedIdentity,
)

logger = logging.getLogger(__name__)


def cosine_similarity(q: list[float], d: list[float]) -> float:
    """Cosine similarity between query q and database vector d."""
    if len(q) != len(d):
        raise ValueError(f"Dimension mismatch: {len(q)} vs {len(d)}")
    dot = sum(qi * di for qi, di in zip(q, d))
    norm_q = math.sqrt(sum(qi * qi for qi in q))
    norm_d = math.sqrt(sum(di * di for di in d))
    if norm_q == 0 or norm_d == 0:
        return 0.0
    return dot / (norm_q * norm_d)


def selfi_fuse_identity(
    phi_id: list[float],
    phi_vis: list[float],
    synthetic_confidence: float,
    w_id: float | None = None,
    w_vis: float | None = None,
) -> list[float]:
    """
    SELFI (Forgery-Aware Identity Adapter) fusion:
    F_fused = w_id * Phi_id + w_vis * Phi_vis
    Weights shift toward visual when synthetic confidence is high.
    """
    w_id = w_id if w_id is not None else settings.fusion_identity_weight
    w_vis = w_vis if w_vis is not None else settings.fusion_visual_weight
    # Increase visual weight under high synthetic manipulation
    adj_vis = w_vis + (synthetic_confidence * 0.3)
    adj_id = max(0.1, 1.0 - adj_vis)
    total = adj_id + adj_vis
    adj_id, adj_vis = adj_id / total, adj_vis / total
    n = min(len(phi_id), len(phi_vis))
    return [adj_id * phi_id[i] + adj_vis * phi_vis[i] for i in range(n)]


# Mock reference database for development / when Qdrant is unavailable
_MOCK_FIGURES: list[dict[str, Any]] = [
    {
        "id": "eci-official-001",
        "face": [0.01] * 511 + [1.0],
        "voice": [0.02] * 255 + [0.9],
        "profile": {"full_name": "Rajesh Kumar Mehta", "aadhaar_masked": "XXXX-XXXX-4521", "gender": "Male"},
        "electoral": {
            "party_affiliation": None,
            "active_candidacy_mcc": False,
            "constituency": None,
            "role": "Deputy Election Commissioner",
        },
        "is_eci_official": True,
    },
    {
        "id": "candidate-042",
        "face": [0.03] * 512,
        "voice": [0.04] * 256,
        "profile": {"full_name": "Priya Sharma", "aadhaar_masked": "XXXX-XXXX-7890", "gender": "Female"},
        "electoral": {
            "party_affiliation": "National Democratic Alliance",
            "active_candidacy_mcc": True,
            "constituency": "Mumbai North",
            "role": "Lok Sabha Candidate",
        },
        "is_eci_official": False,
    },
    {
        "id": "public-figure-108",
        "face": [0.05] * 512,
        "voice": [0.06] * 256,
        "profile": {"full_name": "Amit Verma", "aadhaar_masked": "XXXX-XXXX-3344", "gender": "Male"},
        "electoral": {
            "party_affiliation": "Independent",
            "active_candidacy_mcc": False,
            "constituency": None,
            "role": "Public Figure / Commentator",
        },
        "is_eci_official": False,
    },
]


class BiometricContextResolver:
    """Resolves target identity from ArcFace + ECAPA embeddings via Qdrant."""

    def __init__(self) -> None:
        self._client = None
        self._use_mock = settings.qdrant_mock

    async def _get_client(self):
        if self._use_mock:
            return None
        if self._client is None:
            try:
                from qdrant_client import AsyncQdrantClient

                self._client = AsyncQdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key,
                )
            except Exception as exc:
                logger.warning("Qdrant unavailable, using mock resolver: %s", exc)
                self._use_mock = True
        return self._client

    async def _query_collection(
        self,
        collection: str,
        vector: list[float],
        limit: int = 5,
    ) -> list[tuple[str, float, dict]]:
        client = await self._get_client()
        if client is None:
            return self._mock_query(collection, vector, limit)

        try:
            results = await client.search(
                collection_name=collection,
                query_vector=vector,
                limit=limit,
                with_payload=True,
            )
            out: list[tuple[str, float, dict]] = []
            for hit in results:
                payload = hit.payload or {}
                out.append((str(hit.id), float(hit.score), payload))
            return out
        except Exception as exc:
            logger.error("Qdrant search failed on %s: %s", collection, exc)
            return self._mock_query(collection, vector, limit)

    def _mock_query(
        self,
        collection: str,
        vector: list[float],
        limit: int,
    ) -> list[tuple[str, float, dict]]:
        results: list[tuple[str, float, dict]] = []
        for fig in _MOCK_FIGURES:
            ref = fig["face"] if "face" in collection else fig["voice"]
            score = cosine_similarity(vector, ref)
            payload = {
                "identity_id": fig["id"],
                "profile": fig["profile"],
                "electoral": fig["electoral"],
                "is_eci_official": fig["is_eci_official"],
            }
            results.append((fig["id"], score, payload))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def resolve(
        self,
        biometrics: BiometricEmbeddings,
        synthetic_confidence: float = 0.5,
    ) -> ResolvedIdentity:
        face_hits = await self._query_collection(
            settings.qdrant_face_collection,
            biometrics.arcface_visual_embedding,
        )
        voice_hits = await self._query_collection(
            settings.qdrant_voice_collection,
            biometrics.ecapa_voiceprint_embedding,
        )

        best_face = face_hits[0] if face_hits else None
        best_voice = voice_hits[0] if voice_hits else None

        face_score = best_face[1] if best_face else 0.0
        voice_score = best_voice[1] if best_voice else 0.0

        # Prefer identity with highest combined score
        candidates: dict[str, dict] = {}
        for _id, score, payload in face_hits + voice_hits:
            iid = payload.get("identity_id", _id)
            if iid not in candidates:
                candidates[iid] = {"face": 0.0, "voice": 0.0, "payload": payload}
            if score == face_score and _id == (best_face[0] if best_face else None):
                candidates[iid]["face"] = max(candidates[iid]["face"], score)
            if score == voice_score and _id == (best_voice[0] if best_voice else None):
                candidates[iid]["voice"] = max(candidates[iid]["voice"], score)

        if best_face:
            iid = best_face[2].get("identity_id", best_face[0])
            candidates.setdefault(iid, {"face": 0.0, "voice": 0.0, "payload": best_face[2]})
            candidates[iid]["face"] = face_score
            candidates[iid]["payload"] = best_face[2]
        if best_voice:
            iid = best_voice[2].get("identity_id", best_voice[0])
            candidates.setdefault(iid, {"face": 0.0, "voice": 0.0, "payload": best_voice[2]})
            candidates[iid]["voice"] = voice_score
            if not candidates[iid]["payload"]:
                candidates[iid]["payload"] = best_voice[2]

        threshold = settings.similarity_threshold
        best_iid: str | None = None
        best_combined = 0.0
        for iid, data in candidates.items():
            combined = (data["face"] + data["voice"]) / 2.0
            if combined > best_combined:
                best_combined = combined
                best_iid = iid

        if best_iid is None or best_combined < threshold:
            return ResolvedIdentity(matched=False)

        payload = candidates[best_iid]["payload"]
        profile_raw = payload.get("profile", {})
        electoral_raw = payload.get("electoral", {})

        return ResolvedIdentity(
            matched=True,
            cosine_similarity_face=face_score if face_score >= threshold else None,
            cosine_similarity_voice=voice_score if voice_score >= threshold else None,
            fused_similarity=best_combined,
            profile=ProfileDetails(**profile_raw) if profile_raw else None,
            electoral=ElectoralContext(**electoral_raw) if electoral_raw else None,
            is_eci_official=bool(payload.get("is_eci_official", False)),
            identity_id=best_iid,
        )
