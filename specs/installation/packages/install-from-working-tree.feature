@domain:installation @area:packages @from:readthrough/makefile
Feature: Installing readthrough from a working tree
  Lets an operator put a checked-out copy of readthrough on their PATH, and take it off again, with a single command, preferring an isolated pipx install.

  Background:
    Given a checked-out copy of readthrough

  @id:installation.packages.001 @rule:installation.working-tree.prefers-pipx @inferred @source:Makefile#install
  Scenario: Installing from a working tree uses pipx when it is available
    Given pipx is available on the operator's machine
    When the operator runs make install
    Then readthrough is installed through pipx from the working tree
    And an existing pipx install of readthrough is replaced
    And no fallback warning is shown

  @id:installation.packages.002 @rule:installation.working-tree.falls-back-to-pip-user @inferred @source:Makefile#install
  Scenario: Without pipx, installing falls back to a per-user pip install and says so
    Given pipx is not available on the operator's machine
    When the operator runs make install
    Then the error stream shows "pipx not found; falling back to pip --user"
    And readthrough is installed or upgraded into the operator's user site with pip

  @id:installation.packages.003 @rule:installation.working-tree.warns-when-not-on-path @inferred @source:Makefile#install @questionable
  Scenario: An install that leaves the command off the PATH tells the operator how to fix it
    Given the install finished but the readthrough command cannot be found on the PATH
    When the operator runs make install
    Then the error stream shows 'installed, but not on PATH — add: export PATH="$HOME/.local/bin:$PATH"'
    And the install still counts as having worked

  @id:installation.packages.004 @rule:installation.working-tree.uninstall-either-method @inferred @source:Makefile#uninstall
  Scenario: Uninstalling removes readthrough however it was installed
    Given readthrough was installed with make install, through pipx or through pip
    When the operator runs make uninstall
    Then readthrough is removed through pipx when pipx knows it
    And otherwise readthrough is removed through pip without a confirmation prompt
