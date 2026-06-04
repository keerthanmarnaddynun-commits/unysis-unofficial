"""Module 4: ReportLab document generation and PDF compilation."""

from __future__ import annotations

import base64
from datetime import datetime, timezone, timedelta
import hashlib
import logging
import os
from pathlib import Path
import random
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import Flowable

from config import settings
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

# ─────────────────────────────────────────────
# COLOUR PALETTE (formal print-safe from legal_1)
# ─────────────────────────────────────────────
NAVY       = colors.HexColor("#1F1F1F")
ACCENT     = colors.HexColor("#3A3A3A")
LIGHT_BLUE = colors.HexColor("#EFEFEF")
DANGER     = colors.HexColor("#6A1B1B")
SUCCESS    = colors.HexColor("#1E8449")
WARNING    = colors.HexColor("#B7770D")
GRAY_DARK  = colors.HexColor("#202020")
GRAY_MID   = colors.HexColor("#555555")
GRAY_LIGHT = colors.HexColor("#F5F5F5")
WHITE      = colors.white
BLACK      = colors.black

def build_styles():
    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "doc_title":    S("doc_title",    fontName="Times-Bold",   fontSize=16, textColor=NAVY,
                           alignment=TA_CENTER, spaceBefore=2, spaceAfter=6, leading=20),
        "doc_subtitle": S("doc_subtitle", fontName="Times-Roman",        fontSize=10, textColor=GRAY_MID,
                           alignment=TA_CENTER, spaceAfter=14, leading=14),
        "section_head": S("section_head", fontName="Times-Bold",   fontSize=10.5, textColor=NAVY,
                           alignment=TA_LEFT,   spaceBefore=12, spaceAfter=6, borderWidth=0,
                           borderColor=WHITE, leftIndent=0, rightIndent=0),
        "field_label":  S("field_label",  fontName="Times-Bold",   fontSize=8.8, textColor=GRAY_MID,
                           spaceBefore=4, spaceAfter=1),
        "field_value":  S("field_value",  fontName="Times-Roman",        fontSize=10, textColor=GRAY_DARK,
                           spaceAfter=3, leading=14),
        "body":         S("body",         fontName="Times-Roman",        fontSize=10.4, textColor=GRAY_DARK,
                           leading=15.5,  alignment=TA_JUSTIFY,        spaceAfter=7),
        "bullet":       S("bullet",       fontName="Times-Roman",        fontSize=9.9, textColor=GRAY_DARK,
                           leftIndent=16, spaceAfter=4, leading=14.5),
        "verdict_text": S("verdict_text", fontName="Times-Bold",   fontSize=13, textColor=DANGER,
                           alignment=TA_CENTER, spaceBefore=5, spaceAfter=5),
        "footer_text":  S("footer_text",  fontName="Times-Italic",fontSize=8,  textColor=GRAY_MID,
                           alignment=TA_CENTER),
        "mono":         S("mono",         fontName="Courier",          fontSize=8.3, textColor=GRAY_DARK,
                           leading=12.5),
        "warning_box":  S("warning_box",  fontName="Times-Bold",   fontSize=9,  textColor=WARNING,
                           alignment=TA_CENTER),
        "table_header": S("table_header", fontName="Times-Bold",   fontSize=9.2, textColor=WHITE),
        "table_cell":   S("table_cell",   fontName="Times-Roman",        fontSize=9.2, textColor=GRAY_DARK,
                           leading=13.5),
        "ref_num":      S("ref_num",      fontName="Courier-Bold",     fontSize=9.5, textColor=ACCENT),
    }

class HeaderBanner(Flowable):
    """Draws a formal legal-document header block."""
    def __init__(self, doc_type_label, ref_number, classification="RESTRICTED – LAW ENFORCEMENT USE ONLY"):
        super().__init__()
        self.doc_type_label  = doc_type_label
        self.ref_number      = ref_number
        self.classification  = classification
        self.width           = A4[0] - 40*mm
        self.height          = 38*mm

    def draw(self):
        c = self.canv
        w, h = self.width, self.height

        # Outer formal border
        c.setStrokeColor(ACCENT)
        c.setLineWidth(0.8)
        c.rect(0, 0, w, h, stroke=1, fill=0)

        # Top line and government-style heading
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.0)
        c.line(0, h - 8*mm, w, h - 8*mm)

        c.setFillColor(NAVY)
        c.setFont("Times-Bold", 11)
        c.drawString(6*mm, h - 6*mm, "GOVERNMENT OF INDIA")
        c.setFont("Times-Roman", 8.5)
        c.drawString(6*mm, h - 11*mm, "BharatShield National Deepfake Detection and Response Platform")

        c.setFont("Times-Bold", 10)
        c.drawRightString(w - 6*mm, h - 6*mm, self.doc_type_label)
        c.setFont("Courier", 7.5)
        c.drawRightString(w - 6*mm, h - 11*mm, f"Reference No.: {self.ref_number}")

        # Classification row
        c.setStrokeColor(GRAY_MID)
        c.setLineWidth(0.5)
        c.line(0, 8*mm, w, 8*mm)
        c.setFillColor(DANGER)
        c.setFont("Times-Bold", 7.5)
        c.drawCentredString(w / 2, 3.2*mm, self.classification)

