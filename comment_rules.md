# Code Comment Writing Rules

This document summarizes practical rules for writing code comments based on the uploaded text. It is organized so it can be reused as a team convention, project guideline, or report appendix.

## 1. Core Principles

### 1.1 Comments do not replace code quality
- Comments cannot justify or fix bad code.
- If code is hard to understand, refactoring should be considered first.
- Whenever possible, make the code express intent through better names, clearer structure, and smaller functions.

### 1.2 The best comment is often the one you do not need
- Do not write comments that can disappear with better naming.
- Prefer better alternatives before adding a comment:
  - better function names
  - better variable names
  - smaller functions
  - separation of responsibilities
  - extracted helper functions

### 1.3 A comment must add information that the code does not already show
- A comment that only repeats the code is not useful.
- A comment is meaningful only when it explains something such as:
  - why this implementation exists
  - what constraint applies
  - what side effect may happen
  - what edge case requires caution
  - what still needs to be done later

---

## 2. What Makes a Good Comment

The following kinds of comments can be useful when they are truly needed.

### 2.1 Legal comments
- Required legal notices such as copyright, license, or compliance information

### 2.2 Informative comments
- Comments that explain formats, conventions, input assumptions, or external dependencies that are not obvious from the code alone
- However, if a better function name or structure can replace the comment, improve the code first.

Examples:
- date and time string format
- meaning of a regular expression
- constraints from an external file format or protocol

### 2.3 Comments that explain intent
- Comments that explain why a certain approach was chosen, not just what the code is doing
- These are especially useful in testing, concurrency, workarounds, and performance tradeoffs.

Examples:
- creating many threads intentionally to provoke a race condition
- using a workaround for a browser or platform-specific bug

### 2.4 Clarifying comments
- Useful when explaining library behavior, external APIs, comparison rules, or encoding rules that are difficult to infer directly
- These comments must be accurate. An incorrect clarification is worse than no comment.

### 2.5 Warning comments
- Comments that warn about runtime cost, thread safety, data loss risk, side effects, or dangerous behavior

Examples:
- a test that takes a very long time
- an object that is not thread-safe
- an operation that handles very large files or large data volumes

### 2.6 TODO comments
- Used to mark unfinished work, temporary implementation, planned removal, or future improvement
- A good TODO should include both the reason and the direction.

A good TODO explains:
- why it cannot be done now
- how it should be improved later
- under what condition it can be removed

### 2.7 Amplifying comments
- Used when a very small line of code is actually extremely important
- These are helpful for code involving trim, normalization, byte order, boundaries, or special parsing behavior.

### 2.8 Public API documentation
- Well-written documentation for public APIs is helpful and appropriate
- Private or internal code does not need public-level documentation by default

---

## 3. What Makes a Bad Comment

The following types of comments should be avoided.

### 3.1 Mumbling comments
- Comments that may make sense only to the original author
- If a reader cannot understand the meaning directly from the comment, it has failed.

### 3.2 Redundant comments
- Comments that simply restate what the code already says

Bad example:
```java
i = i + 1; // Add one to i
```

### 3.3 Misleading comments
- Comments that are slightly wrong, outdated, or inconsistent with the real behavior
- Since the compiler does not verify comments, they can easily become false documentation.

### 3.4 Mandated comments
- Mechanical comments added to every function or every variable
- These rarely provide value and usually make the code harder to read.

### 3.5 Change-history comments
- Modification history written inside the file
- This belongs in version control systems such as Git, not in source comments.

### 3.6 Noise comments
- Comments that add no real value
- They often bury the few comments that actually matter

Examples:
- This is the default constructor.
- This is the name field.
- This is the day of the month.

### 3.7 Scary noise
- Comments that look formal but contain almost no information

Examples:
- The name.
- The version.

### 3.8 Comments that should be replaced with better code
- If a function, variable, or extracted helper can make the code self-explanatory, do that instead of adding a comment.

### 3.9 Banner or section-marker comments
- Decorative separators and loud visual markers used too often
- They usually reduce readability instead of improving it.

