"""Module 4: Jinja2 document generation and PDF compilation."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, BaseLoader, select_autoescape

from config import settings
from pdf_render import html_to_pdf
from schemas import (
    AcousticForensics,
    DeepfakeExplanation,
    FileMetadata,
    GeneratedDocument,
    LegalRoutingDecision,
    ResolvedIdentity,
    SystemMetadata,
    VisualForensics,
)

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(IST)


def _format_ist(dt: datetime | None = None) -> str:
    dt = dt or _now_ist()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)
    return dt.strftime("%d-%m-%Y %H:%M:%S IST")


def _subject_name(identity: ResolvedIdentity) -> str:
    return identity.display_name or (identity.profile.full_name if identity.profile else "Unknown")


EXPLANATION_GROUNDS_HTML = """
{% if explanation and explanation.findings %}
<h3>Grounds for Deepfake Classification</h3>
<p><strong>Summary:</strong> {{ explanation.summary }}</p>
<ul>
  {% for f in explanation.findings %}
  <li><strong>{{ f.category }} ({{ f.severity.value }}):</strong> {{ f.plain_language }}
      {% if f.metric_ref %}<em>({{ f.metric_ref }}: {{ f.value }})</em>{% endif %}
  </li>
  {% endfor %}
</ul>
{% endif %}
"""

# --- Legal HTML templates (embedded per spec) ---

TEMPLATE_BSA_PART_A = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>Schedule to Section 63 BSA 2023 — Part A</title>
<style>
  body { font-family: 'Times New Roman', serif; font-size: 11pt; margin: 2cm; color: #000; }
  h1 { font-size: 14pt; text-align: center; text-transform: uppercase; }
  h2 { font-size: 12pt; border-bottom: 1px solid #000; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; }
  td, th { border: 1px solid #000; padding: 6px 8px; vertical-align: top; }
  th { background: #f0f0f0; width: 35%; text-align: left; }
  .footer { margin-top: 24px; font-size: 10pt; }
  .sig-line { border-top: 1px solid #000; width: 240px; margin-top: 48px; }
</style>
</head>
<body>
<h1>Schedule to Section 63 of the Bharatiya Sakshya Adhiniyam, 2023</h1>
<h2>Part A — Certificate by Person in Control of Computer / Device (User/Owner Declaration)</h2>
<p>I, the undersigned, being the person in lawful control of the computer resource or electronic device from which the electronic record was produced, hereby certify as follows:</p>
<table>
  <tr><th>1. Full Name of Declarant</th><td>{{ analyst_display_name }}</td></tr>
  <tr><th>2. Analyst / Operator ID</th><td>{{ system.analyst_id }}</td></tr>
  <tr><th>3. Place of Certification</th><td>{{ place }}</td></tr>
  <tr><th>4. Date &amp; Time (IST)</th><td>{{ ist_timestamp }}</td></tr>
  <tr><th>5. Lawful Control Statement</th><td>I affirm that I was in lawful possession and control of the workstation/device identified below at the time of acquisition of the electronic record, and that the record was obtained without alteration of its substantive content.</td></tr>
  <tr><th>6. Workstation Serial No.</th><td>{{ system.workstation_serial_number }}</td></tr>
  <tr><th>7. Terminal MAC Address</th><td>{{ system.terminal_mac_address }}</td></tr>
  <tr><th>8. IMEI / Mobile Identifier (if applicable)</th><td>{{ imei or 'N/A' }}</td></tr>
  <tr><th>9. Original File Name</th><td>{{ file.filename }}</td></tr>
  <tr><th>10. Container Format</th><td>{{ file.container_format }}</td></tr>
  <tr><th>11. File Size (bytes)</th><td>{{ file.file_size_bytes }}</td></tr>
  <tr><th>12. SHA-256 Hash (original)</th><td><code>{{ file.sha256_hash }}</code></td></tr>
  <tr><th>13. Ingestion Timestamp (UTC stored / IST displayed)</th><td>{{ ingestion_ist }}</td></tr>
</table>
<p>I understand that any false statement in this certificate may attract penal consequences under applicable law. This certificate is issued for production of electronic evidence before a Court, Tribunal, or authority in accordance with Section 63 of the Bharatiya Sakshya Adhiniyam, 2023.</p>
<div class="footer">
  <div class="sig-line"></div>
  <p>Signature of Declarant: _________________________ &nbsp; Date: {{ ist_date }}</p>
  <p>Page 1 of 1 | Packet ID: {{ packet_id }}</p>
</div>
</body>
</html>
"""

