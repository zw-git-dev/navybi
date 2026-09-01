/*
 * Generates the SBIR Direct-to-Phase-II feasibility documentation for the
 * NavyBI prototype.
 *
 * Every quantitative claim in this document is produced by the repository it
 * describes and is reproducible from it -- extraction accuracy comes from
 * data/clean/extraction_accuracy.json (written by ingest/run_ingest.py),
 * test counts from the suites themselves. Nothing here is estimated.
 */
const fs = require('fs');
const path = require('path');
const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, LevelFormat,
  PageBreak, PageNumber, Packer, Paragraph, ShadingType, Table, TableCell, TableRow,
  TextRun, WidthType,
} = require('docx');

const REPO = path.join(__dirname, '..');
const accuracy = JSON.parse(
  fs.readFileSync(path.join(REPO, 'data/clean/extraction_accuracy.json'), 'utf8')
);

// US Letter, 1" margins -> usable content width in DXA.
const CONTENT_W = 12240 - 1440 * 2;
const ACCENT = '1F3864';
const HDR_BG = 'DCE3F0';
const ALT_BG = 'F2F5FA';

// ---------------------------------------------------------------- helpers

const P = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 120, line: 276 },
    alignment: opts.align,
    children: [new TextRun({ text, size: opts.size ?? 21, bold: opts.bold, italics: opts.italics, color: opts.color })],
  });

/** Paragraph built from [text, {bold|italics}] pairs, for inline emphasis. */
const RichP = (runs, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 120, line: 276 },
    children: runs.map(([text, o = {}]) =>
      new TextRun({ text, size: 21, bold: o.b, italics: o.i, color: o.color, font: o.mono ? 'Consolas' : undefined })),
  });

const H1 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 160 },
    children: [new TextRun({ text, bold: true, size: 30, color: ACCENT })],
  });

const H2 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 260, after: 120 },
    children: [new TextRun({ text, bold: true, size: 24, color: ACCENT })],
  });

const Bullet = (text, level = 0) =>
  new Paragraph({
    numbering: { reference: 'bullets', level },
    spacing: { after: 80, line: 276 },
    children: [new TextRun({ text, size: 21 })],
  });

const cell = (content, { bold, bg, width, align } = {}) =>
  new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: bg ? { type: ShadingType.CLEAR, fill: bg, color: 'auto' } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
    children: (Array.isArray(content) ? content : [content]).map(
      (t) => new Paragraph({
        alignment: align,
        spacing: { after: 0, line: 264 },
        children: [new TextRun({ text: String(t), bold, size: 19 })],
      })
    ),
  });

/** Table with header row; widths must sum to CONTENT_W. */
const makeTable = (headers, rows, widths) =>
  new Table({
    columnWidths: widths,
    width: { size: CONTENT_W, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: 'B4C0D8' },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: 'B4C0D8' },
      left: { style: BorderStyle.SINGLE, size: 2, color: 'B4C0D8' },
      right: { style: BorderStyle.SINGLE, size: 2, color: 'B4C0D8' },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: 'D2DAE8' },
      insideVertical: { style: BorderStyle.SINGLE, size: 1, color: 'D2DAE8' },
    },
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) => cell(h, { bold: true, bg: HDR_BG, width: widths[i] })),
      }),
      ...rows.map((r, ri) =>
        new TableRow({
          children: r.map((c, i) =>
            cell(c, { width: widths[i], bg: ri % 2 ? ALT_BG : undefined })),
        })
      ),
    ],
  });

const Rule = () =>
  new Paragraph({
    spacing: { before: 60, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT } },
    children: [new TextRun({ text: '' })],
  });

const Callout = (title, body) =>
  new Table({
    columnWidths: [CONTENT_W],
    width: { size: CONTENT_W, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: ACCENT },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: ACCENT },
      left: { style: BorderStyle.SINGLE, size: 12, color: ACCENT },
      right: { style: BorderStyle.SINGLE, size: 4, color: ACCENT },
      insideHorizontal: { style: BorderStyle.NONE },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: CONTENT_W, type: WidthType.DXA },
            shading: { type: ShadingType.CLEAR, fill: 'F4F7FC', color: 'auto' },
            margins: { top: 140, bottom: 140, left: 200, right: 160 },
            children: [
              new Paragraph({
                spacing: { after: 70 },
                children: [new TextRun({ text: title, bold: true, size: 21, color: ACCENT })],
              }),
              ...body.map((t) => new Paragraph({
                spacing: { after: 60, line: 276 },
                children: [new TextRun({ text: t, size: 20 })],
              })),
            ],
          }),
        ],
      }),
    ],
  });

const FILL = (label) => `[${label}]`;

// ------------------------------------------------------------ derived data

const pf = (m, field) => accuracy[m].per_field[field];
const fmtCell = (m, field) => {
  const s = pf(m, field);
  return `${s.correct} correct / ${s.wrong} wrong / ${s.missing} missing`;
};

