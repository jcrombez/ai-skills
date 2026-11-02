# ai-skills

A library of skills for [Claude Code](https://code.claude.com).

## Installation

The quickest way, in Claude Code (version 2.1.275 or later):

```
/plugin install blender-modular-kit --marketplace jcrombez/ai-skills
```

In two steps: add the library, then install a skill.

```
/plugin marketplace add jcrombez/ai-skills
/plugin install blender-modular-kit@ai-skills
```

Or from a terminal:

```bash
claude plugin marketplace add jcrombez/ai-skills
claude plugin install blender-modular-kit@ai-skills
```

Skills installed from a terminal are loaded at the next session (or after `/reload-plugins`).

### Updates

Auto-update is off by default for third-party libraries.
To turn it on: `/plugin` > Marketplaces > `ai-skills` > Enable auto-update.
Otherwise, update manually:

```bash
claude plugin marketplace update ai-skills
claude plugin update blender-modular-kit@ai-skills
```

## Available skills

| Skill | Description |
|---|---|
| [blender-modular-kit](plugins/blender-modular-kit/skills/blender-modular-kit/SKILL.md) | Design a modular low/mid poly 3D kit in Blender (grid, conventions, corners, roofs), assemble an example and hunt down z-fighting. Ships a Python helper library (`kit_lib.py`) and a z-fight detector (`zfight_check.py`). |

## Layout

```
.claude-plugin/marketplace.json        library catalog
plugins/<plugin>/
  .claude-plugin/plugin.json           plugin description and version
  skills/<skill>/SKILL.md              the skill and its files (scripts/, references/)
```

Each skill ships in a plugin of the same name. Once installed, it triggers automatically
based on its description, or can be invoked explicitly with `/<plugin>:<skill>`
(e.g. `/blender-modular-kit:blender-modular-kit`).

## Publishing or updating a skill

1. Create `plugins/<name>/skills/<name>/SKILL.md` and `plugins/<name>/.claude-plugin/plugin.json`.
2. Declare it in `.claude-plugin/marketplace.json`.
3. Whenever an existing skill changes, bump `version` in its `plugin.json`:
   users only receive the update when the version changes.
4. Validate:

```bash
claude plugin validate . --strict
```
