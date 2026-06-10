import os
import datetime
from pathlib import Path
from fpdf import FPDF
from typing import Dict, Any

class ForensicReportPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_auto_page_break(auto=True, margin=15)
        
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.set_text_color(0, 51, 102)
        self.cell(0, 10, 'BharatShield - Forensic Video Analysis Report', 0, 1, 'C')
        self.set_draw_color(0, 51, 102)
        self.set_line_width(0.5)
        self.line(10, 22, 200, 22)
        self.ln(10)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        disclaimer = "Disclaimer: This report provides AI-assisted analysis and should be used as supporting evidence rather than definitive proof."
        self.cell(0, 10, disclaimer, 0, 0, 'C')

def get_evidence_summary(evidence_type: str, score: float):
    pct = round(score * 100)
    if pct >= 95:
        confidence = "Very High"
    elif pct >= 90:
        confidence = "High"
    elif pct >= 75:
        confidence = "Moderate"
    else:
        confidence = "Low"

    signals = []
    assessment = ""
    
    if evidence_type == "Strong Multi-Model Agreement":
        signals = ["CNN Detector", "Frequency Detector"]
        assessment = "Multiple independent detection methods identified suspicious patterns in this frame."
    elif evidence_type == "Frequency Artifact Detected":
        signals = ["Frequency Detector"]
        assessment = "The frequency-domain detector identified unusual patterns commonly associated with manipulated media."
    elif evidence_type == "Visual Face Anomaly":
        signals = ["CNN Detector"]
        assessment = "The spatial detector identified unusual facial characteristics."
    elif evidence_type == "Temporal Consistency Anomaly":
        signals = ["Temporal Consistency"]
        assessment = "Suspicious patterns persisted across multiple neighboring frames."
    else:
        signals = ["Weak Supporting Signal"]
        assessment = "The frame was flagged, but supporting evidence is limited."
        
    return confidence, signals, assessment

