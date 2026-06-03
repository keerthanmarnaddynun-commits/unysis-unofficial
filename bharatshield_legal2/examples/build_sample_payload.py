"""Generate sample_payload.json from shared dummy_data module."""
import json
from pathlib import Path

from dummy_data import build_dummy_payload_dict

payload = build_dummy_payload_dict(
    politician_name="Shri Example Politician",
    role="active_candidate",
    party_affiliation="Example Party",
    constituency="Example Constituency",
)

out = Path(__file__).parent / "sample_payload.json"
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"Wrote {out}")
