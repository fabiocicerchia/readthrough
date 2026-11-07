@domain:codebase-intake @area:file-filtering @from:readthrough/discover
Feature: Deciding which files get reviewed
  Lets an operator see which files the audit reviewed and why any were left out, so a clean report is never mistaken for an empty one.

  Background:
    Given a repository the operator wants to audit

  @id:codebase-intake.file-filtering.001 @rule:intake.filtering.eligible-source-file @verified @source:readthrough/discover.py#discover_files @test:tests/test_smoke.py#test_coverage_accounts_for_every_file
  Scenario: A readable source file of a known language within the limits is queued for review
    Given the repository contains "app/db.py", a 12-line Python text file of 400 bytes
    When the operator scans the repository with default settings
    Then "app/db.py" is counted as eligible
    And the console reports "1 files eligible, 0 skipped, 12 lines"
    And coverage.json reports files_eligible 1

  @id:codebase-intake.file-filtering.002 @rule:intake.filtering.skip-reason-recorded @inferred @source:readthrough/discover.py#discover_files
  Scenario Outline: A file that cannot be reviewed is listed as skipped with its reason
    Given the repository contains "<file>", which is <condition>
    When the operator scans the repository with default settings
    Then "<file>" is not reviewed
    And the coverage report lists "<file>" as skipped with reason "<reason>"

    Examples:
      | file             | condition                                | reason                                                           |
      | assets/logo.py   | binary content containing NUL bytes      | binary                                                           |
      | data/fixtures.py | 500000 bytes, over the 400000-byte limit | exceeds --max-file-bytes (500000 > 400000)                       |
      | app/__init__.py  | a single line of code                    | too short to review                                              |
      | legacy/report.py | unreadable because of file permissions   | unreadable: [Errno 13] Permission denied: '.../legacy/report.py' |

  @id:codebase-intake.file-filtering.003 @rule:intake.filtering.out-of-scope-files-omitted @inferred @source:readthrough/discover.py#discover_files @questionable
  Scenario Outline: Files filtered out by scope rules leave no trace in the coverage report
    Given the repository contains "<file>", which <why>
    When the operator scans the repository with <options>
    Then "<file>" is not reviewed
    And "<file>" appears in neither the eligible nor the skipped files of the coverage report

    Examples:
      | file                       | why                                     | options             |
      | tests/test_api.py          | matches an exclude pattern              | --exclude 'tests/*' |
      | README.md                  | has an extension with no known language | default settings    |
      | app/views.ts               | is outside the requested extensions     | --ext py            |
      | web/app.min.js             | is a minified bundle                    | default settings    |
      | db/migrations/0001_init.py | sits in a migrations directory          | default settings    |
      | app/link.py                | is a symbolic link                      | default settings    |

  @id:codebase-intake.file-filtering.004 @rule:intake.filtering.extension-allowlist @inferred @source:readthrough/discover.py#discover_files
  Scenario Outline: Choosing extensions reviews exactly those extensions, even ones with no known language
    Given the repository contains "notes/setup.txt" and "app/main.py", both readable text files of 20 lines
    When the operator scans the repository with --ext <ext>
    Then "<reviewed>" is eligible with language "<language>"
    And "<left_out>" is not reviewed

    Examples:
      | ext | reviewed        | language | left_out        |
      | txt | notes/setup.txt | txt      | app/main.py     |
      | py  | app/main.py     | Python   | notes/setup.txt |
