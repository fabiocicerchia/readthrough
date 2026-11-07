@domain:documentation @area:docs-theme @from:stylesheets/extra
Feature: Branding the documentation site
  Gives readers of the readthrough docs and splash page one consistent, legible, privacy-respecting look so the project reads as a single product.

  Background:
    Given the documentation site is built with the readthrough theme

  @id:docs.documentation.docs-theme.001 @rule:docs.theme.single-shared-palette @inferred @source:docs/stylesheets/extra.css#:root @questionable
  Scenario: The docs and the splash page share one orange-red accent palette
    Given the theme's accent pair is orange #fb923c and red #ef4444
    When the reader opens the splash page and then the rendered docs
    Then the docs primary colour is red #ef4444
    And the docs interactive accent uses orange #fb923c
    And the splash page headline and its GitHub button use the same orange-to-red pair

  @id:docs.documentation.docs-theme.002 @rule:docs.theme.links-legible-per-scheme @inferred @source:docs/stylesheets/extra.css#[data-md-color-scheme="slate"]
  Scenario Outline: Links stay readable in both light and dark schemes
    Given the reader views the docs in the <scheme> scheme
    When the reader reads a page containing links
    Then links are shown in <link_colour>
    And the page background is <background>

    Examples:
      | scheme | link_colour    | background                                    |
      | light  | red #ef4444    | the default light background                  |
      | dark   | orange #fb923c | near-black #0b0f1a, including header and tabs |

  @id:docs.documentation.docs-theme.003 @rule:docs.theme.no-network-assets @inferred @source:docs/stylesheets/extra.css#:root
  Scenario: The docs theme loads no fonts or assets over the network
    When the reader opens a docs page
    Then text uses the operating system's own sans-serif font
    And code uses the operating system's own monospace font
    And no web font, CDN or analytics request is made by the theme

  @id:docs.documentation.docs-theme.004 @rule:docs.theme.no-borrowed-logo @inferred @source:docs/stylesheets/extra.css#.md-header__button.md-logo
  Scenario: No stand-in logo is shown in place of a project logo
    Given the project has no logo configured
    When the reader views the docs header and navigation
    Then no logo icon appears in the header
    And no logo icon appears in the navigation title

  @id:docs.documentation.docs-theme.005 @rule:docs.theme.home-hero-accent @inferred @source:docs/stylesheets/extra.css#.md-typeset .hero h1
  Scenario: The home page headline and feature cards carry the accent palette
    Given the home page has a hero headline and feature cards
    When the reader opens the docs home page
    Then the hero headline is drawn in an orange-to-red gradient, centred
    And primary buttons are pill-shaped with an orange-to-red gradient and white text
    And feature card icons are orange
    And a hovered feature card lifts and gains an orange-tinted border

  @id:docs.documentation.docs-theme.006 @rule:docs.theme.button-hover-glow @inferred @source:docs/stylesheets/extra.css#.md-typeset .md-button:hover @questionable
  Scenario: Hovered buttons glow indigo whatever the accent palette
    Given the accent palette is orange-red
    When the reader hovers over a docs button
    Then the button lifts slightly and enlarges
    And the button casts an indigo glow, not an orange-red one
