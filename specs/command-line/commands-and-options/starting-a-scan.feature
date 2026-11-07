@domain:command-line @area:commands-and-options @from:readthrough/cli
Feature: Starting a scan of one repository
  Lets an operator audit one repository from the command line, refusing a bad invocation before any money is spent and leaving a complete set of reports when it finishes.

  Background:
    Given a repository directory "shop-api" containing source files

  @id:command-line.commands-and-options.001 @rule:cli.scan.refuses-invalid-invocation @verified @source:readthrough/cli.py#cmd_scan @test:tests/test_smoke.py#test_unknown_lens_is_rejected_before_spending_anything
  Scenario Outline: A scan with an unusable setup is refused before any pass runs
    Given <setup>
    When the operator runs `readthrough scan <target> <options>`
    Then the error "<message>" is printed on standard error
    And no pass is run
    And the command exits with status 2

    Examples:
      | setup                                           | target             | options                            | message                                                             |
      | "shop-api/README.md" is a file, not a directory | shop-api/README.md | --fake                             | not a directory: <absolute path of shop-api/README.md>              |
      | the repository exists                           | shop-api           | --fake --lenses injection,nonsense | unknown lenses: nonsense (followed by the list of available lenses) |
      | ANTHROPIC_API_KEY is not set in the environment | shop-api           |                                    | ANTHROPIC_API_KEY is not set (use --fake to dry-run)                |

  @id:command-line.commands-and-options.002 @rule:cli.scan.writes-full-report-set @gap @source:readthrough/cli.py#cmd_scan
  Scenario: A finished scan leaves every report and the resumable state in the output directory
    Given the operator has not chosen an output directory
    When the operator runs `readthrough scan shop-api --fake`
    Then the directory "readthrough-reports/shop-api" contains report.md, findings.json, coverage.json, findings.sarif and scan.db
    And the last printed line names the path of report.md
    And the command exits with status 0

  @id:command-line.commands-and-options.003 @rule:cli.scan.summary-shows-coverage-and-failures @gap @source:readthrough/cli.py#_summarise
  Scenario Outline: The end-of-run summary shows coverage, unreviewed files and active findings by severity
    Given a scan of "shop-api" where <failed> of 40 passes failed, leaving <unreviewed> files without a successful pass
    And the merged findings are 1 critical, 2 high and 1 high that verification rejected
    When the scan finishes
    Then the summary shows "coverage : <scanned>/12 files, <done>/40 passes"
    And <failure line>
    And the summary shows "findings : 1 critical, 2 high, 0 medium, 0 low"
    And the summary shows input and output token totals and the report path

    Examples:
      | failed | unreviewed | scanned | done | failure line                                                                         |
      | 0      | 0          | 12      | 40   | no FAILED line is shown                                                              |
      | 3      | 1          | 11      | 37   | the summary shows "FAILED   : 3 passes (1 files left unreviewed) -- re-run to retry" |

  @id:command-line.commands-and-options.004 @rule:cli.scan.rerun-resumes-completed-passes @gap @source:readthrough/cli.py#cmd_scan
  Scenario Outline: Re-running a scan skips passes already completed for unchanged content, unless forced
    Given "shop-api" was scanned once and none of its files has changed since
    When the operator runs the same scan command again <flag>
    Then <outcome>
    And the token totals in findings.json <tokens>

    Examples:
      | flag            | outcome                                                             | tokens                                                   |
      | without --force | it prints "resuming: N passes already complete" and "nothing to do" | are unchanged from the first run                         |
      | with --force    | every planned pass runs again                                       | count each pass's latest run only, not both runs summed |

  @id:command-line.commands-and-options.005 @rule:cli.scan.estimate-only-spends-nothing @gap @source:readthrough/cli.py#cmd_scan @questionable
  Scenario: An estimate-only scan reports expected token use without running any pass or writing reports
    Given "shop-api" has passes still to run
    When the operator runs `readthrough scan shop-api --estimate-only`
    Then the number of passes to run is printed
    And an "estimate: ~N input tokens, ~M output tokens" line is printed, with M equal to 500 per pass
    And no findings.json is written
    And the command exits with status 0

  @id:command-line.commands-and-options.006 @rule:cli.scan.limit-reviews-largest-files @gap @source:readthrough/cli.py#cmd_scan
  Scenario: A limited scan reviews only the largest eligible files
    Given "shop-api" has 12 eligible files
    When the operator runs `readthrough scan shop-api --limit 3`
    Then the message "--limit: reviewing the 3 largest" is printed
    And passes run only for the 3 eligible files with the most lines

  @id:command-line.commands-and-options.007 @rule:cli.output.progress-on-stderr-unless-quiet @gap @source:readthrough/cli.py#Progress
  Scenario Outline: Live progress goes to standard error and can be silenced
    Given "shop-api" has passes to run
    When the operator runs the scan <flag>
    Then <progress>
    And the scan's result lines still appear on standard output

    Examples:
      | flag            | progress                                                                                 |
      | without --quiet | standard error shows a running "N/T passes · F raw findings · X failed · eta MmSSs" line |
      | with --quiet    | no progress line is written                                                              |
