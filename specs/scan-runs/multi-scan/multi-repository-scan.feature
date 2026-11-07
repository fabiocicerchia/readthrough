@domain:scan-runs @area:multi-scan @from:readthrough/cli
Feature: Scanning a fleet of repositories
  Lets an operator audit many repositories in one run and get a single rollup ranking them by risk.

  @id:scan-runs.multi-scan.001 @rule:cli.multi.repo-list-sources @gap @source:readthrough/cli.py#cmd_multi
  Scenario Outline: The repositories come from a directory of repos or a file of paths
    Given <listing>
    When the operator runs `readthrough multi <list> --fake`
    Then exactly the repositories <scanned> are scanned, each into its own folder under "readthrough-reports"
    And "readthrough-reports/rollup.md" and "readthrough-reports/rollup.json" are written

    Examples:
      | listing                                                                                                 | list      | scanned                             |
      | a directory "fleet" holding "billing", "shop-api" and a hidden ".cache" directory                       | fleet     | billing and shop-api, in name order |
      | a file "repos.txt" with a "# payments" comment line, a blank line and the paths of billing and shop-api | repos.txt | billing and shop-api, in file order |

  @id:scan-runs.multi-scan.002 @rule:cli.multi.failed-repo-recorded-in-rollup @gap @source:readthrough/cli.py#cmd_multi @questionable
  Scenario: A repository that cannot be scanned appears in the rollup with its error and the run carries on
    Given "repos.txt" lists "billing", a path "legacy" that does not exist, and "shop-api"
    When the operator runs `readthrough multi repos.txt --fake`
    Then "skipping, not a directory" is printed for legacy
    And billing and shop-api are still scanned
    And rollup.md has a row for legacy showing "—" for every count and "not a directory" under Failed passes
    And the command exits with status 0

  @id:scan-runs.multi-scan.003 @rule:cli.multi.rollup-ranks-by-risk @gap @source:readthrough/cli.py#cmd_multi
  Scenario: The rollup ranks repositories by critical and high findings and lists each one's top findings
    Given "billing" has 0 critical and 4 high findings
    And "shop-api" has 1 critical and 0 high findings, plus 1 critical finding that verification rejected
    When the operator runs `readthrough multi fleet --verify`
    Then rollup.md lists shop-api before billing
    And shop-api's row shows 1 critical, linked to "shop-api/report.md", with its coverage as scanned/eligible files
    And under "Highest priority findings across the fleet", each repository lists at most 5 findings as severity, file:line and title
    And the rejected finding appears nowhere in the rollup

  @id:scan-runs.multi-scan.004 @rule:cli.multi.ctrl-c-stops-remaining-repos @gap @source:readthrough/cli.py#cmd_multi @questionable
  Scenario: Ctrl-C during a fleet scan stops before the next repository and still writes the rollup
    Given "fleet" holds 5 repositories and the second one is being scanned
    When the operator presses Ctrl-C once
    Then the second repository's scan stops gracefully and its reports are written
    And "stopping; remaining repos not scanned" is printed
    And rollup.md covers only the first two repositories
