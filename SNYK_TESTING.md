# Snyk Testing Notes

This project was tested with the Snyk CLI and the `app-security-score` tool.

## Tool Used

`app-security-score` is a Docker-based security scoring tool that runs:

- `snyk test --all-projects --json` for dependency scanning (SCA)
- `snyk code test --json` for static code analysis (SAST)

Tool repo:

https://github.com/javiergarza-snyk/app-security-score

## Initial GitHub Repo Scan

The scanner was cloned locally:

```bash
git clone https://github.com/javiergarza-snyk/app-security-score.git /tmp/app-security-score
cd /tmp/app-security-score
```

Docker Desktop was started, then the scanner was run against the project GitHub repo:

```bash
export SNYK_TOKEN="<snyk-personal-access-token>"
node cli.mjs https://github.com/TessaAnselm/Protage_Hackathon911
```

Initial result:

```text
Repo: https://github.com/TessaAnselm/Protage_Hackathon911
  First-party Code:  H:0 M:7 L:0
  Dependencies:      H:0 M:0 L:0
  Score: 7.9/10
```

## Initial Findings

Snyk found 7 medium-severity DOM XSS findings in `frontend/app.js`.

The affected areas rendered dynamic content with `innerHTML`, including:

- Masked preview table
- Uploaded file chip
- Profile panel
- Recall panel
- Mapping table
- Reconciliation report
- RocketRide answer/error output

The reported findings were all:

```text
DOM-based Cross-site Scripting (XSS)
Severity: Medium
Rule: javascript/DOMXSS
```

Reported lines from the initial scan:

```text
frontend/app.js:102
frontend/app.js:106
frontend/app.js:164
frontend/app.js:180
frontend/app.js:360
frontend/app.js:393
frontend/app.js:395
```

## Fix Applied

The vulnerable rendering paths were changed to safe DOM creation:

- Replaced dynamic `innerHTML` rendering with `document.createElement(...)`
- Used `textContent` for file names, column names, API responses, model answers, and error messages
- Replaced empty-clearing `innerHTML = ""` calls with `replaceChildren()`
- Removed all `innerHTML`, `outerHTML`, and `insertAdjacentHTML` usage from `frontend/app.js`

Local verification:

```bash
rg -n "innerHTML|insertAdjacentHTML|outerHTML" frontend/app.js
node --check frontend/app.js
python -m py_compile backend/main.py backend/pipeline.py
```

The search returned no remaining unsafe HTML insertion APIs in `frontend/app.js`.

## Post-Fix Snyk Code Scan

After the fix, Snyk Code was run locally against the updated working tree:

```bash
export SNYK_TOKEN="<snyk-personal-access-token>"
snyk code test --json-file-output=/tmp/hackathon911-snyk-code.json
```

Post-fix result:

```text
Testing /Users/tessa/Desktop/Hackathon911 ...

Test type:    Static code analysis
Project path: /Users/tessa/Desktop/Hackathon911

Total issues: 0
```

## Before / After

```text
Before:
  First-party Code: H:0 M:7 L:0
  app-security-score: 7.9/10

After:
  Snyk Code: 0 issues
  Projected app-security-score after pushing the fix: 10/10 for first-party code
```

## Caveat

The post-fix `snyk code test` result validates the local working tree. The GitHub-based
`app-security-score` scan will continue to show the old result until the local fixes are
pushed to:

https://github.com/TessaAnselm/Protage_Hackathon911

Also, the dependency scan still needs the `backend/requirements.txt` dependency conflict
resolved before the dependency score can be fully trusted.
