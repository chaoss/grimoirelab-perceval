# Contributing to GrimoireLab Perceval

These are some general guidelines and information related to how we contribute to 
GrimoireLab. You can read about it from the [CONTRIBUTING.md](https://github.com/chaoss/grimoirelab/blob/master/CONTRIBUTING.md).

## Changelog Entries

Some of your contributions will require a changelog entry which explains 
the motivation of the change. These entries would be included in the 
release notes to explain users and developers about the new features 
or bugs fixed in the software. This is an example of changelog entry:

```
title: 'Fix bug casting spells on magicians'
category: fixed
author: John Smith <jsmith@example.com>
issue: 666
notes: >
    The bug was making impossible to cast a spell on
    a magician.
```

Changelog entries will be written to explain *what* was changed and *why*, 
not *how*. Take into account not everybody is a developer and they are 
meant to reach a wider audience.

### What warrants a changelog entry

Changelog entries are **required** for:
- Code changes that directly affects the GrimoireLab users.
- Bug fixes.
- New updates.
- Performance improvements.

Changelog entries are **not required** for
- Docs-only (e.g., README.md) changes.
- Developer-facing change (e.g., test suite changes).
- Code refactoring.

### Writing changelog entries

These changelog entries should be written to the `releases/unreleased/` 
directory. The file is expected to be a [YAML](https://yaml.org/) file 
in the following format: 

```
title: 'Fix bug casting spells on magicians'
category: fixed
author: John Smith <jsmith@example.com>
issue: 666
notes: >
    The bug was making impossible to cast a spell on
    a magician.
```

The `title` field has the name of the change. This is a mandatory field.

The `category` field maps the category of the change, valid options are: 
added, fixed, changed, deprecated, removed, security, performance, other. 
This field is mandatory.

The `author` key (format: `Your Name <YourName@example.org>`) is used to 
give attribution to community contributors. This is an optional field but 
the Community contributors are encouraged to add their names.

The `issue` value is a reference to the issue, if any, that is targeted 
with this change. This is an optional field.

The `notes` field should have a description explaining the changes in the 
code. Remember you can write blocks of text using the `>` character at the 
beginning of each block. See the above given example.

Contributors can use the interactive [changelog](https://github.com/Bitergia/release-tools#changelog)
tool for this purpose which generates the changelog entry file automatically.

### Tips for writing good changelog entries

A good changelog entry should be descriptive and concise. It should explain 
the change to a reader who has *zero context* about the change. If you have 
trouble making it both concise and descriptive, err on the side of descriptive.

Use your best judgment and try to put yourself in the mindset of someone 
reading the compiled changelog. Does this entry add value? Does it offer 
context about *what* and *why* the change was made?

#### Examples

- **Bad:** Go to a project order.
- **Good:** Show a user’s starred projects at the top of the “Go to project” dropdown. 

The first example provides no context of where the change was made, or why, or 
how it benefits the user. 

- **Bad:** Copy (some text) to clipboard.
- **Good:** Update the “Copy to clipboard” tooltip to indicate what’s being copied. 

Again, the first example is too vague and provides no context.

- **Bad:** Fixes and Improves CSS and HTML problems in mini pipeline graph and builds dropdown.
- **Good:** Fix tooltips and hover states in mini pipeline graph and builds dropdown. 

The first example is too focused on implementation details. The user doesn’t care 
that we changed CSS and HTML, they care about the result of those changes.

- **Bad:** Strip out `nil`s in the Array of Commit objects returned from `find_commits_by_message_with_elastic`
- **Good:** Fix 500 errors caused by Elasticsearch results referencing garbage-collected commits 

The first example focuses on *how* we fixed something, not on *what* it fixes. 
The rewritten version clearly describes the *end benefit* to the user 
(fewer 500 errors), and *when* (searching commits with Elasticsearch).