### 3.10 Closing brace comments
- Comments such as `} // if` or `} // while`
- These often indicate that blocks or functions have become too long.
- Shorter functions and simpler structure are usually better.

### 3.11 Attribution comments
- Comments stating who wrote a piece of code
- Version control already tracks this more accurately.

### 3.12 Commented-out code
- Old code left in place as comments
- If needed, it can be recovered from version control, so it should be deleted.

### 3.13 HTML comments in source code
- Styling comments with HTML inside the source
- Formatting is the responsibility of documentation tools, not code comments.

### 3.14 Nonlocal information
- Comments that describe distant system behavior instead of the nearby code
- The farther the comment is from the code it describes, the more likely it is to become wrong.

### 3.15 Too much information
- Large pasted blocks of RFC text, specifications, or background explanations
- Keep only the essential summary and use a link for the rest.

### 3.16 Obscure connection comments
- Comments whose relationship to the code is not clear
- If numbers, offsets, constants, or formulas are still unclear after the comment, the comment has failed.

### 3.17 Header comments for short functions
- Small, single-purpose functions usually do not need long header comments
- A well-chosen name is usually better.

### 3.18 Excessive Javadoc for non-public code
- Internal or private code generally does not need full public API style documentation

---

## 4. Practical Rules for Writing Comments

### Rule 1. Do not duplicate the code
- A comment should add information that is not already visible in the code.
- Do not write line-by-line translations of the implementation.

### Rule 2. Do not use comments to excuse poor code
- Do not hide bad names, long functions, or complex conditionals behind comments.
- Improve the code structure first.

### Rule 3. If you cannot write the comment clearly, the code may still be unclear
- A vague comment is often a sign of vague design or vague logic.
- Before writing the comment, check whether the code itself should be rewritten.

### Rule 4. Comments should reduce confusion
- A good comment lowers the number of questions a reader has.
- If the comment creates more interpretation work, it is not helping.

### Rule 5. Explain only the non-obvious parts
- Do not explain common idioms or obvious syntax.
- Do explain surprising behavior, exceptions, bug workarounds, and unusual constraints.

### Rule 6. Leave a source reference for borrowed code
- If code comes from Stack Overflow, an RFC, a standard, vendor documentation, or another external source, leave a reference.
- But do not paste code that you do not understand.

### Rule 7. Link to the most useful external references
- Links to specifications, formats, browser issues, protocols, or library documentation can save future readers a lot of time.
- Prefer a short explanation plus a trustworthy reference.

### Rule 8. Add background when fixing a bug
- Briefly explain:
  - why the fix is needed
  - under what condition the bug appears
  - whether the fix is temporary or permanent

### Rule 9. Mark incomplete implementation clearly
- Use TODO, FIXME, or NOTE to show current limitations and the intended future action.

---

## 5. Recommended Comment Styles

### 5.1 TODO
```text
// TODO: The current code always uses '.' as the decimal separator.
// Add locale-aware parsing and formatting later.
```

### 5.2 NOTE
```text
// NOTE: In Firefox, dragging outside the browser window may stop mouse-move events.
// This logic is a workaround for that behavior.
```

### 5.3 WARNING
```text
// WARNING: SimpleDateFormat is not thread-safe.
// Create a new instance for each use.
```

### 5.4 Why-focused explanation
```text
// Create many threads at once to increase the chance of reproducing a race condition.
```

---

## 6. Comment Writing Checklist

Before keeping a comment, ask the following:

- Does this comment add information the code does not already show?
- Am I explaining why instead of merely what?
- Can better naming or refactoring remove the need for this comment?
- Is the comment accurate today?
- Will another developer understand it without extra guessing?
- Would a short link to an external reference be better than a long pasted explanation?

If the answer to most of these is no, the comment should probably be removed or rewritten.

---

## 7. One-Sentence Summary

Write comments only when they provide necessary context that clean code alone cannot express, and avoid comments that repeat, excuse, decorate, or confuse the code.