def verdict_badge(styles, verdict, score):
    color_map = {"LIKELY SYNTHETIC": DANGER, "UNCERTAIN": WARNING, "LIKELY AUTHENTIC": SUCCESS}
    col = color_map.get(verdict, DANGER)
    data = [[
        Paragraph(f"VERDICT: {verdict}", styles["verdict_text"]),
        Paragraph(f"Fusion Score: {score:.1%}", styles["verdict_text"]),
    ]]
    t = Table(data, colWidths=["60%", "40%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), colors.HexColor("#FBEEEE")),
        ("TEXTCOLOR",    (0,0), (-1,-1), col),
        ("ALIGN",        (0,0), (-1,-1), "CENTER"),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("BOX",          (0,0), (-1,-1), 1.2, col),
        ("ROWPADDING",   (0,0), (-1,-1), 9),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
    ]))
    return t

def kv_table(rows, styles, col_widths=("35%", "65%")):
    """Renders a two-column key-value table."""
    data = [[Paragraph(k, styles["field_label"]),
             Paragraph(str(v), styles["field_value"])] for k, v in rows]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (0,-1), GRAY_LIGHT),
        ("VALIGN",      (0,0), (-1,-1), "TOP"),
        ("GRID",        (0,0), (-1,-1), 0.35, colors.HexColor("#C5CED6")),
        ("ROWPADDING",  (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (0,-1), 8),
        ("LEFTPADDING", (1,0), (1,-1), 10),
        ("RIGHTPADDING",(0,0), (-1,-1), 8),
        ("LINEBELOW",   (0,-1), (-1,-1), 0.5, colors.HexColor("#B7C3CF")),
    ]))
    return t

def section(title, styles):
    return KeepTogether([
        HRFlowable(width="100%", thickness=0.6, color=ACCENT),
        Spacer(1, 1.2*mm),
        Paragraph(f"{title.upper()}", styles["section_head"]),
    ])

def sig_block(name, designation, org, date_str, styles):
    data = [[
        Paragraph(f"<b>{name}</b><br/>{designation}<br/>{org}", styles["field_value"]),
        Paragraph(f"Signature: ___________________________<br/><br/>Date: {date_str}", styles["field_value"]),
    ]]
    t = Table(data, colWidths=["50%", "50%"])
    t.setStyle(TableStyle([
        ("BOX",        (0,0), (-1,-1), 0.5, GRAY_MID),
        ("INNERGRID",  (0,0), (-1,-1), 0.35, colors.HexColor("#D3DAE2")),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("ROWPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",(0,0), (-1,-1), 10),
        ("RIGHTPADDING",(0,0), (-1,-1), 10),
    ]))
    return t

def make_page_template(canvas, doc, case_id):
    canvas.saveState()
    w, h = A4
    # Footer
    canvas.setFont("Times-Roman", 7.5)
    canvas.setFillColor(GRAY_MID)
    canvas.drawString(20*mm, 12*mm,
                      f"BharatShield | Case {case_id} | Restricted circulation")
    canvas.drawRightString(w - 20*mm, 12*mm,
                           f"Page {doc.page} | Generated {datetime.now().strftime('%d %b %Y %H:%M IST')}")
    canvas.setStrokeColor(GRAY_MID)
    canvas.setLineWidth(0.45)
    canvas.line(20*mm, 15*mm, w - 20*mm, 15*mm)
    canvas.restoreState()

def _trim_trailing_pagebreaks(story: list) -> list:
    trimmed_story = list(story)
    while trimmed_story and isinstance(trimmed_story[-1], PageBreak):
        trimmed_story.pop()
    return trimmed_story

# ─────────────────────────────────────────────
# NEW SECTION: Target Person Details
# ─────────────────────────────────────────────
def _person_details_section(identity: ResolvedIdentity, styles: dict) -> list:
    story = [
        section("Resolved Subject Biometrics & Identity Profile", styles),
    ]
    if identity.matched:
        rows = [
            ("Match Status", "RESOLVED / BIOMETRIC MATCH DETECTED"),
            ("Resolved Subject Name", _subject_name(identity)),
            ("Aadhaar Number (Masked)", identity.profile.aadhaar_masked if identity.profile else "N/A"),
            ("Gender", identity.profile.gender if identity.profile else "N/A"),
        ]
        if identity.electoral:
            rows.extend([
                ("Electoral Role", identity.electoral.role or "N/A"),
                ("Constituency", identity.electoral.constituency or "N/A"),
                ("Party Affiliation", identity.electoral.party_affiliation or "N/A"),
                ("Active Candidacy (MCC)", "Yes" if identity.electoral.active_candidacy_mcc else "No"),
            ])
        if identity.cosine_similarity_face:
            rows.append(("Face Cosine Similarity", f"{identity.cosine_similarity_face:.4%}"))
        if identity.cosine_similarity_voice:
            rows.append(("Voice Cosine Similarity", f"{identity.cosine_similarity_voice:.4%}"))
        if identity.fused_similarity:
            rows.append(("Fused Confidence Score", f"{identity.fused_similarity:.4%}"))
        rows.append(("Verification Source", identity.identity_source.value))
    else:
        rows = [
            ("Match Status", "UNRESOLVED / BELOW MATCHING THRESHOLD"),
            ("Identity Source", identity.identity_source.value),
            ("Explanation", "The biometric indicators do not match any registered public figure in the reference database above the threshold.")
        ]
    
    story.append(kv_table(rows, styles))
    story.append(Spacer(1, 4*mm))
    return story

# ─────────────────────────────────────────────
# INDIVIDUAL STORIES BUILDERS
# ─────────────────────────────────────────────