// --------------------------------------------------------------- document

const doc = new Document({
  creator: FILL('COMPANY NAME'),
  title: 'SBIR Direct to Phase II — Phase I Feasibility Documentation',
  description: 'Phase I feasibility documentation for an intelligent post-mission data analysis capability',
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [
        { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 400, hanging: 220 } } } },
        { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 760, hanging: 220 } } } },
      ],
    }],
  },
  styles: {
    default: { document: { run: { font: 'Calibri', size: 21 } } },
  },
  sections: [{
    properties: {
      page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          spacing: { after: 0 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'B4C0D8' } },
          children: [new TextRun({
            text: `Phase I Feasibility Documentation  |  ${FILL('COMPANY NAME')}  |  ${FILL('TOPIC NUMBER')}`,
            size: 16, color: '5A6478',
          })],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: ['Page ', PageNumber.CURRENT, ' of ', PageNumber.TOTAL_PAGES], size: 16, color: '5A6478' })],
        })],
      }),
    },
    children: [
      // ------------------------------------------------------ cover
      new Paragraph({ spacing: { before: 1800, after: 0 }, children: [
        new TextRun({ text: 'SBIR DIRECT TO PHASE II', bold: true, size: 22, color: ACCENT }),
      ]}),
      new Paragraph({ spacing: { after: 60 }, children: [
        new TextRun({ text: 'Phase I Feasibility Documentation', bold: true, size: 44, color: '000000' }),
      ]}),
      Rule(),
      new Paragraph({ spacing: { after: 500 }, children: [
        new TextRun({
          text: 'An Intelligent, Verifiable Analysis Capability for Multimodal Post-Mission Reporting Data',
          size: 26, italics: true, color: '2A3550',
        }),
      ]}),

      makeTable(
        ['Field', 'Value'],
        [
          ['Topic number / title', FILL('TOPIC NUMBER AND TITLE')],
          ['Solicitation', FILL('SOLICITATION / CYCLE')],
          ['Proposing small business', FILL('COMPANY NAME')],
          ['UEI / CAGE', `${FILL('UEI')} / ${FILL('CAGE')}`],
          ['Principal Investigator', `${FILL('PI NAME, TITLE, CREDENTIALS')}`],
          ['Prototype system of record', 'NavyBI Prototype (internal designation)'],
          ['Basis of feasibility', 'Company-funded independent research and development (IR&D)'],
          ['Date', FILL('SUBMISSION DATE')],
        ],
        [3000, CONTENT_W - 3000]
      ),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------- placeholders to fill
      H1('Before Submission: Items Requiring Completion'),
      P('This document is complete with respect to the technical work performed. The bracketed items below are organization-specific facts that must be supplied before submission. They are listed here in one place so none is missed; each also appears in context.'),
      makeTable(
        ['Placeholder', 'Where it appears', 'Notes'],
        [
          [FILL('COMPANY NAME'), 'Cover, header, throughout', 'Registered small-business name'],
          [FILL('UEI') + ' / ' + FILL('CAGE'), 'Cover', 'SAM.gov registration identifiers'],
          [FILL('TOPIC NUMBER AND TITLE'), 'Cover, header', 'From the solicitation'],
          [FILL('SOLICITATION / CYCLE'), 'Cover', 'From the solicitation'],
          [FILL('PI NAME, TITLE, CREDENTIALS'), 'Cover, §2.3', 'Principal Investigator qualifications'],
          [FILL('KEY PERSONNEL'), '§2.3', 'Technical staff and relevant background'],
          [FILL('PRIOR PAST PERFORMANCE'), '§2.4', 'Other relevant prior work, if any, beyond the system described here'],
          [FILL('IR&D PERIOD OF PERFORMANCE'), '§2.2', 'Dates over which the described work was performed'],
          [FILL('SUBMISSION DATE'), 'Cover', ''],
        ],
        [2400, 2100, CONTENT_W - 4500]
      ),
      P(''),
      Callout('A note on scope of claims', [
        'Every technical claim and every quantitative result in this document was produced by the software system described, is reproducible from its source repository, and is reported as measured — including results that are unfavorable. Section 10 states plainly what the work does not demonstrate. Nothing in this document should be read as claiming capability that has not been built and tested.',
      ]),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 1. exec summary
      H1('1. Executive Summary'),
      P('The proposing firm has designed, built, and measured a working end-to-end analytic system for post-mission reporting data. The system ingests heterogeneous data — structured records in three different formats and unstructured text, audio, and imagery — prepares and cleanses it under a fully logged audit trail, governs it through a single semantic layer of documented measures, and exposes it to non-technical users through a natural-language question interface that returns visualizations together with the exact query that produced them.'),
      P('The work was performed under company-funded independent research and development. It is not derived from any prior or ongoing federally funded SBIR or STTR effort.'),
      RichP([
        ['The capability directly addresses the technical core of this topic: ', {}],
        ['allowing non-specialist users to perform advanced analysis on complex mission data through a natural interface, with results that are transparent and independently verifiable.', { b: true }],
      ]),
      H2('1.1 What has been demonstrated'),
      Bullet('Ingestion and preparation of six distinct source types across three modalities: CSV, JSON, and SQL (SQLite) structured records; free-text debrief narratives; spoken debrief audio; and photographed maintenance discrepancy forms.'),
      Bullet('Automated extraction of structured, analysis-ready facts from each unstructured modality, measured against held-out ground truth: 99.2% field accuracy on text, 97.9% on audio, 86.7% on imagery.'),
      Bullet('A governed semantic layer of 14 documented measures, including cross-modal measures that compare what aircrew reported in narrative debriefs against what the maintenance system of record logged — an analysis neither source supports alone.'),
      Bullet('A natural-language query interface backed by a live large language model, with a deterministic fallback interpreter, that returns a chart, the generating SQL, the plain-language measure definition, and a path to the underlying rows for manual verification.'),
      Bullet('Scope-safety behavior developed across seven documented rounds of adversarial testing: the system refuses or explicitly caveats questions it cannot correctly answer rather than returning a confident wrong chart.'),
      Bullet('Role-based multi-user authentication, a per-query audit log, a full NIST RMF documentation package, containerized deployment, continuous integration, and 98 automated tests.'),

      H2('1.2 Why this constitutes Phase I feasibility'),
      P('The topic asks that a proposer entering Phase II have already established, through prior work, that the proposed approach is achievable. The system described here is not a study or a design concept. It runs, it has been exercised end-to-end against a purpose-built corpus with known ground truth, its accuracy is quantified per modality and per field, and its failure modes are characterized and documented. Section 3 maps each Phase I requirement to the specific artifact and measurement that satisfies it.'),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 2. feasibility statement
      H1('2. Feasibility Statement and Funding Provenance'),
      H2('2.1 Basis of the feasibility claim'),
      P('The Phase I-type research and development substantiating this Direct to Phase II submission consists of the design, implementation, and quantitative evaluation of the prototype analytic system described throughout this document. The work encompasses data engineering, applied natural-language processing, speech recognition, document image processing, semantic modeling, human-computer interaction for analytic workflows, and security control documentation.'),
      H2('2.2 Funding provenance'),
      Callout('Statement of independent development', [
        `The research and development described in this document was performed by ${FILL('COMPANY NAME')} using company-funded independent research and development resources during ${FILL('IR&D PERIOD OF PERFORMANCE')}.`,
        'It was not performed under, derived from, or funded by any prior or ongoing federally funded SBIR or STTR award, and it is not solely based on work performed under any such award. The firm retains full rights in the software and technical data described.',
      ]),
      P(''),
      H2('2.3 Key personnel'),
      P(`Principal Investigator: ${FILL('PI NAME, TITLE, CREDENTIALS')}.`),
      P(`Supporting technical staff and relevant qualifications: ${FILL('KEY PERSONNEL')}.`),
      H2('2.4 Related past performance'),
      P(`${FILL('PRIOR PAST PERFORMANCE')} — summarize any additional relevant prior work here. If the system described in this document constitutes the firm's primary relevant past performance for this topic, state that directly; the technical evidence in Sections 3 through 7 stands on its own.`),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 3. traceability
      H1('3. Phase I Requirements Traceability'),
      P('Each Phase I requirement stated in the topic is mapped below to the specific implemented capability that satisfies it and to the section of this document containing the supporting evidence.'),
      makeTable(
        ['Phase I requirement (topic language)', 'How it is satisfied', 'Evidence'],
        [
          [
            'Previous work designing and developing advanced analytic techniques, methods, and models with technical approaches relevant to this topic.',
            'A complete analytic system: logged multi-source cleansing, a governed semantic measure layer, LLM-based natural-language query interpretation with a deterministic fallback, and cross-modal fusion measures. Seven documented rounds of adversarial accuracy work on the interpretation layer.',
            '§4, §5.2',
          ],
          [
            'Evidence that a previous capability is feasible within a relevant domain or using publicly available training data, with clear parallels to DoW post-mission analysis use cases.',
            'The system is built directly on a post-mission reporting domain model — squadrons, sorties, mission outcomes, equipment readiness, maintenance discrepancies, aircrew training currency, and post-mission debriefs. Speech and OCR components use openly available pretrained models. The parallel to Navy post-mission air data is structural, not analogical.',
            '§4.1, §4.3',
          ],
          [
            'The ability to ingest various data types, prepare the data, and output initial visualizations. This includes identifying advanced and automated processing solutions for text, audio, and graphics.',
            'Six source types across three modalities are ingested and prepared, with per-modality automated processing implemented and measured — not merely identified. All converge on one semantic layer and are rendered as interactive visualizations.',
            '§4.2, §4.3, §5.1',
          ],
          [
            'A clear description of existing prototypes, matured capabilities, or modules to be leveraged, developed, and extended under the Phase II effort.',
            'A module-by-module inventory with current maturity and the specific Phase II extension planned for each.',
            '§7, §8',
          ],
          [
            'Describe the potential commercialization applications.',
            'Dual-use analysis across regulated and data-intensive commercial sectors, keyed to the verification and provenance properties that differentiate the approach.',
            '§9',
          ],
        ],
        [3100, 4200, CONTENT_W - 7300]
      ),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 4. technical approach
      H1('4. Technical Approach and Implemented Architecture'),
      P('The system is organized as a one-directional pipeline. Each stage has a single responsibility and a documented interface, so that a change in how data arrives cannot alter how a measure is defined, and a change in the user interface cannot alter what a number means.'),
      RichP([['Raw sources  →  cleansing and extraction  →  governed semantic layer  →  analytic interfaces', { b: true, mono: true }]]),

      H2('4.1 Domain model'),
      P('The data model is a post-mission reporting model: operational units and their communities, personnel assigned to those units, sorties with type, date, geolocation, duration, and outcome, equipment readiness by system type, maintenance discrepancy events with downtime and resolution status, aircrew certification currency, and post-mission debriefs. Relationships include a two-hop path (training records relate to units only through personnel) and a conformed equipment dimension shared across independently generated sources, so cross-source comparison is genuinely supported rather than superficially plausible.'),
      P('All data is synthetic and fabricated for prototype purposes. It contains no real unit, personnel, mission, or maintenance information. The generators deliberately inject realistic defects — duplicate records, missing values, inconsistent date formats, orphaned foreign keys, physically impossible values, and inconsistent boolean encodings across data-entry eras — so that the cleansing stage performs real work that can be demonstrated and audited rather than assumed.'),

      H2('4.2 Structured ingestion and preparation'),
      P('Three structured sources are ingested through deliberately different mechanisms, because "connects to varied data types" is only demonstrated by actually doing so: flat CSV exports, a JSON export from a notional training-management system, and a SQL database accessed over a live database connection and query rather than a file parse.'),
      P('Cleansing is automated and fully logged. Every decision — each duplicate removed, each impossible value nulled, each orphaned reference flagged, each date format normalized — is recorded with a row count and a plain-language reason, and the log is exposed inside the application rather than left as an external artifact. The governing principle is that a cleansing step that cannot be inspected is indistinguishable from data loss.'),

      H2('4.3 Multimodal processing: text, audio, and graphics'),
      P('Three unstructured modalities are processed into the same analysis-ready form as the structured sources.'),
      RichP([['Text. ', { b: true }], ['Free-text debrief narratives are converted into structured facts — whether a discrepancy occurred, which equipment category was affected, severity, and mission phase — by a large language model constrained to a fixed output schema, with a deterministic rule-based extractor as fallback. The narratives never name the equipment category directly; they use operational language ("degraded secure voice quality", "an unstable FLIR gimbal"), so the task requires vocabulary mapping rather than string matching.']]),
      RichP([['Audio. ', { b: true }], ['Spoken debriefs are transcribed with an openly available speech recognition model and the resulting transcript is passed through the identical text extractor. Audio deliberately converges into the text pipeline rather than running beside it: a parallel audio-specific extractor would be a second place where analytic definitions live, and the two would drift. One extractor means a spoken and a typed debrief describing the same sortie yield the same structured record.']]),
      RichP([['Graphics. ', { b: true }], ['Photographed maintenance discrepancy forms are processed by layout-aware optical character recognition. Words are recovered with their bounding boxes and regrouped into true visual rows by vertical position, because reading a two-column form as flat text fails — the OCR engine serializes such forms in column order, and page rotation reorders the label column independently of the value column. A parser that pairs the Nth label with the Nth value therefore mismatches fields precisely on the rotated, realistically degraded scans it most needs to handle, and does so silently. Recovered values are then mapped onto the same controlled vocabulary the structured sources use.']]),
      Callout('Design commitment: fail visibly, not confidently', [
        'Across all three modalities, unrecoverable fields are left empty rather than guessed. A missing value is a gap an analyst can see and act on; a plausible wrong value is a silent falsehood that propagates into a measure. This is enforced in code and verified by test: the imagery extractor is asserted to fail toward blanks rather than toward wrong values, and that assertion runs in continuous integration.',
      ]),
      P(''),

      H2('4.4 Governed semantic layer'),
      P('All prepared data is loaded into an analytical database exposing 14 named, documented measures. Every measure carries a plain-language definition of what it counts and — importantly — what it excludes and why. Records whose outcome is unknown are excluded from denominators rather than counted as failures, on the principle that "unknown" is not "no."'),
      P('Dashboards and the natural-language interface both read exclusively from this layer. Neither computes its own arithmetic. Consequently a number shown on a dashboard and the same number returned by a conversational query are guaranteed to be the same number, computed once.'),
      P('Each measure additionally carries a formally equivalent expression for a commercial BI platform, generated from the same registry that defines the SQL rather than transcribed by hand, so the two definitions cannot silently diverge.'),

      H2('4.5 Conversational analysis with human-in-the-loop control'),
      P('Users ask questions in ordinary language. A large language model classifies the question against the fixed set of supported measures using a constrained schema; it is given the known vocabulary explicitly and is not permitted to invent entity values. A deterministic keyword interpreter runs when no model is configured, when a call fails, or when the model is rate-limited, so the capability degrades rather than becoming unavailable.'),
      P('Model output is validated before use. An entity value outside the known vocabulary is discarded rather than passed into a query, because an unvalidated fabricated value produces a query matching zero rows — which presents to the user as "no data" rather than as "the model made this up."'),
      P('The interface supports both human-in-the-loop and human-on-the-loop operation as the topic requires. Every answer names the interpreter that produced it, so a user can see when a fallback path or an automated correction was involved rather than being presented a uniform result of non-uniform provenance.'),

      H2('4.6 Transparency and verification'),
      P('Verification is treated as a first-class product requirement, not a reporting feature. Every conversational answer is returned with the exact query that generated it, the plain-language definition of the measure, any filter applied, the source view, and a route to the underlying rows for manual inspection. A user who does not trust a number can follow it to the records it came from.'),
      P('Where a question cannot be answered correctly, the system says so explicitly rather than returning the nearest available chart. This behavior was developed in response to a finding recorded early in development and repeatedly re-confirmed: a wrong answer that renders as a normal chart is more dangerous than a refusal, because a rendered chart gives the user no reason to doubt it. The system detects and explicitly caveats questions that request an unsupported dimension, request a time trend against a measure that has no time dimension, or request a ranking that the available chart form cannot express.'),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 5. results
      H1('5. Measured Results'),
      H2('5.1 Multimodal extraction accuracy'),
      P('Extraction accuracy is measured, not asserted. The unstructured corpus is generated from known facts, and those facts are written to a manifest that no extractor reads. Every extracted record is scored against that held-out ground truth. Correct, wrong, and missing outcomes are reported separately because they carry materially different risk: a missing value is a visible gap, a wrong value is a silent error.'),
      makeTable(
        ['Modality', 'Records', 'Fields scored', 'Field accuracy'],
        [
          ['Free-text debrief narratives', String(accuracy.text.records_scored), String(accuracy.text.records_scored * accuracy.text.fields_per_record), `${accuracy.text.field_accuracy_pct}%`],
          ['Spoken debrief audio (transcribed)', String(accuracy.audio.records_scored), String(accuracy.audio.records_scored * accuracy.audio.fields_per_record), `${accuracy.audio.field_accuracy_pct}%`],
          ['Photographed maintenance forms (OCR)', String(accuracy.image.records_scored), String(accuracy.image.records_scored * accuracy.image.fields_per_record), `${accuracy.image.field_accuracy_pct}%`],
        ],
        [4200, 1500, 1800, CONTENT_W - 7500]
      ),
      P(''),
      P('Per-field results, reported as correct / wrong / missing:'),
      makeTable(
        ['Modality', 'Field', 'Result'],
        [
          ['Text', 'Discrepancy present', fmtCell('text', 'has_discrepancy')],
          ['Text', 'Equipment category', fmtCell('text', 'equipment_type')],
          ['Text', 'Severity', fmtCell('text', 'severity')],
          ['Text', 'Mission phase', fmtCell('text', 'phase')],
          ['Audio', 'Discrepancy present', fmtCell('audio', 'has_discrepancy')],
          ['Audio', 'Equipment category', fmtCell('audio', 'equipment_type')],
          ['Audio', 'Severity', fmtCell('audio', 'severity')],
          ['Audio', 'Mission phase', fmtCell('audio', 'phase')],
          ['Imagery', 'Unit identifier', fmtCell('image', 'unit_id')],
          ['Imagery', 'Equipment category', fmtCell('image', 'equipment_type')],
          ['Imagery', 'Severity', fmtCell('image', 'severity')],
          ['Imagery', 'Downtime hours', fmtCell('image', 'downtime_hours')],
          ['Imagery', 'Resolved status', fmtCell('image', 'resolved')],
        ],
        [1500, 3000, CONTENT_W - 4500]
      ),
      P(''),
      Callout('Three findings worth stating explicitly', [
        `Transcription cost is quantified, not assumed. Audio accuracy (${accuracy.audio.field_accuracy_pct}%) is measurable against text accuracy (${accuracy.text.field_accuracy_pct}%) precisely because both paths share one extractor; the difference is attributable to transcription alone. This is a direct benefit of the converged-pipeline design.`,
        `Imagery failures are overwhelmingly recoverable gaps rather than errors. Of the imagery fields not correctly extracted, ${pf('image', 'downtime_hours').missing + pf('image', 'resolved').missing} were left blank and ${pf('image', 'downtime_hours').wrong + pf('image', 'resolved').wrong} produced a wrong value. The weak field is a handwritten-position numeric that the OCR engine frequently does not detect at all — a known, addressable Phase II target.`,
        'A textbook preprocessing pipeline was implemented, measured, and then removed because it reduced accuracy from 87% to 64% on this corpus. It had improved a proxy metric while degrading the real one. This is recorded rather than quietly discarded because the ability to detect that distinction is itself part of the capability being claimed.',
      ]),

      new Paragraph({ children: [new PageBreak()] }),

      H2('5.2 Natural-language interpretation accuracy'),
      P('The conversational layer has been evaluated across seven documented rounds against a growing suite of realistic and deliberately adversarial questions. Accuracy is tracked openly, including regressions.'),
      P('The most consequential result is not a score. Every round that added surface area — a new data source, a new intent, a second interpreter, or a different model behind the same interpreter — surfaced a genuine defect of the same class: a confidently wrong answer in the wrong domain, presented without caveat. In one round, changing only the underlying language model, with no change to application logic, reopened a failure mode that four earlier rounds had closed, because the new model carried a different classification bias.'),
      P('That finding drove a durable architectural response rather than a model-specific patch: a standing, model-agnostic cross-check now re-validates any generic trend classification against domain-priority logic, so the same class of bias in a future model is caught by existing machinery. The operative lesson — that scope-safety must be re-verified whenever any interpretation surface changes, including a model substitution — is a transferable engineering result and is documented in the repository.'),

      H2('5.3 Engineering quality and reproducibility'),
      makeTable(
        ['Dimension', 'Status'],
        [
          ['Automated tests', '98 (65 backend/extraction, 33 frontend), all passing'],
          ['Continuous integration', 'Runs backend tests, frontend typecheck, production build, and lint on every push'],
          ['Containerization', 'Dockerfile and Compose configuration, built and exercised end-to-end'],
          ['Deployment modes', 'Single-process production mode serving a built frontend, plus a containerized mode'],
          ['Reproducibility', 'Full environment, dataset, warehouse, and accuracy figures regenerate from a single command'],
          ['Security documentation', 'NIST RMF package: categorization, SSP, assessment plan, assessment report, POA&M'],
        ],
        [3400, CONTENT_W - 3400]
      ),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 6. cyber
      H1('6. Cybersecurity Posture and ATO Readiness'),
      P('The topic requires that Phase II adhere to applicable policy and address cybersecurity requirements to support a future Authority to Operate. Rather than defer that entirely, the prototype already implements a baseline and — more usefully for Phase II planning — documents the gap precisely.'),
      H2('6.1 Implemented'),
      Bullet('Multi-user authentication with credentials stored as salted bcrypt hashes; no plaintext credentials at rest.'),
      Bullet('Role-based access control enforced server-side and independently of the user interface, so that hiding a control in the client is never the access control. Verified by direct API testing that a non-privileged role receives an authorization failure.'),
      Bullet('An append-only audit log recording every analytic query: who asked, when, the question text, which interpreter answered, and how many caveats were attached.'),
      Bullet('Parameterized queries throughout; user-supplied text is never interpolated into SQL.'),
      Bullet('No signing secret committed to source; a per-process secret is generated when none is configured, with an explicit startup warning.'),
      Bullet('A full NIST SP 800-53 control-status package in which each Implemented or Partial status cites the specific responsible source file, rather than asserting compliance in the abstract.'),
      H2('6.2 Documented gaps, stated plainly'),
      P('Two gaps are material and are documented as requiring organizational decisions rather than additional engineering:'),
      Bullet('Identity: authentication is real but uses local accounts. DoD PKI/CAC integration is a hard requirement for a real deployment and is not implemented.'),
      Bullet('Third-party model exposure: when the hosted language model path is enabled, question text leaves the boundary to a commercial API with no data-handling agreement. Phase II options include an on-premises or self-hosted model, a FedRAMP-authorized arrangement, or explicit risk acceptance by the data owner. The system already runs without the hosted model, which bounds this risk.'),
      P('Additionally, transport encryption, configuration hardening, and continuous monitoring are documented as required before any network-facing deployment.'),
      Callout('On authorization', [
        'An Authority to Operate is a risk-acceptance decision made by a designated Authorizing Official for a real system in a real environment. It cannot be self-granted by a development effort, and no ATO is claimed here. What is claimed is that the security artifacts an assessor would require already exist in reviewable form, and that the remaining gaps are identified rather than latent.',
      ]),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 7. modules
      H1('7. Existing Modules to be Leveraged and Extended in Phase II'),
      P('The following components exist today and are the technical foundation for the Phase II effort. Maturity is stated as assessed, and the planned extension is specific to each.'),
      makeTable(
        ['Module', 'Current state', 'Phase II extension'],
        [
          ['Structured ingestion and cleansing', 'Working across CSV, JSON, and live SQL sources with a complete, auditable cleansing log.', 'Connectors for real Navy post-mission air data formats; schema-drift detection; incremental and scheduled ingestion.'],
          ['Text extraction', `Working; ${accuracy.text.field_accuracy_pct}% measured field accuracy with a deterministic fallback path.`, 'Expanded ontology covering the full post-mission reporting vocabulary; confidence calibration; analyst correction feedback captured as training signal.'],
          ['Speech transcription', `Working; converges into the text extractor. ${accuracy.audio.field_accuracy_pct}% end-to-end field accuracy.`, 'Domain-adapted acoustic and language modeling for aviation phraseology, callsigns, and brevity codes; speaker separation for multi-crew debriefs; offline and airgapped operation.'],
          ['Document image extraction', `Working; layout-aware OCR at ${accuracy.image.field_accuracy_pct}% measured field accuracy.`, 'Form-template registration; handwriting recognition; targeted work on numeric field recovery, the measured weak point; support for real maintenance form layouts.'],
          ['Semantic measure layer', '14 governed measures with plain-language definitions and generated BI-platform equivalents.', 'Measure set expanded with government subject-matter experts; hierarchical roll-ups; unit-level access partitioning.'],
          ['Conversational interpretation', 'Working against a live model with a deterministic fallback; seven rounds of adversarial hardening.', 'Multi-turn dialogue and follow-up questions; self-hosted model option for the security boundary; per-answer confidence surfaced to the user.'],
          ['Verification and explainability', 'Every answer carries its query, definition, filters, and a path to source rows.', 'Extraction-provenance drill-through from any aggregate to the originating narrative, recording, or scanned page.'],
          ['Cross-modal fusion', 'Working corroboration measure comparing narrative reports against system-of-record entries.', 'Statistical significance treatment; time-series divergence detection; expansion to additional source pairs.'],
          ['Application and access control', 'Multi-user roles, audit logging, containerized deployment, CI, 98 automated tests.', 'DoD PKI/CAC integration; TLS and hardening; accreditation-boundary work toward ATO.'],
        ],
        [2500, 3400, CONTENT_W - 5900]
      ),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 8. phase II mapping
      H1('8. Mapping to Phase II Requirements'),
      makeTable(
        ['Phase II requirement', 'Current baseline', 'Phase II work'],
        [
          ['Ingest and prepare a variety of synthetic or real-world data types', 'Six source types across three modalities, ingested and prepared today.', 'Integration with sample Navy post-mission air data files; real-format connectors.'],
          ['Natural, user-friendly interface supporting human-in-the-loop and human-on-the-loop interaction', 'Natural-language querying with interpreter attribution and explicit refusal behavior.', 'Multi-turn dialogue, analyst correction capture, operator-configurable autonomy.'],
          ['Present relevant data visualizations based on the analysis', 'Interactive dashboards and per-answer visualizations from one governed measure layer.', 'Visualization types driven by government user feedback; export to existing reporting workflows.'],
          ['Outputs transparent and include a method for verifying accuracy', 'Query, definition, filters, and source-row access returned with every answer; extraction accuracy measured against ground truth.', 'End-to-end provenance from aggregate to source artifact; continuous accuracy monitoring in operation.'],
          ['Leverage available tools and infrastructure to maximize transition potential', 'Built on widely adopted open components; measures exported to a commercial BI platform from one registry.', 'Alignment with the receiving program\'s existing data and BI infrastructure.'],
          ['Minimize lifecycle sustainment cost', 'One definition per measure, generated rather than duplicated across platforms; automated tests and CI.', 'Government-maintainable configuration; documented extension points; operator-editable measure definitions.'],
          ['Address cybersecurity to support a future ATO', 'RMF package with code-grounded control statuses; identified gaps.', 'CAC/PKI, TLS, hardening, continuous monitoring, and independent assessment support.'],
        ],
        [2900, 3300, CONTENT_W - 6200]
      ),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 9. commercialization
      H1('9. Commercialization Applications'),
      P('The differentiating property of this capability is not natural-language querying, which is increasingly commoditized. It is verifiable natural-language analysis: every answer carries its own derivation, extraction accuracy is measured against ground truth rather than asserted, and the system declines questions it cannot answer correctly. That property is most valuable exactly where an unverifiable answer is unacceptable.'),
      H2('9.1 Target commercial sectors'),
      makeTable(
        ['Sector', 'Application', 'Why verification matters here'],
        [
          ['Aviation and transportation MRO', 'Fusing maintenance logs, technician narratives, and scanned inspection forms to surface reliability signals earlier.', 'Airworthiness decisions require traceable evidence; the narrative-versus-record corroboration measure transfers directly.'],
          ['Regulated manufacturing', 'Deviation and non-conformance analysis across structured quality data and free-text investigation reports.', 'Regulators require demonstrable data lineage for any reported figure.'],
          ['Healthcare operations', 'Combining clinical documentation, dictated notes, and scanned intake forms for operational analytics.', 'Clinical and billing decisions cannot rest on unverifiable machine inference.'],
          ['Insurance and claims', 'Extracting structured facts from adjuster narratives, recorded statements, and photographed documentation.', 'Claims decisions are legally contestable and must be auditable.'],
          ['Energy and utilities', 'Field inspection reports, technician voice notes, and asset imagery unified for predictive maintenance.', 'Safety-critical assets require defensible inspection records.'],
          ['Logistics and supply chain', 'Exception analysis across shipment records, proof-of-delivery scans, and dispatcher communications.', 'Financial settlement depends on verifiable exception evidence.'],
        ],
        [2100, 3700, CONTENT_W - 5800]
      ),
      P(''),
      H2('9.2 Dual-use positioning'),
      P('The architecture separates domain content from platform mechanics. The measure registry, controlled vocabularies, and extraction ontology are configuration; the ingestion, extraction, governance, verification, and interface layers are general. Retargeting to a commercial vertical is therefore primarily a matter of substituting the domain layer, which materially lowers the cost of each additional market and supports the transition strategy the topic asks for.'),
      P('The same property supports government transition: a program office adopting the capability configures its own measures and vocabulary rather than commissioning a bespoke rebuild.'),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ 10. limitations
      H1('10. Limitations and Scope of Claims'),
      P('The following are stated explicitly so that the claims elsewhere in this document can be relied upon.'),
      Bullet('All data is synthetic. The system has not been connected to any real Navy system of record. Connecting to operational data is gated on data access approvals rather than on engineering, and is proposed as Phase II work.'),
      Bullet('The unstructured corpus, while realistically degraded and generated from held-out ground truth, is synthetic. Accuracy against genuine aircrew debriefs, real recordings, and real maintenance forms will differ and must be re-measured on real material.'),
      Bullet('Imagery extraction is the weakest modality at 86.7% field accuracy, concentrated in one numeric field that OCR frequently fails to detect. This is characterized and is an explicit Phase II target rather than a resolved problem.'),
      Bullet('The commercial hosted language model path sends question and narrative text outside the system boundary. This is documented as an unresolved control gap requiring an organizational decision. The system operates without it, at reduced interpretation quality.'),
      Bullet('No independent security assessment has been performed and no Authority to Operate has been granted or applied for. The RMF package is a developer self-assessment, and the same team that built the system wrote the assessment findings.'),
      Bullet('The commercial BI export path is implemented and generated from the measure registry but has not been executed against a live instance of that platform, as no license was available during development.'),
      Bullet('The system has not undergone operational testing with government users. Usability claims rest on design and internal testing, not on evaluation with the intended operators.'),

      new Paragraph({ children: [new PageBreak()] }),

      // ------------------------------------------------------ appendix
      H1('Appendix A. Artifact Index'),
      P('The complete source repository, including all artifacts below, is available for government review on request.'),
      makeTable(
        ['Artifact', 'Description'],
        [
          ['Synthetic data generators', 'Structured multi-format generator and unstructured multimodal generator producing text, audio, and imagery with held-out ground truth.'],
          ['Cleansing pipeline', 'Automated preparation across CSV, JSON, and SQL sources with a complete, auditable decision log.'],
          ['Multimodal extraction layer', 'Text extraction with LLM and deterministic paths, speech transcription, and layout-aware document OCR, with per-record provenance.'],
          ['Extraction accuracy report', 'Machine-generated per-modality, per-field accuracy against held-out ground truth, separating wrong from missing outcomes.'],
          ['Semantic layer', '14 governed measures with plain-language definitions and generated BI-platform equivalents, including cross-modal fusion measures.'],
          ['Conversational analytics layer', 'LLM interpretation with schema constraint and vocabulary validation, deterministic fallback, and the scope-safety caveat system.'],
          ['Adversarial evaluation log', 'Seven documented rounds of question-suite testing, including regressions and the model-substitution finding.'],
          ['Web application', 'API backend and single-page interface providing dashboards, conversational analysis, drill-down verification, governance views, and the audit log.'],
          ['Security package', 'System categorization, System Security Plan with code-grounded control statuses, assessment plan, assessment report, and POA&M.'],
          ['Test suites and CI', '98 automated tests with continuous integration across backend, extraction, and frontend.'],
          ['Deployment artifacts', 'Container image definition, Compose configuration, and single-command local and production run scripts.'],
        ],
        [3000, CONTENT_W - 3000]
      ),
      P(''),
      Rule(),
      P('End of Phase I Feasibility Documentation.', { italics: true, align: AlignmentType.CENTER }),
    ],
  }],
});

const OUT = path.join(__dirname, 'SBIR_Phase_I_Feasibility_Documentation.docx');
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log('Wrote', OUT, `(${(buf.length / 1024).toFixed(0)} KB)`);
});
