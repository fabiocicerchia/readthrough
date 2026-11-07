@domain:reporting @area:report-rebuild @from:readthrough/cli
Feature: Rebuilding reports from an earlier scan
  Lets an operator regenerate or read a scan's reports from its saved state without running or paying for any pass.

  Background:
    Given "readthrough-reports/shop-api" holds the scan.db of an earlier scan

  @id:reporting.report-rebuild.001 @rule:cli.report.rebuild-to-files-or-stdout @gap @source:readthrough/cli.py#cmd_report
  Scenario Outline: Reports are rebuilt to files, or printed as Markdown to standard output
    When the operator runs `readthrough report readthrough-reports/shop-api <flag>`
    Then <outcome>
    And the command exits with status 0

    Examples:
      | flag     | outcome                                                                                                                                     |
      | (none)   | report.md, findings.json, coverage.json and findings.sarif in that directory are rewritten and the coverage and findings summary is printed |
      | --stdout | the Markdown report is printed to standard output and no file is rewritten                                                                  |

  @id:reporting.report-rebuild.002 @rule:cli.report.missing-state-refused @gap @source:readthrough/cli.py#cmd_report
  Scenario: Rebuilding from a directory without saved scan state is refused
    Given the directory "readthrough-reports/billing" has no scan.db
    When the operator runs `readthrough report readthrough-reports/billing`
    Then "no scan.db in readthrough-reports/billing" is printed on standard error
    And the command exits with status 2

  @id:reporting.report-rebuild.003 @rule:cli.output.closed-pipe-is-not-an-error @gap @source:readthrough/cli.py#main
  Scenario: Piping output into a reader that closes early ends quietly with status 0
    When the operator runs `readthrough report readthrough-reports/shop-api --stdout | head -5`
    Then the first 5 lines of the report are shown
    And no error trace is printed
    And readthrough exits with status 0
