import io
import datetime
from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for, session
from routes.auth_routes import login_required, role_required
from database.db import query_db
from config import Config

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

report_bp = Blueprint('reports', __name__, url_prefix='/reports')

def get_report_data(course_id=None, section_id=None, start_date=None, end_date=None):
    """Query consolidated attendance metrics."""
    where_clauses = ["1=1"]
    params = []

    if course_id:
        where_clauses.append("a.course_id = %s")
        params.append(course_id)
    if start_date:
        where_clauses.append("a.attendance_date >= %s")
        params.append(start_date)
    if end_date:
        where_clauses.append("a.attendance_date <= %s")
        params.append(end_date)
    if section_id:
        where_clauses.append("s.section_id = %s")
        params.append(section_id)

    where_sql = " AND ".join(where_clauses)

    records = query_db(f"""
        SELECT a.id, a.attendance_date, a.status, a.confidence_score, a.marked_by, a.marked_at,
               s.id as student_id, s.roll_number, u.full_name as student_name,
               c.course_code, c.course_name,
               sec.name as section_name
        FROM attendance_records a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON s.user_id = u.id
        JOIN courses c ON a.course_id = c.id
        JOIN attendance_sessions sess ON a.session_id = sess.id
        JOIN sections sec ON sess.section_id = sec.id
        WHERE {where_sql}
        ORDER BY a.attendance_date DESC, s.roll_number ASC
    """, params)

    # Student summary aggregation
    student_summary = query_db(f"""
        SELECT s.id as student_id, s.roll_number, u.full_name as student_name,
               c.course_code, c.course_name, sec.name as section_name,
               COUNT(a.id) as total_sessions,
               SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) as present_count,
               SUM(CASE WHEN a.status = 'Late' THEN 1 ELSE 0 END) as late_count,
               SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
               SUM(CASE WHEN a.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended_count
        FROM students s
        JOIN users u ON s.user_id = u.id
        JOIN sections sec ON s.section_id = sec.id
        LEFT JOIN attendance_records a ON s.id = a.student_id {f'AND a.course_id = {course_id}' if course_id else ''}
        LEFT JOIN courses c ON a.course_id = c.id
        WHERE {'s.section_id = ' + str(section_id) if section_id else '1=1'}
        GROUP BY s.id, s.roll_number, u.full_name, c.course_code, c.course_name, sec.name
        ORDER BY s.roll_number ASC
    """)

    for st in student_summary:
        tot = st['total_sessions'] or 0
        att = st['attended_count'] or 0
        st['percent'] = round((att / tot * 100), 1) if tot > 0 else 0.0

    return records, student_summary