def _get_bsa_part_a_story(packet_id: str, system: SystemMetadata, file: FileMetadata, styles: dict) -> list:
    ref = f"EP-{packet_id[:8]}"
    date_str = datetime.now().strftime("%d %B %Y")
    
    story = [
        HeaderBanner("DIGITAL EVIDENCE CERTIFICATE (PART A)", ref),
        Spacer(1, 8*mm),
        Paragraph("Digital Evidence Certificate (Part A)", styles["doc_title"]),
        Paragraph("Schedule to Section 63 of the Bharatiya Sakshya Adhiniyam, 2023 · Part A", styles["doc_subtitle"]),
        HRFlowable(width="100%", thickness=0.5, color=GRAY_MID),
        Spacer(1, 4*mm),
        
        section("1. Declarant & Workstation Details", styles),
        kv_table([
            ("Full Name of Declarant", f"Forensic Analyst ({system.analyst_id})"),
            ("Analyst / Operator ID", system.analyst_id),
            ("Place of Certification", "Forensic Analysis Centre, India"),
            ("Date & Time (IST)", _format_ist()),
            ("Workstation Serial No.", system.workstation_serial_number),
            ("Terminal MAC Address", system.terminal_mac_address),
        ], styles),
        Spacer(1, 4*mm),
        
        section("2. Electronic Record Identification", styles),
        kv_table([
            ("Original File Name", file.filename),
            ("Container Format", file.container_format),
            ("File Size (bytes)", f"{file.file_size_bytes:,}"),
            ("SHA-256 Hash", file.sha256_hash),
            ("Ingestion Timestamp", _format_ist(system.ingestion_timestamp)),
        ], styles),
        Spacer(1, 4*mm),
        
        section("3. Legal Declaration", styles),
        Paragraph(
            "I, the undersigned, hereby certify that I am the person in lawful control of the "
            "computer resource and digital forensic workstation from which the electronic record "
            "described above was produced. I affirm that the computer resource was operating "
            "properly, and the ingestion and cryptographic hashing of the electronic record "
            "were conducted in the ordinary course of forensic analysis, without any alteration "
            "to its substantive contents. This certificate is issued in accordance with Section 63 "
            "of the Bharatiya Sakshya Adhiniyam, 2023.", styles["body"]
        ),
        Spacer(1, 6*mm),
        
        sig_block(f"Forensic Analyst ({system.analyst_id})", "Declarant / Operator", 
                  "Cyber Forensics Division, BharatShield", date_str, styles),
        PageBreak()
    ]
    return story

def _get_bsa_part_b_story(packet_id: str, system: SystemMetadata, file: FileMetadata, 
                          visual: VisualForensics, acoustic: AcousticForensics, 
                          identity: ResolvedIdentity, explanation: DeepfakeExplanation | None, 
                          styles: dict) -> list:
    ref = f"EP-{packet_id[:8]}"
    date_str = datetime.now().strftime("%d %B %Y")
    
    story = [
        HeaderBanner("TECHNICAL EXPERT CERTIFICATE (PART B)", ref),
        Spacer(1, 8*mm),
        Paragraph("Technical Expert Certificate (Part B)", styles["doc_title"]),
        Paragraph("Schedule to Section 63 of the Bharatiya Sakshya Adhiniyam, 2023 · Part B", styles["doc_subtitle"]),
        HRFlowable(width="100%", thickness=0.5, color=GRAY_MID),
        Spacer(1, 4*mm),
        
        section("1. Technical Expert Details", styles),
        kv_table([
            ("Expert Name & Designation", "Dr. Authorized Forensic Examiner"),
            ("Expert ID / License No.", "IT-79A-IND-2026-XXXX"),
            ("Verification Workstation Serial", system.workstation_serial_number),
            ("Verification MAC Address", system.terminal_mac_address),
            ("Date & Time of Examination (IST)", _format_ist()),
        ], styles),
        Spacer(1, 4*mm),
        
        section("2. Forensic Analysis & Detection Metrics", styles),
        kv_table([
            ("Spatial CNN Manipulation Prob.", f"{visual.spatial_cnn_manipulation_probability:.4%}"),
            ("3D Face Mesh Landmark Variance", f"{visual.face_mesh_landmark_variance:.6f}"),
            ("Lip-sync Alignment Error", f"{visual.lip_sync_alignment_error_ms:.2f} ms"),
            ("TTS Synthetic Voice Probability", f"{acoustic.tts_synthetic_probability:.4%}"),
            ("Spectrogram Pitch Mismatch Ratio", f"{acoustic.spectrogram_pitch_mismatch_ratio:.4%}"),
            ("Anti-spoofing NN Confidence (Bona Fide)", f"{acoustic.anti_spoofing_nn_confidence:.4%}"),
        ], styles),
        Spacer(1, 4*mm),
    ]
    
    # Include details of the person present in the video
    story.extend(_person_details_section(identity, styles))
    
    # Include grounds for deepfake classification (explanation findings)
    story.append(section("3. Grounds for Deepfake Classification", styles))
    if explanation:
        story.append(Paragraph(f"<b>Summary:</b> {explanation.summary}", styles["body"]))
        story.append(Spacer(1, 2*mm))
        for f in explanation.findings:
            story.append(Paragraph(
                f"• <b>{f.category} ({f.severity.value.upper()}):</b> {f.plain_language} "
                f"{f'({f.metric_ref}: {f.value})' if f.metric_ref else ''}",
                styles["bullet"]
            ))
    else:
        story.append(Paragraph("No automated grounds registered.", styles["body"]))
    
    story.extend([
        Spacer(1, 4*mm),
        section("4. Declaration & Sworn Opinion", styles),
        Paragraph(
            "I, Dr. Authorized Forensic Examiner, do hereby certify that the electronic record "
            "described above was subjected to multi-modal deepfake analysis on validated "
            "forensic models. It is my technical opinion, to a high degree of certainty, that "
            "the media exhibits synthetic artifacts characteristic of generative artificial intelligence "
            "impersonation. This certificate is issued under the authority of Section 79A of the "
            "Information Technology Act, 2000 for production as electronic evidence.", styles["body"]
        ),
        Spacer(1, 6*mm),
        sig_block("Dr. Authorized Forensic Examiner", "Digital Forensic Examiner (Sec. 79A IT Act)",
                  "Forensic Analysis Centre, India", date_str, styles),
        PageBreak()
    ])
    return story

