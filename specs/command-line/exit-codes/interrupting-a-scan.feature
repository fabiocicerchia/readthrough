@domain:command-line @area:exit-codes @from:readthrough/cli
Feature: Interrupting a scan and the exit status
  Lets an operator stop a long, paid scan without losing recorded work, and lets CI read the exit status as 'did the run work', never as 'were there findings'.

  Background:
    Given a scan of "shop-api" with 400 passes is under way

  @id:command-line.exit-codes.001 @rule:cli.exit.findings-do-not-fail-the-run @gap @source:readthrough/cli.py#cmd_scan
  Scenario: Findings never change the exit status
    Given the scan completes and reports 2 critical findings
    When the scan finishes
    Then the command exits with status 0

  @id:command-line.exit-codes.002 @rule:cli.interrupt.first-ctrl-c-stops-gracefully @gap @source:readthrough/cli.py#_install_sigint @questionable
  Scenario: A first Ctrl-C lets in-flight passes finish, keeps their results and still writes the reports
    Given 120 passes have finished
    When the operator presses Ctrl-C once
    Then standard error shows "stopping after in-flight passes finish; progress is saved, re-run the same command to resume (Ctrl-C again to force)"
    And passes not yet started are not run and verification is skipped
    And the reports are written, counting files with no finished pass as never started
    And the command exits with status 0

  @id:command-line.exit-codes.003 @rule:cli.interrupt.second-ctrl-c-forces-exit @gap @source:readthrough/cli.py#_install_sigint
  Scenario: A second Ctrl-C forces an immediate exit with status 130
    Given the operator has already pressed Ctrl-C once and passes are still in flight
    When the operator presses Ctrl-C again
    Then standard error shows "forced exit"
    And the process ends at once with status 130, without writing reports
    And passes that had finished stay recorded for the next run to resume
