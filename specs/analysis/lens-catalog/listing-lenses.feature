@domain:analysis @area:lens-catalog @from:readthrough/cli
Feature: Listing review lenses
  Shows an operator which review lenses exist and which run by default, so they can choose --lenses.

  @id:analysis.lens-catalog.001 @rule:cli.lenses.lists-with-defaults-marked @gap @source:readthrough/cli.py#cmd_lenses
  Scenario: Every lens is listed with its title and the default ones are starred
    When the operator runs `readthrough lenses`
    Then one line per available lens shows its id and title
    And lines of lenses enabled by default start with "*"
    And the listing ends with "* = enabled by default"
    And the command exits with status 0
