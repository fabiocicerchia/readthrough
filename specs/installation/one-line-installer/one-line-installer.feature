@domain:installation @area:one-line-installer @from:readthrough/install
Feature: Installing readthrough with the one-line installer
  Lets an operator put the readthrough command on their machine with a single piped shell command, choosing which version to install.

  Background:
    Given the operator runs the installer piped from the project's raw install.sh URL

  @id:installation.one-line-installer.001 @rule:installation.installer.prefers-pipx @inferred @source:install.sh
  Scenario: The installer uses pipx when it is available
    Given pipx is on the operator's PATH
    When the operator runs the installer
    Then the installer prints "installing readthrough with pipx (main)"
    And readthrough is installed with pipx from the project's git repository at ref main
    And an existing pipx installation of readthrough is replaced

  @id:installation.one-line-installer.002 @rule:installation.installer.falls-back-to-pip-user @inferred @source:install.sh
  Scenario: Without pipx the installer falls back to a per-user pip install
    Given pipx is not on the operator's PATH
    And python3 is on the operator's PATH
    When the operator runs the installer
    Then the installer prints "pipx not found; falling back to pip --user (main)"
    And readthrough is installed or upgraded into the operator's user site with pip

  @id:installation.one-line-installer.003 @rule:installation.installer.refuses-without-python @inferred @source:install.sh @questionable
  Scenario: The installer refuses to run when neither pipx nor Python is available
    Given neither pipx nor python3 is on the operator's PATH
    When the operator runs the installer
    Then the installer prints "need python3 (3.10+) or pipx on PATH" to standard error
    And the installer exits with status 1
    And nothing is installed

  @id:installation.one-line-installer.004 @rule:installation.installer.choose-ref @inferred @source:install.sh
  Scenario Outline: The operator can choose which tag or branch to install
    Given pipx is on the operator's PATH
    And READTHROUGH_REF is <ref setting>
    When the operator runs the installer
    Then the installer prints "installing readthrough with pipx (<ref>)"
    And readthrough is installed from the project's git repository at <ref>

    Examples:
      | ref setting | ref         |
      | unset       | main        |
      | v1.0.0      | v1.0.0      |
      | release/2.x | release/2.x |

  @id:installation.one-line-installer.005 @rule:installation.installer.warns-when-not-on-path @inferred @source:install.sh @questionable
  Scenario: An install that leaves readthrough off the PATH is reported as a failure with the fix
    Given the package install completes
    And the readthrough command is not on the operator's PATH afterwards
    When the operator runs the installer
    Then the installer prints "readthrough installed, but it is not on your PATH." to standard error
    And it suggests export PATH="$HOME/.local/bin:$PATH"
    And the installer exits with status 1

  @id:installation.one-line-installer.006 @rule:installation.installer.confirms-install @inferred @source:install.sh @questionable
  Scenario: A completed install confirms where readthrough lives and what to run next
    Given the package install completes
    And the readthrough command is on the operator's PATH
    When the operator runs the installer
    Then the installer prints "readthrough installed: " followed by the command's location
    And it prints "set ANTHROPIC_API_KEY, then: readthrough scan ./your-repo --fake"
    And the installer exits with status 0
