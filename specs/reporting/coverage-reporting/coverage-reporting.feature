@domain:reporting @area:coverage-reporting @from:readthrough/report
Feature: Showing what was and was not reviewed
  Lets an operator tell a clean audit from one that never looked, by stating which files were reviewed, skipped, failed or never started.

  Background:
    Given a scan of the repository has finished and its report has been produced

  @id:reporting.coverage-reporting.001 @rule:reporting.coverage.unreviewed-files-flagged-as-gaps @inferred @source:readthrough/report.py#render_markdown
  Scenario: Files with no successful pass are called out as unreviewed
    Given every pass over "app/db.py" failed
    And at least one pass over "app/api.py" succeeded
    When the operator opens the Markdown report
    Then the Coverage section shows a "Gaps" notice saying the listed files are unreviewed
    And "app/db.py" is listed under Gaps
    And "app/api.py" is not listed under Gaps
    And when more than 60 files are unreviewed, only 60 are listed followed by "... and N more"

  @id:reporting.coverage-reporting.002 @rule:reporting.coverage.partial-files-flagged @inferred @source:readthrough/report.py#render_markdown
  Scenario: Files where some passes failed are reported as incomplete
    Given one lens failed on "app/db.py" while the other lenses succeeded on it
    When the operator opens the Markdown report
    Then the Coverage section shows a "Partial" notice with the number of such files
    And the notice says their results are incomplete and points to the appendix
    And "app/db.py" still counts as scanned

  @id:reporting.coverage-reporting.003 @rule:reporting.coverage.not-started-files-flagged @inferred @source:readthrough/report.py#build_results
  Scenario: Eligible files that were never queued are reported with advice to re-run
    Given 3 eligible files have no recorded pass, because the run was interrupted
    When the operator opens the Markdown report
    Then the Coverage table shows "Never started" as 3
    And a "Not started" notice says 3 eligible files were never queued and to re-run the same command to finish

  @id:reporting.coverage-reporting.004 @rule:reporting.coverage.failed-passes-itemised @verified @source:readthrough/report.py#render_markdown @test:tests/test_smoke.py#test_coverage_accounts_for_every_file
  Scenario Outline: Every failed pass is itemised with its error, and a run with none says so
    Given the scan has <failures> failed passes
    When the operator opens the Markdown report
    Then the Coverage table shows "Passes run" as done of total and "Passes failed" as <failures>
    And the appendix "Failed passes" section shows <appendix>

    Examples:
      | failures | appendix                                                                                                   |
      | 0        | "None. Every queued pass completed."                                                                       |
      | 2        | a table of file, lens, lines, attempts and error for each failed pass, noting that re-running resumes them |

  @id:reporting.coverage-reporting.005 @rule:reporting.coverage.skipped-files-with-reasons @inferred @source:readthrough/report.py#render_markdown
  Scenario: Skipped files are counted by reason and listed individually
    Given 2 files were skipped as binary and 1 as too large
    When the operator opens the Markdown report
    Then the Coverage table shows "Skipped by filter" as 3
    And the appendix "Skipped files" section shows a count per reason
    And a collapsible full list names each skipped file with its reason
