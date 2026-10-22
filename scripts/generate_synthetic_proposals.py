"""Generate four fictional, varied RFP proposal PDFs for the classroom project."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sample_proposals"
OUTPUT.mkdir(parents=True, exist_ok=True)

NAVY = colors.HexColor("#18324B")
TEAL = colors.HexColor("#1C7C7D")
PALE = colors.HexColor("#EAF1F5")
MID = colors.HexColor("#5D6B78")
LINE = colors.HexColor("#D5DEE5")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=NAVY, alignment=TA_LEFT, spaceAfter=7))
styles.add(ParagraphStyle(name="SubTitle", parent=styles["Normal"], fontName="Helvetica", fontSize=10, leading=14, textColor=MID, spaceAfter=12))
styles.add(ParagraphStyle(name="SectionHead", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=NAVY, spaceBefore=7, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.6, leading=12.1, textColor=colors.HexColor("#263746"), spaceAfter=5))
styles.add(ParagraphStyle(name="Cell", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.8, leading=10, textColor=colors.HexColor("#263746")))
styles.add(ParagraphStyle(name="CellHead", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.8, leading=9.5, textColor=colors.white))
styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], fontName="Helvetica-Oblique", fontSize=8, leading=10.5, textColor=MID, leftIndent=7, rightIndent=7, spaceBefore=4, spaceAfter=6))


def para(text, style="BodySmall"):
    return Paragraph(escape(text), styles[style])


def bullet_list(items):
    return [Paragraph(f"<bullet>&bull;</bullet> {escape(item)}", styles["BodySmall"]) for item in items]


def section(title, content):
    return [Paragraph(escape(title), styles["SectionHead"]), *content]


def price_table(rows, accent):
    data = [[Paragraph("Workstream", styles["CellHead"]), Paragraph("One-time price (USD)", styles["CellHead"]), Paragraph("Notes", styles["CellHead"])]]
    for work, price, notes, *_ in rows:
        data.append([para(work, "Cell"), para(price, "Cell"), para(notes, "Cell")])
    data.append([Paragraph("Total proposed implementation", styles["CellHead"]), Paragraph(f"<b>{escape(rows[-1][3])}</b>", styles["CellHead"]), para("Excludes any items identified as optional or out of scope.", "Cell")])
    # The total is provided separately as a fourth value on the final row payload.
    table = Table(data, colWidths=[1.62*inch, 1.2*inch, 3.55*inch], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), accent),
        ("BACKGROUND", (0,-1), (-1,-1), accent),
        ("GRID", (0,0), (-1,-1), 0.35, LINE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ALIGN", (1,1), (1,-1), "RIGHT"),
    ]))
    return table


def footer(canvas, doc, supplier):
    canvas.saveState()
    width, height = letter
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 0.48*inch, width-doc.rightMargin, 0.48*inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MID)
    canvas.drawString(doc.leftMargin, 0.31*inch, f"SYNTHETIC CLASSROOM PROPOSAL  |  {supplier}")
    canvas.drawRightString(width-doc.rightMargin, 0.31*inch, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(spec):
    path = OUTPUT / f"{spec['slug']}.pdf"
    accent = colors.HexColor(spec["accent"])
    styles["CoverTitle"].textColor = accent
    styles["SectionHead"].textColor = accent
    doc = BaseDocTemplate(
        str(path), pagesize=letter,
        rightMargin=0.58*inch, leftMargin=0.58*inch,
        topMargin=0.58*inch, bottomMargin=0.68*inch,
        title=f"{spec['supplier']} - Synthetic RFP Proposal",
        author=spec["supplier"],
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="proposal", frames=[frame], onPage=lambda c, d: footer(c, d, spec["supplier"]))])

    story = [
        Paragraph(escape(spec["kicker"]), styles["SubTitle"]),
        Paragraph(escape(spec["supplier"]), styles["CoverTitle"]),
        Paragraph(escape(spec["cover_subtitle"]), styles["SubTitle"]),
    ]
    banner = Table([[para(value, "Cell") for value in spec["banner_values"]]], colWidths=[2.28*inch, 1.8*inch, 2.29*inch])
    banner.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), PALE), ("BOX", (0,0), (-1,-1), 0.5, accent), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 7), ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
    story += [banner, Spacer(1, 6), para("This fictional proposal was created solely for a classroom mini-project. All organizations, people, references, and figures in this document are invented.", "Callout")]
    summary_section = section("Executive summary and understanding", [para(spec["summary"])])
    solution_section = section("Proposed solution and implementation approach", [para(spec["solution"]), *bullet_list(spec["solution_points"])])
    timeline_section = section("Timeline, team, and milestones", [para(spec["timeline_intro"]), timeline(spec["timeline_rows"], accent), Spacer(1, 4), para(spec["team"])])
    price_section = section("Commercial schedule and assumptions", [price_table(spec["price_rows"], accent), Spacer(1, 4), para(spec["price_assumptions"])])
    security_section = section("Security, compliance, and risk controls", [para(spec["security"]), *bullet_list(spec["security_points"])])
    support_section = section("Support model", [para(spec["support"])])
    experience_section = section("Relevant experience and references", [para(spec["experience"]), *bullet_list(spec["references"])])
    layout = spec["layout"]
    if layout == "formal":
        story += summary_section + solution_section + timeline_section
        second_page = price_section + security_section + support_section + experience_section
    elif layout == "quotation":
        story += summary_section + price_section + solution_section
        second_page = timeline_section + security_section + support_section + experience_section
    elif layout == "delivery_plan":
        story += summary_section + timeline_section + solution_section
        second_page = price_section + security_section + support_section + experience_section
    else:  # credential-led response
        story += summary_section + experience_section + solution_section
        second_page = timeline_section + price_section + security_section + support_section
    story.append(PageBreak())
    story += [Paragraph(escape(spec["page_two_kicker"]), styles["SubTitle"]), Paragraph(escape(spec["supplier"]), styles["CoverTitle"])]
    story += second_page
    story += [Spacer(1, 2), para(f"Open items: {spec['open_items']}", "Callout")]
    doc.build(story)
    print(path)


COMMON_TIMELINE_HEADER = [Paragraph("Phase", styles["CellHead"]), Paragraph("Duration", styles["CellHead"]), Paragraph("Milestone / exit evidence", styles["CellHead"])]


def timeline(rows, accent):
    data = [COMMON_TIMELINE_HEADER] + [[para(a, "Cell"), para(b, "Cell"), para(c, "Cell")] for a,b,c in rows]
    table = Table(data, colWidths=[1.38*inch, 0.88*inch, 4.11*inch], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), accent), ("GRID", (0,0), (-1,-1), 0.35, LINE), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
    return table


SPECS = [
    {
        "slug":"apex_systems", "supplier":"Apex Systems", "proposal_date":"21 October 2026", "validity":"90 days",
        "layout":"formal", "accent":"#1C7C7D", "kicker":"FORMAL RFP RESPONSE  /  SYNTHETIC CLASSROOM EXERCISE",
        "cover_subtitle":"Northbridge Municipal Services | Unified Service Delivery Portal",
        "page_two_kicker":"TECHNICAL ASSURANCE & COMMERCIAL SCHEDULE",
        "banner_values":["Issued by: Northbridge Municipal Services (fictional)","Proposal date: 21 October 2026","Offer validity: 90 days"],
        "summary":"Northbridge Municipal Services (NMS) wants one secure portal for residents, service agents, and procurement staff to submit requests, route cases, exchange documents, and track decisions. Apex proposes a cloud-hosted, API-first platform with strong identity, audit, and data-protection controls. Our design favors operational resilience and a clear security boundary; it requires more investment than a basic workflow replacement. We assume NMS will provide timely access to its identity, finance, and document-management owners.",
        "solution":"Apex will configure a case-management platform with a React resident portal, a .NET service layer, and a managed PostgreSQL data store. A message queue will isolate integrations from user-facing transactions. Single sign-on will use NMS's identity provider through OIDC; finance and document services will connect through versioned APIs where available. Batch exchange is available as a fallback, but requires interface approval.",
        "solution_points":["Separate resident, agent, and administrator roles with least-privilege access and delegated approvals.","Encrypt traffic in transit and stored content at rest; retain immutable audit events for administrator and case actions.","Provide a non-production integration environment and automated deployment pipeline with rollback controls."],
        "timeline_intro":"The proposed schedule is 14 months from kickoff, including two integration rehearsals and a security test before production.",
        "timeline_rows":[("Discovery & design","10 weeks","Approved backlog, threat model, and interface specifications"),("Build & integration","24 weeks","Portal, workflow, identity, finance, and document connections"),("Pilot & assurance","14 weeks","UAT, penetration test, accessibility review, remediation"),("Rollout & transition","12 weeks","Phased launch, training, operating handover")],
        "team":"Core team: delivery director (0.3 FTE), solution architect (0.6), security lead (0.3), integration engineers (2), product analyst (1), and test lead (1). NMS must provide a product owner and system owners for approximately four hours per week. A named replacement plan is available for key roles.",
        "price_rows":[("Platform configuration","$720,000","Tenant setup, portal, workflows"),("Integration and migration","$610,000","Three interfaces; migration mapping"),("Security, testing, and launch","$490,000","Threat review, testing, release support"),("Training and transition","$310,000","Admin and service-agent enablement"),("Optional year-one platform subscription","$270,000","Shown separately; not included in implementation total","$2,130,000")],
        "price_assumptions":"The implementation total is $2.13 million, excluding the optional $270,000 year-one subscription. Prices exclude taxes and major third-party license changes. Additional interfaces beyond identity, finance, and document management are estimated through change control. Travel is included for two onsite workshops.",
        "security":"Apex's delivery model is designed for sensitive municipal case data. We will provide a control matrix mapped to NMS requirements before configuration. Apex can provide a current SOC 2 Type II report under NDA; the hosting region will be selected with NMS during discovery. Data residency and deletion schedules require confirmation against NMS retention policy.",
        "security_points":["MFA for privileged users; SSO for staff; role and permission review at each release.","Centralized audit events, vulnerability scanning, annual third-party penetration testing, and a 24-hour incident notification target.","Risks: legacy API limitations, incomplete data ownership, and schedule impact if interface approvals exceed three weeks."],
        "support":"Apex offers 24x7 priority-one intake, a 30-minute acknowledgement target for critical incidents, and a named service manager. Standard support is 08:00–18:00 local business days. The service-level proposal and escalation roster are included in our full commercial schedule.",
        "experience":"Apex reports 12 years delivering public-sector platforms and cites two comparable programs involving identity federation and document exchange. Customer names are withheld here; reference calls can be arranged after shortlist selection. The proposal includes a detailed support staffing plan but no named reference contact details.",
        "references":["Harbor County Digital Permits — 18,000 monthly submissions; identity integration; completed 2024.","Westfield Transit Authority Case Hub — 640 internal users; audit and document controls; completed 2023."],
        "open_items":"Confirm NMS hosting region, retention schedule, accessibility standard, and the three interface owners before final contract.",
    },
    {
        "slug":"brightpath_tech", "supplier":"BrightPath Tech", "proposal_date":"20 October 2026", "validity":"30 days",
        "layout":"quotation", "accent":"#B85E12", "kicker":"FIXED-PRICE OFFER  /  QUICK IMPLEMENTATION RESPONSE",
        "cover_subtitle":"Price-led response for the Northbridge Municipal Services Service Delivery Portal",
        "page_two_kicker":"IMPLEMENTATION SCHEDULE, ASSURANCE & SERVICE NOTES",
        "banner_values":["Prepared for: Northbridge Municipal Services","Submitted: 20 October 2026","Offer validity: 30 days"],
        "summary":"BrightPath understands NMS needs a faster way to accept and route service requests. We propose adapting our low-code workflow product and launching the core intake journey in nine months. Our fixed price is the lowest in this response set. The offer is intentionally focused on standard intake and routing; the proposal does not yet include detailed data migration, security certification evidence, or a complete integration inventory. NMS will need to confirm those items during discovery.",
        "solution":"The BrightPath Hub provides web forms, email notifications, queues, and basic dashboards. We plan to connect the identity provider using its standard SAML connector. Finance and document links will initially use scheduled CSV exports and imports; direct APIs may be scoped if NMS supplies specifications. Mobile access is browser-based. Advanced workflow analytics and multilingual resident content are not included in this price.",
        "solution_points":["Use configurable forms and queue rules for the first five service categories.","Provide a standard staff portal with role groups managed by NMS administrators.","Integrations are limited to one identity connector and two scheduled file exchanges in the base scope."],
        "timeline_intro":"BrightPath targets a nine-month delivery. The schedule is aggressive and assumes NMS decisions and source files arrive within five business days.",
        "timeline_rows":[("Kickoff & workshops","4 weeks","Scope confirmation and form inventory"),("Configure & connect","16 weeks","Core workflows and standard connectors"),("User review","10 weeks","UAT on supplied test data"),("Launch","6 weeks","Production rollout and basic administrator handoff")],
        "team":"Team: one delivery manager, two low-code configurators, one integration analyst, and shared QA support. Roles may be remote and are assigned across several customer projects. Named staff CVs, weekly allocation percentages, and a formal risk owner are not included. NMS is expected to supply test scripts and training materials.",
        "price_rows":[("Platform setup","$370,000","Forms, queues, dashboards"),("Standard connectors","$240,000","SSO plus two file exchanges"),("Testing and launch","$190,000","UAT support and deployment"),("Training","$100,000","Two virtual administrator sessions"),("Year-one subscription","$350,000","Up to 500 staff users","$900,000")],
        "price_assumptions":"The fixed implementation price is $900,000; the $350,000 subscription is separate, making the stated first-year total $1.25 million before taxes. Data cleansing, historical migration, API development, penetration testing, and after-hours support are excluded. Changes to the five-category scope are billed at $190 per hour.",
        "security":"BrightPath will use its hosted SaaS environment and standard platform security settings. The proposal states that data is encrypted in transit and at rest, but does not identify the encryption standards, hosting region, independent assurance reports, retention controls, or incident-notification commitment. No certification evidence is attached. These points are open for clarification and contract review.",
        "security_points":["Staff access uses SAML single sign-on; role details beyond standard administrator and agent groups are not specified.","Backups are described as daily; recovery time and recovery point targets are not stated.","Risks: file-exchange errors, unclear migration scope, and security assurance gaps may add time or cost."],
        "support":"Support is available by email during 09:00–17:00 Eastern Time on business days. The standard response objective is one business day. No 24x7 incident path, severity matrix, service credit schedule, or named escalation manager is proposed.",
        "experience":"BrightPath has delivered four low-code workflow projects, mostly for small private organizations. This would be its first municipal deployment above 300 users. The proposal describes the product and schedule but includes limited outcome metrics and no detailed public-sector case study.",
        "references":["Willow Creek Property Services — 120 staff; request routing; client contact withheld pending permission.","A signed reference letter and measurable case outcomes were not supplied with this proposal."],
        "open_items":"Security assurance, data location, recovery objectives, historical migration, API scope, staffing allocation, and reference permission remain unspecified.",
    },
    {
        "slug":"nexaworks", "supplier":"NexaWorks", "proposal_date":"18 October 2026", "validity":"75 days",
        "layout":"delivery_plan", "accent":"#43734B", "kicker":"DELIVERY PLAN  /  SERVICE TRANSFORMATION PROPOSAL",
        "cover_subtitle":"A phased operating model and implementation plan for Northbridge Municipal Services",
        "page_two_kicker":"COMMERCIAL RESPONSE & SERVICE ASSURANCE",
        "banner_values":["Client: Northbridge Municipal Services","Mobilization: target 12 months","Offer validity: 75 days"],
        "summary":"NexaWorks proposes a balanced modernization that improves resident intake while giving NMS teams a controlled path from paper-heavy processes to measurable digital services. We recommend a 12-month delivery with a service-design phase, working prototypes, staged integration, and a supported pilot before wider rollout. The plan includes named decision gates and a practical operational handover. We assume NMS can assign a product owner and representatives from service, security, and integration teams.",
        "solution":"The solution combines a configurable case platform, accessible resident forms, a staff workspace, and an integration layer. NMS will own the case taxonomy and approval rules; NexaWorks will configure workflows and provide API adapters for identity, finance, and document management. A migration rehearsal will compare record counts and sampled attachments before the final cutover. Each release includes user acceptance and security review.",
        "solution_points":["Start with three high-volume services, then add two service groups after the pilot exit review.","Provide role-based access, configurable retention labels, audit export, and operational dashboards.","Use weekly backlog review and a decision log; unresolved dependencies are raised to the steering group within five working days."],
        "timeline_intro":"The 12-month plan includes explicit exit evidence for each stage and an eight-week stabilization period after go-live.",
        "timeline_rows":[("Discovery & prototype","8 weeks","Service maps, backlog, prototype sign-off"),("Configure & integrate","20 weeks","Workflows and three interface adapters"),("Migration & pilot","12 weeks","Reconciled migration rehearsal and pilot results"),("Rollout & stabilization","12 weeks","Phased launch, adoption measures, service handover")],
        "team":"Named roles include delivery lead (0.5 FTE), product/service designer (0.7), solution architect (0.5), two configuration and integration specialists, test and accessibility lead (0.5), and change manager (0.4). NMS supplies a product owner, security contact, and data steward. NexaWorks will hold a weekly dependency clinic and monthly steering review.",
        "price_rows":[("Discovery and service design","$280,000","Workshops, service maps, prototype"),("Configuration and integrations","$610,000","Core platform and three adapters"),("Migration, test, and pilot","$360,000","Rehearsal, accessibility, UAT"),("Launch and change support","$250,000","Training and stabilization"),("Optional managed support","$180,000","Annual support after warranty","$1,500,000")],
        "price_assumptions":"The fixed implementation total is $1.50 million. Optional managed support is $180,000 annually and is not included in that total. Taxes and third-party licensing are excluded. The price includes one migration rehearsal and up to three integrations; additional source systems require a change estimate before work begins.",
        "security":"NexaWorks will produce a security and privacy plan at discovery and map each NMS control to a design decision or test. The hosting partner's SOC 2 Type II summary and data-processing terms are available for review. NMS selects the hosting region before build. The proposal sets a 24-hour initial incident notification target and includes a tabletop exercise before launch.",
        "security_points":["MFA for privileged roles, SSO for staff, encryption at rest and in transit, and quarterly access recertification.","Retention and deletion follow NMS-approved schedules; audit events export to the NMS monitoring platform.","Key risks are data quality, delayed access to legacy interfaces, and adoption; each has an owner and a mitigation in the delivery risk log."],
        "support":"NexaWorks proposes a 90-day stabilization period with daily triage during launch week, weekly service reviews, and a named transition manager. Optional managed support includes business-hours service desk, severity-based targets, and a 24x7 critical incident contact. The escalation path and customer responsibilities are stated in the commercial appendix.",
        "experience":"NexaWorks reports eight years delivering case and service platforms. Its team has completed public-sector workflow, document migration, and resident portal projects. The proposal provides a clear implementation and support model, though it does not attach full reference letters or detailed service-level performance data.",
        "references":["Pinehaven Regional Services — 410 staff; 22 digital services launched in phases; 2025.","Lakeshore Community Grants Office — migration of 86,000 records; stabilized in 10 weeks; 2024."],
        "open_items":"Confirm final service priorities, hosting region, source-data quality, and whether optional managed support is required.",
    },
    {
        "slug":"orbit_digital", "supplier":"Orbit Digital", "proposal_date":"19 October 2026", "validity":"60 days",
        "layout":"credential_led", "accent":"#604B7A", "kicker":"SUPPLIER QUALIFICATIONS  /  PLATFORM PROPOSAL",
        "cover_subtitle":"OrbitOne case platform response to the Northbridge Municipal Services procurement",
        "page_two_kicker":"DELIVERY, COMMERCIAL & ASSURANCE DETAILS",
        "banner_values":["Prepared for: Northbridge Municipal Services","Program: Unified Service Delivery Portal","Offer validity: 60 days"],
        "summary":"Orbit Digital brings substantial delivery experience and references across complex public-service programs. NMS can use our OrbitOne platform to consolidate intake, case tracking, and manager reporting. We propose an 11-month rollout at a mid-range price. Our proposal describes the target operating model and team credentials in detail, but the integration approach is still at concept level: interface patterns, data ownership, and migration volumes will need to be confirmed after award.",
        "solution":"OrbitOne includes configurable case records, a resident-facing request form, workflow queues, and management dashboards. We expect to connect the platform to NMS identity and enterprise systems using a mix of standard connectors and project-specific adapters. The exact integration sequence and API-versus-file pattern will be agreed during the first design sprint. No interface catalogue or sample mapping is attached at this stage.",
        "solution_points":["Configure separate workspaces for residents, service agents, and department managers.","Support standard role groups, configurable approvals, and searchable case history.","Orbit recommends a phased migration but has not yet estimated record volumes or attachment conversion effort."],
        "timeline_intro":"The 11-month target is based on Orbit's prior program experience. A detailed dependency network and named exit criteria will be prepared during mobilization.",
        "timeline_rows":[("Mobilization","6 weeks","Governance, workshops, and design plan"),("Platform configuration","20 weeks","Core portal and case workflows"),("Integration & migration","16 weeks","Sequence and acceptance criteria to be agreed"),("Rollout & transition","10 weeks","Department rollout and operations handover")],
        "team":"Proposed team: executive sponsor (monthly), program director (0.4 FTE), senior platform architect (0.6), three implementation consultants, data migration lead (0.5), and shared quality lead. Orbit has a large delivery bench and can provide additional specialists. Individual names, weekly allocation commitments, and a staffing contingency table will be finalized after selection.",
        "price_rows":[("Platform configuration","$560,000","Core portal and case setup"),("Integration allowance","$470,000","Planning allowance; interfaces TBD"),("Migration and testing","$390,000","Volume assumptions to be confirmed"),("Training and transition","$240,000","Department sessions and handover"),("Optional premium support","$210,000","Annual enhanced support","$1,660,000")],
        "price_assumptions":"The stated implementation estimate is $1.66 million, excluding optional premium support at $210,000 per year and applicable taxes. The integration amount is an allowance, not a fixed-price commitment, because interface count and complexity are not yet defined. Migration above 60,000 records or major attachment conversion may require a change order.",
        "security":"Orbit states that OrbitOne supports encryption, role permissions, audit history, and configurable retention. A security overview is available after mutual NDA. This response does not name the hosting region or provide a certification report, control mapping, incident-notification target, or detailed recovery objectives. Orbit proposes a joint security workshop in mobilization to resolve those points.",
        "security_points":["MFA and SSO are supported; NMS role mapping and privileged-access review are to be designed.","Backups and disaster recovery are included in the service, but recovery time and recovery point targets are not stated.","Risks include integration uncertainty, migration volume variance, and unresolved data-retention requirements."],
        "support":"Orbit offers business-hours support with a named customer success manager and optional premium coverage. The proposal says critical cases receive priority handling but does not give response or restoration targets. Premium support terms and service credits will be supplied with the final service schedule.",
        "experience":"Orbit reports 15 years in enterprise delivery and lists a senior team with experience in municipal licensing, transit operations, and public-benefit casework. It offers strong client references and describes measurable outcomes, but the integration plan and support response targets are less complete than the experience narrative.",
        "references":["Eastborough Public Works — 1,200 staff; 31% reduction in average assignment time; 2024. Contact available with permission.","Cedar Valley Benefits Office — 74,000 annual cases; portal and workflow rollout; 2023. Reference letter supplied on request.","A third named reference and written performance metrics for platform availability were not included."],
        "open_items":"Confirm interface inventory, data migration volumes, hosting region, control evidence, recovery targets, service levels, and named delivery allocations.",
    },
]

for spec in SPECS:
    build_pdf(spec)
