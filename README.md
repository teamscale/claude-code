# Teamscale Marketplace for Claude Code

A [Claude Code plugin marketplace](https://code.claude.com/docs/en/discover-plugins)
to integrate [Teamscale](https://teamscale.com/)'s quality information with Claude Code.

## Installation

The marketplace is hosted on GitHub at
[`teamscale/claude-code`](https://github.com/teamscale/claude-code).

1. From within Claude Code, register the marketplace:

   ```
   /plugin marketplace add teamscale/claude-code
   ```

2. Install the plugin you want (see the list below). For example:

   ```
   /plugin install teamscale@teamscale-plugins
   ```

3. Activate the newly installed plugin without restarting Claude Code:

   ```
   /reload-plugins
   ```

You can also browse and install plugins through the interactive UI by running
`/plugin` and switching to the **Discover** tab.

## Included plugins

| Plugin | Description |
|--------|-------------|
| [`teamscale`](plugins/teamscale/README.md) | Detect and fix Teamscale findings, close test gaps on a pull request, and run pre-commit analysis on local changes. |

## Requirements

The plugins in this marketplace integrate with a running Teamscale instance and
rely on the [`teamscale-dev`](https://docs.teamscale.com/howto/integrating-with-development/teamscale-dev/)
CLI. See the individual plugin README for the exact prerequisites and setup
steps.

## Support

For issues or questions, contact <support@teamscale.com>.