def _get_it_rules_takedown_story(packet_id: str, file: FileMetadata, routing: LegalRoutingDecision, 
                                 identity: ResolvedIdentity, styles: dict) -> list:
    ref = f"TDN-{packet_id[:8]}"
    date_str = datetime.now().strftime("%d %B %Y")
    takedown = routing.takedown_hours
    deadline = _format_ist(datetime.now(IST) + timedelta(hours=takedown))
    subject = _subject_name(identity)
    
    story = [
        HeaderBanner("PLATFORM TAKEDOWN NOTICE", ref),
        Spacer(1, 8*mm),
        Paragraph("Platform Takedown Notice", styles["doc_title"]),
        Paragraph("Rule 3(1)(b) of IT Amendment Rules 2026 · Statutory Removal Notice", styles["doc_subtitle"]),
        HRFlowable(width="100%", thickness=0.5, color=GRAY_MID),
        Spacer(1, 4*mm),
        
        kv_table([
            ("To", "Grievance Officer / Nodal Compliance Officer (Social Media Intermediary)"),
            ("Re", "Mandatory Removal of Synthetically Generated / Deepfake Content"),
            ("Date", date_str),
            ("Notice Reference", ref),
            ("Compliance Window", f"Mandatory removal within {takedown} hours (Deadline: {deadline})"),
        ], styles),
        Spacer(1, 4*mm),
        
        section("1. Infringing Content Details", styles),
        kv_table([
            ("Target Person", subject),
            ("Target Person Details", f"Name: {subject} | Source: {identity.identity_source.value}"),
            ("Content Description", f"Morphed/synthetic digital record in filename: {file.filename}"),
            ("SHA-256 of Media File", file.sha256_hash),
        ], styles),
        Spacer(1, 4*mm),
    ]
    
    # Include details of the person present in the video
    story.extend(_person_details_section(identity, styles))
    
    story.extend([
        section("2. Legal Grounds & Applicable Penal Provisions", styles),
        Paragraph(
            f"The content depicted above has been analysed via the BharatShield Deepfake Detection "
            f"Platform and classified as synthetic with high confidence. Under the Information Technology "
            f"Rules and the Bharatiya Nyaya Sanhita, 2023, circulating deepfakes of public figures "
            f"constitutes cheating by personation and forgery. The following charges are applicable:", styles["body"]
        ),
        Spacer(1, 2*mm)
    ])
    
    for c in routing.charges:
        story.append(Paragraph(f"• <b>{c.statute} Sec {c.section}:</b> {c.description}", styles["bullet"]))
        
    story.extend([
        Spacer(1, 4*mm),
        section("3. Action Required from Intermediary", styles),
        Paragraph(
            "Pursuant to Rule 3(1)(b) of the IT Amendment Rules, 2026, you are directed to immediately "
            "disable access to the infringing content within the compliance window, preserve all "
            "associated metadata and upload IP logs for a period of 180 days, and report back compliance "
            "to the Cyber Crime Coordination Centre.", styles["body"]
        ),
        Spacer(1, 6*mm),
        sig_block("BharatShield Legal Automation", "Authorized Compliance Representative",
                  "Ministry of Electronics and IT (MeitY)", date_str, styles),
        PageBreak()
    ])
    return story

def _get_eci_contempt_story(packet_id: str, file: FileMetadata, identity: ResolvedIdentity, styles: dict) -> list:
    ref = f"ECI-{packet_id[:8]}"
    date_str = datetime.now().strftime("%d %B %Y")
    subject = _subject_name(identity)
    
    story = [
        HeaderBanner("ECI CONTEMPT NOTICE", ref, classification="CONFIDENTIAL – ELECTORAL INTEGRITY"),
        Spacer(1, 8*mm),
        Paragraph("Notice of Contempt / Obstruction", styles["doc_title"]),
        Paragraph("Article 324 of the Constitution of India · Model Code of Conduct MCC Violation", styles["doc_subtitle"]),
        HRFlowable(width="100%", thickness=0.5, color=GRAY_MID),
        Spacer(1, 4*mm),
        
        kv_table([
            ("To", "The Election Commission of India (ECI), Nirvachan Sadan, New Delhi"),
            ("Subject", f"Obstruction of Election Official via Deepfake Impersonation: {subject}"),
            ("Date", date_str),
            ("Reference ID", ref),
            ("Primary Evidence Hash", file.sha256_hash),
        ], styles),
        Spacer(1, 4*mm),
        
        section("1. Details of Target Election Official", styles),
    ]
    
    # Include details of the person present in the video
    story.extend(_person_details_section(identity, styles))
    
    story.extend([
        section("2. Summary of Electoral Contempt", styles),
        Paragraph(
            f"It has been detected that a synthetically generated video depicting {subject} has "
            f"been circulated with the intent to disrupt official election duties and damage the "
            f"credibility of the constitutional electoral processes. Under Article 324 and the Model Code "
            f"of Conduct, this represents a deliberate obstruction of ECI operations, warranting "
            f"immediate regulatory blockages and initiation of contempt proceedings.", styles["body"]
        ),
        Spacer(1, 6*mm),
        sig_block("BharatShield Sovereign Compliance System", "ECI Nodal Desk Representative",
                  "Government of India", date_str, styles),
        PageBreak()
    ])
    return story