TEMPLATE_BSA_PART_B = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>Schedule to Section 63 BSA 2023 — Part B</title>
<style>
  body { font-family: 'Times New Roman', serif; font-size: 11pt; margin: 2cm; }
  h1 { font-size: 14pt; text-align: center; text-transform: uppercase; }
  table { width: 100%; border-collapse: collapse; }
  td, th { border: 1px solid #000; padding: 6px; }
  th { background: #f0f0f0; width: 38%; }
</style>
</head>
<body>
<h1>Schedule to Section 63 of the Bharatiya Sakshya Adhiniyam, 2023</h1>
<h2>Part B — Technical Expert Certification (Section 79A, IT Act authorised expert)</h2>
<table>
  <tr><th>Expert Name &amp; Designation</th><td>{{ expert_name }} — Digital Forensic Examiner (Sec 79A IT Act)</td></tr>
  <tr><th>Expert ID / Licence</th><td>{{ expert_id }}</td></tr>
  <tr><th>Verification Workstation Serial</th><td>{{ system.workstation_serial_number }}</td></tr>
  <tr><th>Verification MAC</th><td>{{ system.terminal_mac_address }}</td></tr>
  <tr><th>Independent SHA-256 Confirmation</th><td><code>{{ file.sha256_hash }}</code> (verified match)</td></tr>
  <tr><th>Date &amp; Time of Examination (IST)</th><td>{{ ist_timestamp }}</td></tr>
</table>
<h3>Forensic Analysis Summary</h3>
<p>The electronic record identified above was extracted using write-protected forensic procedures. Structural integrity of the bitstream was preserved. No transcoding or lossy re-encoding was applied during acquisition.</p>
<ul>
  <li>Spatial CNN manipulation probability: <strong>{{ "%.4f"|format(visual.spatial_cnn_manipulation_probability) }}</strong></li>
  <li>3D face mesh landmark variance: <strong>{{ "%.6f"|format(visual.face_mesh_landmark_variance) }}</strong></li>
  <li>Lip-sync alignment error: <strong>{{ "%.2f"|format(visual.lip_sync_alignment_error_ms) }} ms</strong></li>
  <li>TTS synthetic voice probability: <strong>{{ "%.4f"|format(acoustic.tts_synthetic_probability) }}</strong></li>
  <li>Spectrogram pitch mismatch ratio: <strong>{{ "%.4f"|format(acoustic.spectrogram_pitch_mismatch_ratio) }}</strong></li>
  <li>Anti-spoofing NN confidence (bona fide): <strong>{{ "%.4f"|format(acoustic.anti_spoofing_nn_confidence) }}</strong></li>
</ul>
{% if identity.matched or subject_name %}
<p><strong>Resolved Subject:</strong> {{ subject_name }}{% if identity.identity_id %} (ID: {{ identity.identity_id }}{% if identity.fused_similarity %}, fused similarity: {{ "%.4f"|format(identity.fused_similarity) }}{% endif %}){% endif %}
 — source: {{ identity.identity_source.value }}{% if identity.merge_conflicts %} — note: {{ identity.merge_conflicts|join('; ') }}{% endif %}</p>
{% else %}
<p><strong>Resolved Subject:</strong> Not matched above biometric threshold.</p>
{% endif %}
""" + EXPLANATION_GROUNDS_HTML + """
<p>I certify that the above analysis was conducted on the hash-verified original and that the opinions expressed are based on validated multi-modal deepfake detection models.</p>
<div class="sig-line" style="border-top:1px solid #000;width:240px;margin-top:40px;"></div>
<p>Expert Signature: _________________________ &nbsp; Date: {{ ist_date }}</p>
<p>Page 1 of 1 | Packet ID: {{ packet_id }}</p>
</body>
</html>
"""

TEMPLATE_IT_TAKEDOWN = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>IT Amendment Rules 2026 — Intermediary Notice</title>
<style>
  body { font-family: 'Times New Roman', serif; font-size: 11pt; margin: 2cm; }
  .header { text-align: right; } table { border-collapse: collapse; width: 100%; }
  td, th { border: 1px solid #000; padding: 8px; }
</style>
</head>
<body>
<p class="header">Date: {{ ist_date }}<br/>Ref: {{ packet_id }}/IT-Rules-2026</p>
<p><strong>To,</strong><br/>The Grievance Officer / Nodal Compliance Officer<br/>[Intermediary Social Media Platform]<br/>India</p>
<p><strong>Subject:</strong> Statutory Notice for Removal of Synthetically Generated Information — Rule 3(1)(b), IT Amendment Rules, 2026 ({{ takedown_hours }}-Hour Compliance Window)</p>
<p>Sir/Madam,</p>
<p>Under Rule 3(1)(b) of the Information Technology (Intermediary Guidelines and Digital Media Ethics Code) Amendment Rules, 2026, you are hereby notified that the following content hosted on your platform constitutes synthetically generated / morphed information prejudicial to {% if routing.case_type.value == 'case_a_eci_official' %}constitutional election processes{% elif routing.case_type.value == 'case_b_active_candidate' %}free and fair elections{% else %}public order and individual dignity{% endif %}.</p>
<table>
  <tr><th>Content URL / Identifier</th><td>As per annexure hash {{ file.sha256_hash[:16] }}…</td></tr>
  <tr><th>SHA-256 of Media</th><td><code>{{ file.sha256_hash }}</code></td></tr>
  <tr><th>Mandated Removal Window</th><td><strong>{{ takedown_hours }} hours</strong> from service of this notice (deadline: {{ deadline_ist }})</td></tr>
  <tr><th>Applicable Offences</th><td>{% for c in routing.charges %}{{ c.statute }} §{{ c.section }}; {% endfor %}</td></tr>
</table>
<p>Failure to disable access within the stipulated period may attract safe-harbour forfeiture and referral to competent authorities including ECI / Cyber Crime Coordination Centre.</p>
<p>Yours faithfully,<br/><strong>BharatShield Legal Automation</strong><br/>On behalf of the complainant</p>
</body>
</html>
"""

TEMPLATE_ECI_CONTEMPT = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>ECI Contempt Notice — Article 324</title>
<style>body{font-family:'Times New Roman',serif;font-size:11pt;margin:2cm;} h1{text-align:center;font-size:14pt;}</style>
</head>
<body>
<h1>Notice of Contempt / Obstruction — Election Commission of India</h1>
<p><strong>Under:</strong> Article 324 of the Constitution of India; Model Code of Conduct; Bharatiya Nyaya Sanhita §319</p>
<p>The Commission is respectfully informed that synthetically generated media targeting <strong>{{ subject_name }}</strong>, an official performing election duties, has been detected with forensic confidence exceeding evidentiary thresholds.</p>
<p>Requested Action: Immediate regulatory direction, preservation of platform logs, and initiation of contempt proceedings where applicable.</p>
<p>Packet: {{ packet_id }} | Hash: {{ file.sha256_hash }} | {{ ist_timestamp }}</p>
</body>
</html>
"""

TEMPLATE_RPA_COMPLAINT = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>RPA Section 123(4) Complaint</title>
<style>body{font-family:'Times New Roman',serif;margin:2cm;} table{border-collapse:collapse;width:100%;} td,th{border:1px solid #000;padding:6px;}</style>
</head>
<body>
<h1 style="text-align:center;">Complaint under Section 123(4), Representation of the People Act, 1951</h1>
<p><strong>To:</strong> The Election Commission of India, Nirvachan Sadan, New Delhi</p>
<table>
  <tr><th>Impugned Candidate</th><td>{{ subject_name }}</td></tr>
  <tr><th>Constituency</th><td>{{ identity.electoral.constituency or 'N/A' }}</td></tr>
  <tr><th>Party</th><td>{{ identity.electoral.party_affiliation or 'N/A' }}</td></tr>
  <tr><th>Nature of Corrupt Practice</th><td>Publication of deepfake/synthetic audiovisual material to prejudice election outcome</td></tr>
  <tr><th>Evidence Hash</th><td><code>{{ file.sha256_hash }}</code></td></tr>
</table>
<p>Complainant prays for immediate regulatory action, takedown directions, and investigation under RPA and BNS.</p>
<p>Date: {{ ist_date }} | Ref: {{ packet_id }}</p>
</body>
</html>
"""

TEMPLATE_DRAFT_FIR = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>Draft FIR — BNS</title>
<style>body{font-family:'Times New Roman',serif;margin:2cm;font-size:11pt;} table{border-collapse:collapse;width:100%;} td,th{border:1px solid #000;padding:6px;}</style>
</head>
<body>
<h1 style="text-align:center;">DRAFT FIRST INFORMATION REPORT</h1>
<p><strong>Police Station:</strong> _________________________ &nbsp; <strong>District:</strong> _________________________</p>
<table>
  <tr><th>Offences</th><td>{% for c in routing.charges %}{{ c.statute }} Sec {{ c.section }} — {{ c.description }}; {% endfor %}</td></tr>
  <tr><th>Victim / Personated</th><td>{{ subject_name }}</td></tr>
  <tr><th>Electronic Record Hash</th><td><code>{{ file.sha256_hash }}</code></td></tr>
  <tr><th>Forensic Summary</th><td>Multi-modal deepfake detection — visual manip {{ "%.2f"|format(visual.spatial_cnn_manipulation_probability*100) }}%, synthetic voice {{ "%.2f"|format(acoustic.tts_synthetic_probability*100) }}%</td></tr>
</table>
""" + EXPLANATION_GROUNDS_HTML + """
<p>Complainant requests registration of FIR and preservation of intermediary logs under BNSS/BSA procedures.</p>
<p>Date: {{ ist_date }} IST | BharatShield Packet {{ packet_id }}</p>
</body>
</html>
"""

TEMPLATE_CYBER_FIR = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>Cyber Crime FIR</title>
<style>body{font-family:'Times New Roman',serif;margin:2cm;}</style>
</head>
<body>
<h1 style="text-align:center;">Cyber Crime First Information Report (Draft)</h1>
<p>Offences: BNS §319 (Cheating by Personation), §336 (Forgery of electronic records), §356 (Criminal Defamation)</p>
<p>Subject media SHA-256: <code>{{ file.sha256_hash }}</code></p>
<p>Identified / declared person: {{ subject_name }} (source: {{ identity.identity_source.value }})</p>
""" + EXPLANATION_GROUNDS_HTML + """
<p>Filed via BharatShield Legal Pipeline | {{ ist_timestamp }}</p>
</body>
</html>
"""

TEMPLATE_DEEPFAKE_SUMMARY = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>Deepfake Forensic Summary</title>
<style>
  body { font-family: 'Times New Roman', serif; font-size: 11pt; margin: 2cm; }
  h1 { text-align: center; font-size: 14pt; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; }
  td, th { border: 1px solid #000; padding: 8px; text-align: left; }
  th { background: #f0f0f0; width: 28%; }
</style>
</head>
<body>
<h1>Deepfake Forensic Classification Report</h1>
<p><strong>Packet ID:</strong> {{ packet_id }} &nbsp; <strong>Date (IST):</strong> {{ ist_timestamp }}</p>
<p><strong>Subject:</strong> {{ subject_name }}</p>
<p><strong>Media SHA-256:</strong> <code>{{ file.sha256_hash }}</code></p>
<p>{{ explanation.summary }}</p>
<table>
  <tr><th>Category</th><th>Severity</th><th>Finding</th><th>Metric</th></tr>
  {% for f in explanation.findings %}
  <tr>
    <td>{{ f.category }}</td>
    <td>{{ f.severity.value }}</td>
    <td>{{ f.plain_language }}</td>
    <td>{% if f.metric_ref %}{{ f.metric_ref }}: {{ f.value }}{% else %}—{% endif %}</td>
  </tr>
  {% endfor %}
</table>
<p><em>This report is generated for court and authority review under the Bharatiya Sakshya Adhiniyam, 2023 evidentiary framework.</em></p>
</body>
</html>
"""

TEMPLATE_COMPLETE_LEGAL_PACKET = """
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>Complete Legal Evidence Packet</title>
<style>
  body { font-family: 'Times New Roman', serif; font-size: 11pt; margin: 1.5cm; }
  h1 { text-align: center; font-size: 16pt; page-break-after: avoid; }
  h2 { font-size: 13pt; border-bottom: 2px solid #000; margin-top: 20px; page-break-after: avoid; }
  h3 { font-size: 11pt; margin-top: 14px; }
  table { width: 100%; border-collapse: collapse; margin: 10px 0; }
  td, th { border: 1px solid #000; padding: 6px; vertical-align: top; font-size: 10pt; }
  th { background: #e8e8e8; width: 32%; }
  .cover { text-align: center; margin: 40px 0; }
  .page-break { page-break-before: always; }
  ul { margin: 8px 0 8px 20px; }
</style>
</head>
<body>
<div class="cover">
  <h1>LEGAL EVIDENCE PACKET</h1>
  <p><strong>BharatShield Sovereign Compliance System</strong></p>
  <p>Packet ID: {{ packet_id }}</p>
  <p>Generated: {{ ist_timestamp }}</p>
  <p>Subject: <strong>{{ subject_name }}</strong></p>
  <p>Case classification: {{ routing.case_type.value }}</p>
</div>

<h2>SECTION 1 — Executive Summary</h2>
<p>{{ explanation.summary }}</p>
<p><strong>Legal routing:</strong> {{ routing.routing_rationale }}</p>
<p><strong>Intermediary takedown window:</strong> {{ takedown_hours }} hours (deadline {{ deadline_ist }})</p>

<h2>SECTION 2 — Applicable Statutory Charges</h2>
<table>
  <tr><th>Statute</th><th>Section</th><th>Description</th></tr>
  {% for c in routing.charges %}
  <tr><td>{{ c.statute }}</td><td>{{ c.section }}</td><td>{{ c.description }}</td></tr>
  {% endfor %}
</table>

<h2>SECTION 3 — Electronic Record Identification (BSA 2023)</h2>
<table>
  <tr><th>Original filename</th><td>{{ file.filename }}</td></tr>
  <tr><th>Format</th><td>{{ file.container_format }}</td></tr>
  <tr><th>Size (bytes)</th><td>{{ file.file_size_bytes }}</td></tr>
  <tr><th>SHA-256 hash</th><td><code>{{ file.sha256_hash }}</code></td></tr>
  <tr><th>Workstation serial</th><td>{{ system.workstation_serial_number }}</td></tr>
  <tr><th>Terminal MAC</th><td>{{ system.terminal_mac_address }}</td></tr>
  <tr><th>Analyst ID</th><td>{{ system.analyst_id }}</td></tr>
</table>

<div class="page-break"></div>
<h2>SECTION 4 — Schedule to Section 63, BSA 2023 — Part A (User Declaration)</h2>
<p>I certify lawful control of the device from which the electronic record was produced, without alteration of substantive content, for production under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023.</p>
<table>
  <tr><th>Declarant</th><td>{{ analyst_display_name }}</td></tr>
  <tr><th>Place / Date (IST)</th><td>{{ place }} / {{ ist_timestamp }}</td></tr>
</table>
<p>Signature: _________________________ Date: {{ ist_date }}</p>

<h2>SECTION 5 — Schedule to Section 63, BSA 2023 — Part B (Expert Certification)</h2>
<p>Certified by authorised digital forensic examiner under Section 79A, Information Technology Act.</p>
<table>
  <tr><th>Expert</th><td>{{ expert_name }} ({{ expert_id }})</td></tr>
  <tr><th>Subject identified</th><td>{{ subject_name }} ({{ identity.identity_source.value }})</td></tr>
  <tr><th>Hash verified</th><td><code>{{ file.sha256_hash }}</code></td></tr>
</table>
<h3>Forensic metrics</h3>
<ul>
  <li>Spatial manipulation probability: {{ "%.2f"|format(visual.spatial_cnn_manipulation_probability * 100) }}%</li>
  <li>Lip-sync error: {{ "%.2f"|format(visual.lip_sync_alignment_error_ms) }} ms</li>
  <li>TTS synthetic probability: {{ "%.2f"|format(acoustic.tts_synthetic_probability * 100) }}%</li>
  <li>Anti-spoofing confidence: {{ "%.2f"|format(acoustic.anti_spoofing_nn_confidence * 100) }}%</li>
</ul>
""" + EXPLANATION_GROUNDS_HTML + """
<p>Expert signature: _________________________ Date: {{ ist_date }}</p>

<div class="page-break"></div>
<h2>SECTION 6 — Grounds for Deepfake Classification</h2>
<p>See detailed findings above. This media exhibits indicators consistent with synthetic generation under multi-modal forensic analysis.</p>

<h2>SECTION 7 — Regulatory Notices &amp; Complaints (Summary)</h2>
<p><strong>IT Amendment Rules, 2026:</strong> Intermediary takedown notice required within {{ takedown_hours }} hours under Rule 3(1)(b).</p>
{% if routing.case_type.value == 'case_b_active_candidate' %}
<p><strong>RPA 1951:</strong> Complaint under Section 123(4) for corrupt practice to prejudice election regarding {{ subject_name }}.</p>
<p><strong>Draft FIR:</strong> Offences under BNS §319, §336, §356 recommended for registration.</p>
{% elif routing.case_type.value == 'case_a_eci_official' %}
<p><strong>ECI:</strong> Contempt/obstruction notice under Article 324 regarding targeting an election official.</p>
{% else %}
<p><strong>Cyber crime:</strong> FIR recommended under BNS for cheating by personation, forgery, and defamation.</p>
{% endif %}

<h2>SECTION 8 — Chain of Custody Statement</h2>
<p>The original electronic record, forensic analysis outputs, and this compiled packet are sealed with cryptographic hashes. Any alteration invalidates the bundle hash recorded in the audit log and eSakshya metadata.</p>
<p><em>End of consolidated legal evidence packet — {{ packet_id }}</em></p>
</body>
</html>
"""

DOCUMENT_TEMPLATES: dict[str, str] = {
    "bsa_section_63_part_a": TEMPLATE_BSA_PART_A,
    "bsa_section_63_part_b": TEMPLATE_BSA_PART_B,
    "it_rules_2026_intermediary_takedown_3h": TEMPLATE_IT_TAKEDOWN,
    "it_rules_2026_intermediary_takedown_2h": TEMPLATE_IT_TAKEDOWN,
    "eci_contempt_notice_art_324": TEMPLATE_ECI_CONTEMPT,
    "rpa_eci_corrupt_practice_complaint": TEMPLATE_RPA_COMPLAINT,
    "draft_fir_bns": TEMPLATE_DRAFT_FIR,
    "cyber_crime_fir_bns": TEMPLATE_CYBER_FIR,
    "deepfake_forensic_summary": TEMPLATE_DEEPFAKE_SUMMARY,
    "complete_legal_evidence_packet": TEMPLATE_COMPLETE_LEGAL_PACKET,
}

DOCUMENT_FILENAMES: dict[str, str] = {
    "bsa_section_63_part_a": "BSA_Section63_PartA_User_Declaration.pdf",
    "bsa_section_63_part_b": "BSA_Section63_PartB_Expert_Certification.pdf",
    "it_rules_2026_intermediary_takedown_3h": "IT_Rules_2026_Intermediary_Takedown_3H.pdf",
    "it_rules_2026_intermediary_takedown_2h": "IT_Rules_2026_Intermediary_Takedown_2H.pdf",
    "eci_contempt_notice_art_324": "ECI_Contempt_Notice_Article324.pdf",
    "rpa_eci_corrupt_practice_complaint": "RPA_Section123_4_ECI_Complaint.pdf",
    "draft_fir_bns": "Draft_FIR_BNS.pdf",
    "cyber_crime_fir_bns": "Cyber_Crime_FIR_BNS.pdf",
    "deepfake_forensic_summary": "Deepfake_Forensic_Summary.pdf",
    "complete_legal_evidence_packet": "Complete_Legal_Evidence_Packet.pdf",
}


class DocumentGenerator:
    """Renders Jinja2 HTML templates and compiles to PDF."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def _build_context(
        self,
        packet_id: str,
        system: SystemMetadata,
        file: FileMetadata,
        visual: VisualForensics,
        acoustic: AcousticForensics,
        identity: ResolvedIdentity,
        routing: LegalRoutingDecision,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = _now_ist()
        takedown = routing.takedown_hours
        deadline = now + timedelta(hours=takedown)
        ctx: dict[str, Any] = {
            "packet_id": packet_id,
            "system": system,
            "file": file,
            "visual": visual,
            "acoustic": acoustic,
            "identity": identity,
            "subject_name": _subject_name(identity),
            "routing": routing,
            "ist_timestamp": _format_ist(now),
            "ist_date": now.strftime("%d-%m-%Y"),
            "ingestion_ist": _format_ist(system.ingestion_timestamp),
            "place": "Forensic Analysis Centre, India",
            "analyst_display_name": f"Forensic Analyst ({system.analyst_id})",
            "expert_name": "Dr. Authorized Forensic Examiner",
            "expert_id": "IT-79A-IND-2026-XXXX",
            "imei": None,
            "takedown_hours": takedown,
            "deadline_ist": _format_ist(deadline),
        }
        if extra:
            ctx.update(extra)
        return ctx

    def _html_to_pdf(self, html: str, output_path: Path) -> None:
        html_to_pdf(html, output_path)

    def _sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    async def generate_all(
        self,
        packet_id: str,
        system: SystemMetadata,
        file: FileMetadata,
        visual: VisualForensics,
        acoustic: AcousticForensics,
        identity: ResolvedIdentity,
        routing: LegalRoutingDecision,
        explanation: DeepfakeExplanation | None = None,
    ) -> list[GeneratedDocument]:
        out_dir = settings.output_dir / packet_id / "documents"
        out_dir.mkdir(parents=True, exist_ok=True)
        generated: list[GeneratedDocument] = []
        from schemas import DeepfakeExplanation as DE

        expl = explanation or DE(
            summary="No automated explanation generated.",
            findings=[],
            sources=[],
        )
        ctx = self._build_context(
            packet_id, system, file, visual, acoustic, identity, routing,
            extra={"explanation": expl},
        )

        doc_keys = list(routing.documents_to_generate)
        if explanation and explanation.findings and "deepfake_forensic_summary" not in doc_keys:
            doc_keys.append("deepfake_forensic_summary")
        if "complete_legal_evidence_packet" not in doc_keys:
            doc_keys.insert(0, "complete_legal_evidence_packet")

        for doc_key in doc_keys:
            # Normalize 2h/3h takedown template key
            template_key = doc_key
            if doc_key.startswith("it_rules_2026_intermediary_takedown_") and doc_key not in DOCUMENT_TEMPLATES:
                template_key = (
                    "it_rules_2026_intermediary_takedown_2h"
                    if routing.takedown_hours == 2
                    else "it_rules_2026_intermediary_takedown_3h"
                )

            tpl = DOCUMENT_TEMPLATES.get(template_key)
            if not tpl:
                logger.warning("Unknown document type: %s", doc_key)
                continue

            html = self._env.from_string(tpl).render(**ctx)
            fname = DOCUMENT_FILENAMES.get(template_key, f"{doc_key}.pdf")
            pdf_path = out_dir / fname
            self._html_to_pdf(html, pdf_path)

            generated.append(
                GeneratedDocument(
                    document_type=doc_key,
                    filename=fname,
                    filepath=str(pdf_path),
                    sha256_hash=self._sha256_file(pdf_path),
                )
            )
        return generated
