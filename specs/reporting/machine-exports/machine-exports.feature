@domain:reporting @area:machine-exports @from:readthrough/report
Feature: Exporting findings for CI and code scanning
  Lets CI pipelines and code-scanning tools consume the audit's findings and coverage without parsing prose.

  Background:
    Given a scan of the repository has finished

  @id:reporting.machine-exports.001 @rule:reporting.exports.all-formats-written @verified @source:readthrough/report.py#write_reports @test:tests/test_smoke.py#test_scan_writes_every_report @test:tests/test_smoke.py#test_coverage_accounts_for_every_file
  Scenario: Every report produces Markdown, findings JSON, coverage JSON and SARIF together
    When the operator writes the reports to an output directory
    Then the directory contains "report.md", "findings.json", "coverage.json" and "findings.sarif"
    And "findings.json" holds the scan details, coverage, token usage and every finding, rejected ones included with their verdict
    And "coverage.json" holds the same coverage figures on their own

  @id:reporting.machine-exports.002 @rule:reporting.sarif.severity-to-level @verified @source:readthrough/report.py#to_sarif @test:tests/test_smoke.py#test_sarif_is_valid_json_with_a_run
  Scenario Outline: SARIF levels follow finding severity
    Given an active finding of severity <severity>
    When the operator uploads "findings.sarif" to code scanning
    Then the result's level is <level>
    And its rule is the finding's defect class
    And its message is the title followed by the explanation

    Examples:
      | severity | level   |
      | critical | error   |
      | high     | error   |
      | medium   | warning |
      | low      | note    |

  @id:reporting.machine-exports.003 @rule:reporting.sarif.rejected-findings-excluded @inferred @source:readthrough/report.py#to_sarif
  Scenario: Findings rejected by verification are not raised as code-scanning alerts
    Given the verification pass rejected one finding and confirmed another
    When the operator uploads "findings.sarif" to code scanning
    Then only the confirmed finding appears as a result
    And the rejected finding is still present in "findings.json" with verdict "rejected"

  @id:reporting.machine-exports.004 @rule:reporting.sarif.valid-location-and-fingerprint @inferred @source:readthrough/report.py#to_sarif
  Scenario Outline: Each SARIF alert has a valid line region and a stable fingerprint
    Given an active finding whose recorded lines are <start> to <end>
    When the operator uploads "findings.sarif" to code scanning
    Then the alert's region starts at line <sarif_start> and ends at line <sarif_end>
    And the alert carries the finding's fingerprint under "readthrough/v1"

    Examples:
      | start | end | sarif_start | sarif_end |
      | 12    | 14  | 12          | 14        |
      | 0     | 0   | 1           | 1         |
      | 20    | 15  | 20          | 20        |