def _get_rpa_complaint_story(packet_id: str, file: FileMetadata, identity: ResolvedIdentity, styles: dict) -> list:
    ref = f"RPA-{packet_id[:8]}"
    date_str = datetime.now().strftime("%d %B %Y")
    subject = _subject_name(identity)
    
    story = [
        HeaderBanner("RPA SECTION 123(4) COMPLAINT", ref, classification="CONFIDENTIAL – ELECTORAL INTEGRITY"),
        Spacer(1, 8*mm),
        Paragraph("Complaint under Section 123(4), RPA 1951", styles["doc_title"]),
        Paragraph("Representation of the People Act, 1951 · Corrupt Practice Complaint", styles["doc_subtitle"]),
        HRFlowable(width="100%", thickness=0.5, color=GRAY_MID),
        Spacer(1, 4*mm),
        
        kv_table([
            ("To", "The Election Commission of India (ECI), New Delhi"),
            ("Re", "Corrupt Practice (MCC Violation) regarding candidate deepfake"),
            ("Date", date_str),
            ("Reference ID", ref),
            ("Candidate Name", subject),
            ("Electoral Constituency", identity.electoral.constituency if identity.electoral else "N/A"),
            ("Party Affiliation", identity.electoral.party_affiliation if identity.electoral else "N/A"),
            ("Evidence SHA-256", file.sha256_hash),
        ], styles),
        Spacer(1, 4*mm),
        
        section("1. Details of Affected Candidate", styles),
    ]
    
    # Include details of the person present in the video
    story.extend(_person_details_section(identity, styles))
    
    story.extend([
        section("2. Prayer and Relief Sought", styles),
        Paragraph(
            f"The complainant prays that the Commission take immediate regulatory action against the "
            f"unauthorized distribution of deepfakes depicting the candidate {subject}. Such "
            f"actions violate Section 123(4) of the RPA 1951 by publishing false statements in relation "
            f"to candidate conduct. We pray for immediate takedown orders and prosecution of the creators.", styles["body"]
        ),
        Spacer(1, 6*mm),
        sig_block("BharatShield Compliance Officer", "Electoral Misinformation Cell",
                  "Election Commission Liaison Office", date_str, styles),
        PageBreak()
    ])
    return story

def _get_fir_story(packet_id: str, file: FileMetadata, routing: LegalRoutingDecision, 
                   visual: VisualForensics, acoustic: AcousticForensics,
                   identity: ResolvedIdentity, explanation: DeepfakeExplanation | None, 
                   styles: dict) -> list:
    ref = f"FSR-{packet_id[:8]}"
    date_str = datetime.now().strftime("%d %B %Y")
    subject = _subject_name(identity)
    
    story = [
        HeaderBanner("DRAFT FIR SUPPORT REPORT", ref),
        Spacer(1, 8*mm),
        Paragraph("First Information Report (Draft Support)", styles["doc_title"]),
        Paragraph("Evidentiary Report for Registration of FIR · Bharatiya Nyaya Sanhita 2023", styles["doc_subtitle"]),
        HRFlowable(width="100%", thickness=0.5, color=GRAY_MID),
        Spacer(1, 4*mm),
        
        kv_table([
            ("To", "Officer-in-Charge, Cyber Crime Police Station / Local Police Station"),
            ("Victim / Personated", subject),
            ("Electronic Record Hash", file.sha256_hash),
            ("Date", date_str),
            ("Reference Reference", ref),
        ], styles),
        Spacer(1, 4*mm),
        
        section("1. Details of Victim / Personated Subject", styles),
    ]
    
    # Include details of the person present in the video
    story.extend(_person_details_section(identity, styles))
    
    story.extend([
        section("2. Applicable Sections and Offences", styles),
        Paragraph(
            "Based on multi-modal AI verification and statutory rules, the following offences "
            "are disclosed under the Bharatiya Nyaya Sanhita (BNS) 2023 and the Information "
            "Technology Act, 2000:", styles["body"]
        ),
        Spacer(1, 2*mm)
    ])
    
    for c in routing.charges:
        story.append(Paragraph(f"• <b>{c.statute} Sec {c.section}:</b> {c.description}", styles["bullet"]))
        
    story.extend([
        Spacer(1, 4*mm),
        section("3. Forensic Deepfake Analysis Summary", styles),
        kv_table([
            ("Visual Manipulation Probability", f"{visual.spatial_cnn_manipulation_probability:.2%}"),
            ("Voice Synthetic Probability", f"{acoustic.tts_synthetic_probability:.2%}"),
            ("Forensic Recommendation", "Immediate registration of FIR and service of takedown to intermediary"),
        ], styles),
        Spacer(1, 4*mm),
        section("4. Grounds for Deepfake Classification", styles),
    ])
    
    if explanation:
        story.append(Paragraph(f"<b>Summary:</b> {explanation.summary}", styles["body"]))
        story.append(Spacer(1, 2*mm))
        for f in explanation.findings:
            story.append(Paragraph(f"• <b>{f.category} ({f.severity.value.upper()}):</b> {f.plain_language}", styles["bullet"]))
    else:
        story.append(Paragraph("No automated grounds registered.", styles["body"]))
        
    story.extend([
        Spacer(1, 6*mm),
        sig_block("Cyber Crime Nodal Officer", "Technical Investigation Officer",
                  "Cyber Crime Cell, Police Department", date_str, styles),
        PageBreak()
    ])
    return story