def generate_pdf_report(data: Dict[str, Any], output_path: str, evidence_dir: Path):
    from pathlib import Path
    output_path = str(Path(output_path))
    evidence_dir = Path(evidence_dir)
    
    pdf = ForensicReportPDF()
    pdf.add_page()
    
    # Header Info
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(35, 10, 'Date/Time:', 0, 0)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 0, 1)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(35, 10, 'Video Name:', 0, 0)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, data.get('video_name', 'Unknown Video'), 0, 1)
    
    pdf.ln(5)
    
    # Multimodal Fusion Summary
    fusion = data.get('fusion')
    if fusion:
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 10, '1. Multimodal Fusion Summary', 0, 1)
        
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(45, 10, 'Final Verdict:', 0, 0)
        
        f_decision = fusion.get('final_decision', 'UNKNOWN')
        if f_decision == "FAKE":
            pdf.set_text_color(200, 0, 0)
        elif f_decision == "REAL":
            pdf.set_text_color(0, 150, 0)
        else:
            pdf.set_text_color(150, 150, 0)
            
        pdf.cell(0, 10, f"{f_decision} (Confidence: {fusion.get('confidence', 'UNKNOWN')})", 0, 1)
        
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(45, 10, 'Decision Source:', 0, 0)
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, fusion.get('decision_source', 'UNKNOWN'), 0, 1)
        
        conflict = fusion.get('conflict_level', 'NONE')
        if conflict != 'NONE':
            pdf.set_font('Arial', 'B', 12)
            pdf.set_text_color(200, 0, 0)
            pdf.cell(45, 10, 'Conflict Level:', 0, 0)
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 10, conflict, 0, 1)
            pdf.set_text_color(0, 0, 0)
            
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(45, 10, 'Modality Weights:', 0, 0)
        pdf.set_font('Arial', '', 12)
        v_weight = fusion.get('modality_contributions', {}).get('video', 0.0)
        a_weight = fusion.get('modality_contributions', {}).get('audio', 0.0)
        if "VIDEO_PRIMARY" in fusion.get('decision_source', ''):
            pdf.cell(0, 10, "Video: Dominant | Audio: Supporting", 0, 1)
        else:
            pdf.cell(0, 10, f"Video: {v_weight*100:.0f}% | Audio: {a_weight*100:.0f}%", 0, 1)
        
        pdf.ln(2)
        pdf.set_font('Arial', 'I', 11)
        pdf.multi_cell(0, 8, f"Explanation: {fusion.get('explanation', '')}")
        pdf.ln(5)
    
    # Video Analysis Result
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 10, '2. Video Analysis', 0, 1)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(45, 10, 'Video Verdict:', 0, 0)
    
    final_decision = data.get('final_decision', 'UNKNOWN')
    if final_decision == "FAKE":
        pdf.set_text_color(200, 0, 0)
    elif final_decision == "REAL":
        pdf.set_text_color(0, 150, 0)
    else:
        pdf.set_text_color(0, 0, 0)
        
    pdf.cell(0, 10, final_decision, 0, 1)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(45, 10, 'Video Score:', 0, 0)
    pdf.set_font('Arial', '', 12)
    final_score = data.get('final_score', 0.0)
    pdf.cell(0, 10, f"{final_score * 100:.1f}%", 0, 1)

    
    pdf.ln(10)
    
    # Audio Analysis
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(0, 10, '3. Audio Analysis', 0, 1)
    pdf.ln(2)
    audio_data = data.get('audio', {})
    if not audio_data.get('available', False):
        pdf.set_font('Arial', '', 12)
        pdf.set_text_color(100, 100, 100)
        status_msg = "Audio track not detected" if audio_data.get('extraction_status') == "NO_AUDIO" else "Extraction Failed or Not Analyzed"
        pdf.cell(0, 10, f'Status: {status_msg}', 0, 1)
        pdf.ln(5)
    else:
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(0, 0, 0)
        
        decision = audio_data.get('decision', 'NOT_ANALYZED')
        if decision == 'LIMITED_AUDIO_EVIDENCE' or decision == 'UNRELIABLE':
            pdf.set_text_color(200, 100, 0)
            pdf.cell(0, 8, f"Audio Supporting Signal: LIMITED AUDIO EVIDENCE", 0, 1)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('Arial', '', 11)
            pdf.cell(0, 8, f"Explanation: {audio_data.get('explanation', '')}", 0, 1)
        elif decision != 'NOT_ANALYZED':
            if "SUSPICION" in decision or "SUSPICIOUS" in decision or decision == "FAKE":
                pdf.set_text_color(200, 0, 0)
            else:
                pdf.set_text_color(0, 150, 0)
            pdf.cell(0, 8, f"Audio Supporting Signal: {decision.replace('_', ' ')}", 0, 1)
            pdf.set_text_color(0, 0, 0)
            
            raw_score = audio_data.get('raw_fake_score', audio_data.get('fake_score', 0))
            calibrated = audio_data.get('calibrated_fake_score', audio_data.get('fake_score', 0))
            
            pdf.cell(0, 8, f"Calibrated Score: {calibrated * 100:.1f}% (Raw: {raw_score * 100:.1f}%) | Confidence: {audio_data.get('confidence', 'UNKNOWN')}", 0, 1)
            
            reliability = audio_data.get('audio_reliability', 'Unknown')
            rel_level = audio_data.get('reliability_level', 'Unknown')
            pdf.cell(0, 8, f"Audio Reliability: {reliability}/100 ({rel_level})", 0, 1)
            
            reasons = audio_data.get('reliability_reasons', [])
            if reasons:
                pdf.set_font('Arial', 'I', 10)
                pdf.cell(0, 6, f"Reliability Factors: {', '.join(reasons)}", 0, 1)
                pdf.set_font('Arial', '', 11)
            
        pdf.ln(2)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, "Model Configuration:", 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 8, f"Model: {audio_data.get('model_name', 'N/A')} ({audio_data.get('model_version', 'N/A')}) | Checkpoint: {audio_data.get('checkpoint_name', 'N/A')}", 0, 1)
        
        pdf.ln(2)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, "Quality Metrics:", 0, 1)
        pdf.set_font('Arial', '', 11)
        qr = audio_data.get('audio_quality_report', {})
        
        q_score_str = f"{qr.get('quality_score', 0)*100:.0f}/100"
        pdf.cell(0, 8, f"Quality Score: {q_score_str} | Duration: {qr.get('duration_sec', 0):.2f}s | Sample Rate: {qr.get('sample_rate', 0)} Hz", 0, 1)
        pdf.cell(0, 8, f"Silence Ratio: {qr.get('silence_ratio', 0)*100:.1f}% | SNR Estimate: {qr.get('snr_estimate', 0):.1f} dB | Clipping: {'Yes' if qr.get('clipping_detected', False) else 'No'}", 0, 1)
        
        q_reasons = qr.get('quality_reasons', [])
        if q_reasons:
            pdf.set_text_color(200, 100, 0)
            pdf.cell(0, 8, f"Quality Warnings: {', '.join(q_reasons)}", 0, 1)
            pdf.set_text_color(0, 0, 0)
            
        pdf.ln(2)
        
        if decision != 'NOT_ANALYZED' and decision != 'UNRELIABLE':
            segments = audio_data.get('suspicious_segments', [])
            if segments:
                pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f"Top Suspicious Audio Segments:", 0, 1)
                pdf.set_font('Arial', '', 11)
                for seg in segments:
                    pdf.cell(0, 8, f"  {seg.get('start_sec', 0):.1f}s - {seg.get('end_sec', 0):.1f}s (Score: {seg.get('score', 0) * 100:.1f}%)", 0, 1)
            
            evidence_images = audio_data.get('evidence_images', [])
            if evidence_images:
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 11)
                pdf.cell(0, 8, f"Spectrogram Analysis:", 0, 1)
                import os
                from pathlib import Path
                spec_path = str(Path('D:/forsen') / evidence_images[0].lstrip('/'))
                if os.path.exists(spec_path):
                    pdf.image(spec_path, x=10, w=150)
                    pdf.ln(60)
        
        pdf.ln(5)

    # Top Suspicious Moments
    top_frames = data.get('top_suspicious_frames', [])
    if top_frames:
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 10, '4. Top Suspicious Moments', 0, 1)
        pdf.ln(5)
        
        pdf.set_text_color(0, 0, 0)
        for i, frame in enumerate(top_frames):
            pdf.set_font('Arial', 'B', 12)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(0, 10, f"  Moment #{i+1} - Timestamp: {frame.get('timestamp_label', '')}", 0, 1, 'L', fill=True)
            pdf.ln(2)
            
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(45, 8, 'Confidence Score:', 0, 0)
            pdf.set_font('Arial', '', 11)
            pdf.cell(0, 8, f"{frame.get('score', 0.0) * 100:.1f}%", 0, 1)
            
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(45, 8, 'Evidence Type:', 0, 0)
            pdf.set_font('Arial', '', 11)
            ev_type = frame.get('evidence_type', '')
            pdf.cell(0, 8, ev_type, 0, 1)
            
            conf, signals, assessment = get_evidence_summary(ev_type, frame.get('score', 0.0))
            
            pdf.set_font('Arial', 'B', 11)
            pdf.cell(45, 8, 'Key Finding:', 0, 0)
            pdf.set_font('Arial', '', 11)
            pdf.multi_cell(0, 8, assessment)
            
            # Images
            f_name = frame.get('frame')
            orig_path = evidence_dir / f_name if f_name else None
            grad_path = evidence_dir / f"heatmap_{f_name}" if f_name else None
            
            if orig_path and orig_path.exists():
                pdf.ln(5)
                # Ensure we don't page break in the middle of images
                if pdf.get_y() > 200:
                    pdf.add_page()
                    
                y_before_images = pdf.get_y()
                
                # Original Frame
                pdf.set_font('Arial', 'I', 10)
                pdf.cell(90, 8, 'Original Frame', 0, 0, 'C')
                
                # Grad-CAM
                has_grad = grad_path and grad_path.exists()
                if has_grad:
                    pdf.cell(90, 8, 'Model Attention Map', 0, 1, 'C')
                else:
                    pdf.ln(8)
                
                # Render images
                img_y = pdf.get_y()
                pdf.image(str(orig_path), x=20, y=img_y, w=60)
                
                if has_grad:
                    pdf.image(str(grad_path), x=110, y=img_y, w=60)
                
                # Move Y down below images (assume height ~45 for w=60)
                pdf.set_y(img_y + 50)
            
            pdf.ln(10)
            
    pdf.output(output_path)
