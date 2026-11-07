@domain:reporting @area:markdown-report @from:readthrough/report
Feature: Reading the audit report
  Gives a reviewer one human-readable document stating what ran, what was found and what was dismissed.

  Background:
    Given a scan of the repository has finished and its report has been produced

  @id:reporting.markdown-report.001 @rule:reporting.markdown.answering-model-disclosed @inferred @source:readthrough/report.py#render_markdown
  Scenario: The report discloses when a different model answered than the one requested
    Given the scan requested model "claude-sonnet-5"
    And the answers came from "claude-haiku-4-5-20251001"
    When the operator opens the Markdown report
    Then the header names the requested model "claude-sonnet-5"
    And a notice states the request was answered by "claude-haiku-4-5-20251001" and that each finding names its own model

  @id:reporting.markdown-report.002 @rule:reporting.markdown.clean-result-stated @inferred @source:readthrough/report.py#render_markdown
  Scenario: A scan with no surviving findings says so explicitly
    Given no finding survived merging and verification
    When the operator opens the Markdown report
    Then the Findings summary reads "No findings survived merging and verification."
    And the Coverage section is still shown above it
    And there is no Findings detail section

  @id:reporting.markdown-report.003 @rule:reporting.markdown.severity-summary @inferred @source:readthrough/report.py#render_markdown
  Scenario: The summary counts findings per severity, per file and per defect class
    Given the active findings are 1 critical, 2 high and 4 low
    When the operator opens the Markdown report
    Then the severity table shows CRITICAL 1, HIGH 2, LOW 4 and Total 7
    And no MEDIUM row is shown
    And the report lists the files with the most findings and the recurring defect classes with their counts

  @id:reporting.markdown-report.004 @rule:reporting.markdown.rejected-findings-set-aside @inferred @source:readthrough/report.py#render_markdown
  Scenario: Findings rejected by verification are kept out of the results but listed in the appendix
    Given the verification pass rejected 2 findings and confirmed 5
    When the operator opens the Markdown report
    Then the summary total is 5
    And a note says 2 additional findings were rejected and are listed in the appendix
    And the appendix "Rejected by verification" table shows each rejected finding's file, lines, title and why it was rejected

  @id:reporting.markdown-report.005 @rule:reporting.markdown.finding-detail-content @inferred @source:readthrough/report.py#render_markdown
  Scenario: Each finding shows where it is, how sure the tool is and what to do about it
    Given a high-severity finding in "app/db.py" lines 12-14 in "lookup", flagged by 2 of 7 passes, with a suggested fix and a verification verdict
    When the operator reads that finding in the report
    Then its heading shows "HIGH" and the finding title
    And its location line shows "app/db.py":12-14, in "lookup", the defect class, the confidence, "agreement 2/7" and the verification verdict
    And it shows the explanation, the suggested fix and the verifier's reasoning
    And it ends with the lenses that found it and its fingerprint

  @id:reporting.markdown-report.006 @rule:reporting.markdown.detail-capped-with-pointer @inferred @source:readthrough/report.py#render_markdown
  Scenario: Beyond 250 findings the report points to the full JSON export
    Given the scan has 300 active findings
    When the operator opens the Markdown report
    Then the Findings section details the first 250 in priority order
    And a note says 50 further findings were omitted and are all in "findings.json"