def _get_forensic_summary_story(packet_id: str, file: FileMetadata, identity: ResolvedIdentity, 
                                explanation: DeepfakeExplanation | None, styles: dict) -> list:
    ref = f"DFS-{packet_id[:8]}"
    date_str = datetime.now().strftime("%d %B %Y")
    
    story = [
        HeaderBanner("DEEPFAKE FORENSIC SUMMARY", ref),
        Spacer(1, 8*mm),
        Paragraph("Deepfake Forensic Summary Report", styles["doc_title"]),
        Paragraph("BharatShield Multi-Modal Forensic Detection Benchmarks", styles["doc_subtitle"]),
        HRFlowable(width="100%", thickness=0.5, color=GRAY_MID),
        Spacer(1, 4*mm),
        
        section("1. Case Details", styles),
        kv_table([
            ("Packet Reference", ref),
            ("Case Identifier ID", packet_id),
            ("Generated Date", _format_ist()),
            ("Subject Name Depicted", _subject_name(identity)),
            ("Media File SHA-256", file.sha256_hash),
        ], styles),
        Spacer(1, 4*mm),
    ]
    
    # Include details of the person present in the video
    story.extend(_person_details_section(identity, styles))
    
    story.append(section("2. Detailed Findings", styles))
    if explanation:
        story.append(Paragraph(f"<b>Summary:</b> {explanation.summary}", styles["body"]))
        story.append(Spacer(1, 4*mm))
        
        table_data = [[
            Paragraph("Category", styles["table_header"]),
            Paragraph("Severity", styles["table_header"]),
            Paragraph("Finding Details", styles["table_header"]),
            Paragraph("Metric Reference", styles["table_header"]),
        ]]
        for f in explanation.findings:
            table_data.append([
                Paragraph(f.category, styles["table_cell"]),
                Paragraph(f.severity.value.upper(), styles["table_cell"]),
                Paragraph(f.plain_language, styles["table_cell"]),
                Paragraph(f"{f.metric_ref or '—'}: {f.value or '—'}" if f.metric_ref else "—", styles["table_cell"]),
            ])
            
        t = Table(table_data, colWidths=["25%", "15%", "40%", "20%"])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),  (-1,0),  NAVY),
            ("TEXTCOLOR",    (0,0),  (-1,0),  WHITE),
            ("BACKGROUND",   (0,1),  (-1,-1), WHITE),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, GRAY_LIGHT]),
            ("GRID",         (0,0),  (-1,-1), 0.25, colors.HexColor("#BDC3C7")),
            ("VALIGN",       (0,0),  (-1,-1), "TOP"),
            ("ROWPADDING",   (0,0),  (-1,-1), 5),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No forensic findings registered.", styles["body"]))
        
    story.extend([
        Spacer(1, 6*mm),
        sig_block("CDAC Principal Scientist", "Expert Witness Representative",
                  "AI Forensics Division, CDAC", date_str, styles),
        PageBreak()
    ])
    return story

def _get_cover_page_story(packet_id: str, file: FileMetadata, identity: ResolvedIdentity, 
                          routing: LegalRoutingDecision, document_registry: list[tuple[str, str, list]], 
                          styles: dict) -> list:
    date_str = datetime.now().strftime("%d %B %Y, %H:%M:%S IST")
    
    cover = [
        Spacer(1, 20*mm),
        Paragraph("GOVERNMENT OF INDIA", ParagraphStyle("cover_gov", fontName="Times-Bold",
                  fontSize=14, textColor=NAVY, alignment=TA_CENTER, leading=18, spaceAfter=0)),
        Paragraph("BHARATSHIELD", ParagraphStyle("cover_brand", fontName="Times-Bold",
                  fontSize=30, textColor=NAVY, alignment=TA_CENTER, leading=34, spaceAfter=1)),
        Paragraph("National Deepfake Detection and Misinformation Response Platform",
                  ParagraphStyle("cover_sub", fontName="Times-Roman", fontSize=11.5,
                                 textColor=GRAY_MID, alignment=TA_CENTER, spaceAfter=2, leading=14)),
        Spacer(1, 4*mm),
        HRFlowable(width="80%", thickness=2, color=ACCENT, hAlign="CENTER"),
        Spacer(1, 4*mm),
        Paragraph("LEGAL DOCUMENT PACKAGE",
                  ParagraphStyle("cover_type", fontName="Times-Bold", fontSize=19,
                                 textColor=ACCENT, alignment=TA_CENTER, spaceAfter=5, leading=24)),
        Spacer(1, 6*mm),
        Table([[
            Paragraph("Case ID", styles["field_label"]),
            Paragraph(packet_id, styles["ref_num"]),
        ],[
            Paragraph("Generated", styles["field_label"]),
            Paragraph(date_str, styles["field_value"]),
        ],[
            Paragraph("Classification", styles["field_label"]),
            Paragraph("RESTRICTED — LAW ENFORCEMENT USE ONLY",
                      ParagraphStyle("danger_sm", fontName="Times-Bold",
                                     fontSize=9, textColor=DANGER)),
        ]], colWidths=["35%", "65%"],
        style=TableStyle([
            ("BOX",        (0,0), (-1,-1), 0.5, GRAY_MID),
            ("INNERGRID",  (0,0), (-1,-1), 0.25, GRAY_LIGHT),
            ("ROWPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING",(0,0), (0,-1), 10),
            ("BACKGROUND", (0,0), (0,-1), GRAY_LIGHT),
        ])),
        Spacer(1, 7*mm),
        Paragraph("DOCUMENTS INCLUDED",
                  ParagraphStyle("toc_head", fontName="Times-Bold", fontSize=11,
                                 textColor=NAVY, alignment=TA_CENTER, spaceAfter=0.5)),
        Spacer(1, 2*mm),
    ]
    
    # TOC
    toc_rows = []
    for idx, (slug, title, _) in enumerate(document_registry, 1):
        toc_rows.append([str(idx), title, slug.replace("_", " ").title()])
        
    t = Table(toc_rows, colWidths=["6%", "52%", "42%"])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), GRAY_LIGHT),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [GRAY_LIGHT, WHITE]),
        ("GRID",        (0,0), (-1,-1), 0.25, colors.HexColor("#BDC3C7")),
        ("FONTNAME",    (0,0), (-1,-1), "Times-Roman"),
        ("FONTSIZE",    (0,0), (-1,-1), 9),
        ("ROWPADDING",  (0,0), (-1,-1), 6),
        ("FONTNAME",    (1,0), (1,-1), "Times-Bold"),
        ("TEXTCOLOR",   (1,0), (1,-1), NAVY),
        ("TEXTCOLOR",   (2,0), (2,-1), GRAY_MID),
    ]))
    cover.append(t)
    cover.append(PageBreak())
    
    return cover