@report_bp.route('/')
@login_required
def index():
    course_id = request.args.get('course_id')
    section_id = request.args.get('section_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Defaults to past 30 days if not set
    if not end_date:
        end_date = datetime.date.today().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')

    records, student_summary = get_report_data(course_id, section_id, start_date, end_date)

    courses = query_db("SELECT id, course_code, course_name FROM courses ORDER BY course_code")
    sections = query_db("SELECT id, name FROM sections ORDER BY name")

    # Metrics
    total_records = len(records)
    total_present = sum(1 for r in records if r['status'] == 'Present')
    total_late = sum(1 for r in records if r['status'] == 'Late')
    total_absent = sum(1 for r in records if r['status'] == 'Absent')
    overall_attendance_pct = round(((total_present + total_late) / total_records * 100), 1) if total_records > 0 else 0.0

    # Low attendance count in this view
    defaulters = [s for s in student_summary if s['percent'] < Config.MIN_ATTENDANCE_PERCENT and s['total_sessions'] > 0]

    return render_template('reports/index.html',
                           records=records,
                           student_summary=student_summary,
                           courses=courses,
                           sections=sections,
                           selected_course=course_id,
                           selected_section=section_id,
                           start_date=start_date,
                           end_date=end_date,
                           total_records=total_records,
                           total_present=total_present,
                           total_late=total_late,
                           total_absent=total_absent,
                           overall_pct=overall_attendance_pct,
                           defaulters=defaulters,
                           min_threshold=Config.MIN_ATTENDANCE_PERCENT)

@report_bp.route('/export/excel')
@login_required
def export_excel():
    course_id = request.args.get('course_id')
    section_id = request.args.get('section_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    records, student_summary = get_report_data(course_id, section_id, start_date, end_date)

    # Build Excel Workbook
    wb = openpyxl.Workbook()
    
    # Sheet 1: Summary Report
    ws_summary = wb.active
    ws_summary.title = "Student Attendance Summary"

    # Header Styling
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1E3A8A")
    thin_border = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB')
    )
    defaulter_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    good_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")

    # Title Block
    ws_summary["A1"] = "AI-BASED SMART ATTENDANCE SYSTEM"
    ws_summary["A1"].font = title_font
    ws_summary["A2"] = f"Attendance Report: {start_date} to {end_date}"
    ws_summary["A2"].font = Font(name="Calibri", size=11, italic=True)

    headers = ["Roll Number", "Student Name", "Course", "Section", "Total Classes", "Present", "Late", "Absent", "Attendance %", "Status"]
    for col_idx, header in enumerate(headers, 1):
        cell = ws_summary.cell(row=4, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    row_idx = 5
    for st in student_summary:
        pct = st['percent']
        status_label = "ELIGIBLE" if pct >= Config.MIN_ATTENDANCE_PERCENT else "LOW ATTENDANCE"
        
        ws_summary.cell(row=row_idx, column=1, value=st['roll_number']).alignment = Alignment(horizontal="center")
        ws_summary.cell(row=row_idx, column=2, value=st['student_name'])
        ws_summary.cell(row=row_idx, column=3, value=st['course_name'] or 'All Courses')
        ws_summary.cell(row=row_idx, column=4, value=st['section_name'] or 'N/A').alignment = Alignment(horizontal="center")
        ws_summary.cell(row=row_idx, column=5, value=st['total_sessions']).alignment = Alignment(horizontal="center")
        ws_summary.cell(row=row_idx, column=6, value=st['present_count']).alignment = Alignment(horizontal="center")
        ws_summary.cell(row=row_idx, column=7, value=st['late_count']).alignment = Alignment(horizontal="center")
        ws_summary.cell(row=row_idx, column=8, value=st['absent_count']).alignment = Alignment(horizontal="center")
        
        pct_cell = ws_summary.cell(row=row_idx, column=9, value=f"{pct}%")
        pct_cell.alignment = Alignment(horizontal="center")
        pct_cell.font = Font(bold=True)

        stat_cell = ws_summary.cell(row=row_idx, column=10, value=status_label)
        stat_cell.alignment = Alignment(horizontal="center")
        stat_cell.font = Font(bold=True)
        if pct < Config.MIN_ATTENDANCE_PERCENT:
            pct_cell.fill = defaulter_fill
            stat_cell.fill = defaulter_fill
        else:
            pct_cell.fill = good_fill
            stat_cell.fill = good_fill

        for c in range(1, 11):
            ws_summary.cell(row=row_idx, column=c).border = thin_border
        row_idx += 1

    # Auto-adjust column widths
    for col in ws_summary.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_summary.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # Sheet 2: Detailed Daily Logs
    ws_detail = wb.create_sheet(title="Daily Attendance Logs")
    ws_detail["A1"] = "Detailed Attendance Daily Logs"
    ws_detail["A1"].font = title_font

    detail_headers = ["Record ID", "Date", "Roll Number", "Student Name", "Course", "Section", "Status", "Confidence %", "Marked By", "Timestamp"]
    for col_idx, header in enumerate(detail_headers, 1):
        cell = ws_detail.cell(row=3, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    d_row = 4
    for r in records:
        ws_detail.cell(row=d_row, column=1, value=r['id']).alignment = Alignment(horizontal="center")
        ws_detail.cell(row=d_row, column=2, value=str(r['attendance_date'])).alignment = Alignment(horizontal="center")
        ws_detail.cell(row=d_row, column=3, value=r['roll_number']).alignment = Alignment(horizontal="center")
        ws_detail.cell(row=d_row, column=4, value=r['student_name'])
        ws_detail.cell(row=d_row, column=5, value=r['course_code'])
        ws_detail.cell(row=d_row, column=6, value=r['section_name']).alignment = Alignment(horizontal="center")
        ws_detail.cell(row=d_row, column=7, value=r['status']).alignment = Alignment(horizontal="center")
        ws_detail.cell(row=d_row, column=8, value=f"{r['confidence_score']}%" if r['confidence_score'] else '-').alignment = Alignment(horizontal="center")
        ws_detail.cell(row=d_row, column=9, value=r['marked_by'])
        ws_detail.cell(row=d_row, column=10, value=str(r['marked_at']))

        for c in range(1, 11):
            ws_detail.cell(row=d_row, column=c).border = thin_border
        d_row += 1

    for col in ws_detail.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_detail.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # Save to memory buffer
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    filename = f"Attendance_Report_{datetime.date.today().strftime('%Y%m%d')}.xlsx"
    return send_file(stream, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@report_bp.route('/export/pdf')
@login_required
def export_pdf():
    course_id = request.args.get('course_id')
    section_id = request.args.get('section_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    records, student_summary = get_report_data(course_id, section_id, start_date, end_date)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1, # Center
        spaceAfter=6
    )
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4B5563'),
        alignment=1,
        spaceAfter=15
    )

    story.append(Paragraph("AI-BASED SMART ATTENDANCE SYSTEM", title_style))
    story.append(Paragraph(f"Official Attendance Report &amp; Defaulter Analysis | Period: {start_date} to {end_date} | Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", sub_style))

    # Table Data
    table_data = [
        ["Roll No", "Student Name", "Course", "Section", "Classes", "Present", "Late", "Absent", "Rate %", "Status"]
    ]

    for st in student_summary:
        pct = st['percent']
        status = "ELIGIBLE" if pct >= Config.MIN_ATTENDANCE_PERCENT else "DEFICIENT"
        table_data.append([
            st['roll_number'],
            st['student_name'],
            st['course_code'] or 'All',
            st['section_name'] or 'All',
            str(st['total_sessions']),
            str(st['present_count']),
            str(st['late_count']),
            str(st['absent_count']),
            f"{pct}%",
            status
        ])

    table = Table(table_data, colWidths=[80, 150, 65, 65, 55, 55, 50, 55, 65, 80])
    
    # Table Style
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
    ])

    # Highlight low attendance rows
    for i, st in enumerate(student_summary, 1):
        if st['percent'] < Config.MIN_ATTENDANCE_PERCENT:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FEE2E2'))
            t_style.add('TEXTCOLOR', (8, i), (9, i), colors.HexColor('#DC2626'))
        else:
            if i % 2 == 0:
                t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F9FAFB'))

    table.setStyle(t_style)
    story.append(table)
    story.append(Spacer(1, 30))

    # Signoff Block
    sign_data = [
        ["Course Instructor Signature: ____________________", "Head of Department / Dean Signature: ____________________"]
    ]
    sign_table = Table(sign_data, colWidths=[360, 360])
    sign_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold')
    ]))
    story.append(sign_table)

    doc.build(story)
    buffer.seek(0)

    filename = f"Attendance_Report_{datetime.date.today().strftime('%Y%m%d')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")
