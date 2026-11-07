@domain:codebase-intake @area:file-discovery @from:readthrough/discover
Feature: Finding the files to audit
  Gives the operator an audit of the code they actually own, following git's view of the repository when there is one.

  @id:codebase-intake.file-discovery.001 @rule:intake.discovery.honours-gitignore @inferred @source:readthrough/discover.py#_git_tracked
  Scenario: In a git repository, ignored files are not audited but untracked ones are
    Given a git repository whose .gitignore lists "generated/"
    And it contains a committed "app/api.py", an uncommitted new "app/new.py" and "generated/client.py"
    When the operator scans the repository
    Then "app/api.py" and "app/new.py" are eligible
    And "generated/client.py" is not reviewed

  @id:codebase-intake.file-discovery.002 @rule:intake.discovery.hidden-dirs-depend-on-git @inferred @source:readthrough/discover.py#_walk @questionable
  Scenario Outline: Hidden directories are audited in a git repository but not in a plain directory
    Given a directory containing "<file>", a 30-line source file
    And the directory <is_git>
    When the operator scans the directory
    Then "<file>" is <outcome>

    Examples:
      | file                      | is_git                                      | outcome                     |
      | .github/workflows/ci.yml  | is a git repository with the file committed | eligible                    |
      | .github/workflows/ci.yml  | is not a git repository                     | not reviewed and not listed |
      | node_modules/lib/index.js | is a git repository with the file committed | not reviewed and not listed |