def _get_complete_evidence_packet_story(packet_id: str, file: FileMetadata, identity: ResolvedIdentity,
                                        routing: LegalRoutingDecision, document_registry: list[tuple[str, str, list]],
                                        explanation: DeepfakeExplanation | None, styles: dict) -> list:
    # Build Cover Page
    story = _get_cover_page_story(packet_id, file, identity, routing, document_registry, styles)
    
    # Section 1: Executive Summary
    story.extend([
        section("SECTION 1 — Executive Summary", styles),
        Paragraph(explanation.summary if explanation else "No automated explanation generated.", styles["body"]),
        Paragraph(f"<b>Legal routing rationale:</b> {routing.routing_rationale}", styles["body"]),
        Paragraph(f"<b>Intermediary takedown window:</b> {routing.takedown_hours} hours (Deadline: {_format_ist(datetime.now(IST) + timedelta(hours=routing.takedown_hours))})", styles["body"]),
        Spacer(1, 4*mm),
    ])
    
    # Section 2: Applicable Statutory Charges
    charge_rows = [["Statute", "Section", "Description"]]
    for c in routing.charges:
        charge_rows.append([c.statute, c.section, c.description])
    
    t_charges = Table(charge_rows, colWidths=["30%", "20%", "50%"])
    t_charges.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),  (-1,0),  NAVY),
        ("TEXTCOLOR",    (0,0),  (-1,0),  WHITE),
        ("GRID",         (0,0),  (-1,-1), 0.25, colors.HexColor("#BDC3C7")),
        ("VALIGN",       (0,0),  (-1,-1), "TOP"),
        ("ROWPADDING",   (0,0),  (-1,-1), 6),
        ("FONTSIZE",     (0,0),  (-1,-1), 9),
    ]))
    story.extend([
        section("SECTION 2 — Applicable Statutory Charges", styles),
        t_charges,
        Spacer(1, 4*mm),
    ])
    
    # Section 3: Electronic Record Identification
    story.extend([
        section("SECTION 3 — Electronic Record Identification (BSA 2023)", styles),
        kv_table([
            ("Original Filename", file.filename),
            ("Container Format", file.container_format),
            ("Size (bytes)", f"{file.file_size_bytes:,}"),
            ("SHA-256 Hash", file.sha256_hash),
        ], styles),
        Spacer(1, 4*mm),
    ])
    
    # Append the stories of the individual documents
    for slug, title, doc_story in document_registry:
        if slug == "complete_legal_evidence_packet":
            continue
        # Trim leading/trailing pagebreaks if any
        trimmed_story = list(doc_story)
        while trimmed_story and isinstance(trimmed_story[-1], PageBreak):
            trimmed_story.pop()
        
        story.extend([
            PageBreak(),
            section(f"SECTION: {title}", styles),
            Spacer(1, 4*mm),
        ])
        story.extend(trimmed_story)
        
    # Section 6: Details of the Person Present in the Video
    story.extend([
        PageBreak(),
        section("SECTION 6 — Details of the Person Present in the Video", styles),
    ])
    story.extend(_person_details_section(identity, styles))
    
    # Section 7: Regulatory notices & complaints
    takedown = routing.takedown_hours
    story.extend([
        section("SECTION 7 — Regulatory Notices & Complaints (Summary)", styles),
        Paragraph(f"<b>IT Amendment Rules, 2026:</b> Intermediary takedown notice required within {takedown} hours under Rule 3(1)(b).", styles["body"]),
    ])
    if routing.case_type.value == 'case_b_active_candidate':
        story.extend([
            Paragraph(f"<b>RPA 1951:</b> Complaint under Section 123(4) for corrupt practice to prejudice election regarding <b>{_subject_name(identity)}</b>.", styles["body"]),
            Paragraph("<b>Draft FIR:</b> Offences under BNS §319, §336, §356 recommended for registration.", styles["body"]),
        ])
    elif routing.case_type.value == 'case_a_eci_official':
        story.extend([
            Paragraph(f"<b>ECI:</b> Contempt/obstruction notice under Article 324 regarding targeting an election official (<b>{_subject_name(identity)}</b>).", styles["body"]),
        ])
    else:
        story.extend([
            Paragraph("<b>Cyber crime:</b> FIR recommended under BNS for cheating by personation, forgery, and defamation.", styles["body"]),
        ])
    story.append(Spacer(1, 4*mm))
    
    # Section 8: Chain of Custody / Integrity Statement
    story.extend([
        section("SECTION 8 — Chain of Custody & Integrity Statement", styles),
        Paragraph(
            "The original electronic record, forensic analysis outputs, and this compiled packet "
            "are sealed with cryptographic hashes. Any alteration invalidates the bundle hash. "
            "This log certifies that the digital evidence identified above has remained in an "
            "unaltered state from the point of initial capture to the present, satisfying electronic "
            "evidence admissibility requirements under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023.", styles["body"]
        ),
        Spacer(1, 4*mm),
    ])
    
    return story

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
    """Renders ReportLab Flowables directly and compiles to PDF."""

    def __init__(self) -> None:
        pass

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
        
        doc_keys = list(routing.documents_to_generate)
        if explanation and explanation.findings and "deepfake_forensic_summary" not in doc_keys:
            doc_keys.append("deepfake_forensic_summary")
        if "complete_legal_evidence_packet" not in doc_keys:
            doc_keys.insert(0, "complete_legal_evidence_packet")
            
        styles = build_styles()
        
        # Build individual document stories
        individual_stories = {}
        
        if "bsa_section_63_part_a" in doc_keys:
            individual_stories["bsa_section_63_part_a"] = (
                "BSA Section 63 Part A User Declaration",
                _get_bsa_part_a_story(packet_id, system, file, styles)
            )
        if "bsa_section_63_part_b" in doc_keys:
            individual_stories["bsa_section_63_part_b"] = (
                "BSA Section 63 Part B Expert Certification",
                _get_bsa_part_b_story(packet_id, system, file, visual, acoustic, identity, explanation, styles)
            )
        if "it_rules_2026_intermediary_takedown_3h" in doc_keys:
            individual_stories["it_rules_2026_intermediary_takedown_3h"] = (
                "IT Rules 2026 Intermediary Takedown 3H Notice",
                _get_it_rules_takedown_story(packet_id, file, routing, identity, styles)
            )
        if "it_rules_2026_intermediary_takedown_2h" in doc_keys:
            individual_stories["it_rules_2026_intermediary_takedown_2h"] = (
                "IT Rules 2026 Intermediary Takedown 2H Notice",
                _get_it_rules_takedown_story(packet_id, file, routing, identity, styles)
            )
        if "eci_contempt_notice_art_324" in doc_keys:
            individual_stories["eci_contempt_notice_art_324"] = (
                "ECI Contempt Notice Article 324",
                _get_eci_contempt_story(packet_id, file, identity, styles)
            )
        if "rpa_eci_corrupt_practice_complaint" in doc_keys:
            individual_stories["rpa_eci_corrupt_practice_complaint"] = (
                "RPA Section 123(4) ECI Complaint",
                _get_rpa_complaint_story(packet_id, file, identity, styles)
            )
        if "draft_fir_bns" in doc_keys:
            individual_stories["draft_fir_bns"] = (
                "Draft FIR BNS Evidentiary Report",
                _get_fir_story(packet_id, file, routing, visual, acoustic, identity, explanation, styles)
            )
        if "cyber_crime_fir_bns" in doc_keys:
            individual_stories["cyber_crime_fir_bns"] = (
                "Cyber Crime FIR BNS Support Report",
                _get_fir_story(packet_id, file, routing, visual, acoustic, identity, explanation, styles)
            )
        if "deepfake_forensic_summary" in doc_keys:
            individual_stories["deepfake_forensic_summary"] = (
                "Deepfake Forensic Summary Report",
                _get_forensic_summary_story(packet_id, file, identity, explanation, styles)
            )
            
        # Build registries for complete evidence packet assembly
        registry = []
        for k in doc_keys:
            if k == "complete_legal_evidence_packet":
                continue
            if k in individual_stories:
                title, story = individual_stories[k]
                registry.append((k, title, story))
                
        # Now complete packet story
        if "complete_legal_evidence_packet" in doc_keys:
            individual_stories["complete_legal_evidence_packet"] = (
                "Complete Legal Evidence Packet",
                _get_complete_evidence_packet_story(packet_id, file, identity, routing, registry, explanation, styles)
            )
            
        generated: list[GeneratedDocument] = []
        
        for doc_key in doc_keys:
            if doc_key not in individual_stories:
                logger.warning("Unknown document type requested: %s", doc_key)
                continue
                
            title, story = individual_stories[doc_key]
            fname = DOCUMENT_FILENAMES.get(doc_key, f"{doc_key}.pdf")
            pdf_path = out_dir / fname
            
            # Compile PDF using ReportLab SimpleDocTemplate
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                leftMargin=20*mm, rightMargin=20*mm,
                topMargin=18*mm,  bottomMargin=22*mm,
                title=f"{title} — {packet_id[:8]}",
                author="BharatShield Platform",
                subject="Deepfake Detection Legal Documents",
            )
            
            single_story = _trim_trailing_pagebreaks(story)
            doc.build(
                single_story,
                onFirstPage=lambda c, d: make_page_template(c, d, packet_id[:8]),
                onLaterPages=lambda c, d: make_page_template(c, d, packet_id[:8])
            )
            
            generated.append(
                GeneratedDocument(
                    document_type=doc_key,
                    filename=fname,
                    filepath=str(pdf_path),
                    sha256_hash=self._sha256_file(pdf_path),
                )
            )
            
        return generated
