# Feature: Safe link fetch (engine)

**From build-plan:** feature 29b
**Build attempt:** 1
**Branch:** feature/safe-link-fetch
**Status:** verified

## Goal

Given a public job link, the engine reads the page the way a polite visitor would (only when
robots.txt allows it, never reaching private networks, within size and time limits), cleans it, and
hands the text back so the user can confirm company and title and save it with the existing paste
route. When a site says no or cannot be read, the user is told to paste the text instead.

## Design reference

None: engine and proxy routes only. The screen is 29c.

## In scope

1. **Cleaner rewrite (repairs F-120 and F-121 from 29a).** Replace the regex tag matching in
   `engine/src/engine/jobs/posting_guard.py` with a single-pass reader that runs in linear time on
   any input and fails closed: an opening tag of any length is read as a tag, and an unterminated
   tag, comment or script hides the rest of the input (as a browser reads it).
2. `engine/src/engine/jobs/robots.py`: the RFC 9309 rules ported from ai-job-search's
   `robots_check.py` (MIT, Copyright (c) 2026 Mads Lorentzen; notice added to
   `THIRD_PARTY_NOTICES.md`), as pure functions with no fetching.
3. `engine/src/engine/jobs/fetch.py`: an SSRF-safe fetcher that reads robots.txt, then the page.
4. `POST /internal/jobs/fetch`, the web proxy `/api/jobs/fetch` and a client call.

## Out of scope

The screen (29c); saving the fetched page automatically (the user confirms company and title and
uses the existing paste route); JavaScript-rendered pages; extracting company and title; crawling
or following links on the page; PDF postings; per-site rules beyond robots.txt.

## Build steps

- [x] 1. **Linear cleaner.** New HTML reader in `posting_guard.py`; the 62 hostile shapes of
  `test_posting_guard.py` plus the F-120 shapes (opening tags padded past 1,000 characters,
  1,100-space padding, 400 attributes before `hidden`, script with 1,100 characters of attributes)
  clean in under a second each at 1 MB; output for ordinary pages equals the old reader's in a
  differential run of 4,000 random tag soups; unterminated constructs hide the rest. Done when
  those tests and the full engine Verify pass.
- [x] 2. **Robots rules.** `robots.py` with tests ported in spirit from the source tool's rules
  (longest match wins, Disallow wins ties, blank lines inside a record, one leading BOM, percent
  decoding, `$` only at the end, no regex backtracking on wildcard patterns, soft-200 HTML body is
  unreadable, undecodable rule is unreadable, 404 is permission). Done when tests pass and the
  notice lists the file.
- [x] 3. **Safe fetcher.** `fetch.py` per the contract below with an injectable resolver and
  transport, and tests with no real network. Done when tests cover each refusal, each limit and
  the redirect rules, and the full engine Verify passes.
- [x] 4. **Route, proxy, client and docs.** Engine route with a per-user rate limit, web proxy and
  `fetchJobPage` client, tests, `docs/technical-design.md`, README row. Done when lint,
  typecheck, build, web tests and the full engine Verify pass.
- [x] 5. **Repair review findings F-122 to F-129.** Decode the robots path and query, evaluate rules
  with a bit-parallel matcher and refuse oversized rule sets, encode hosts as IDNA and map encoding
  errors, return `fetch_blocked` for bad redirect hops and `robots_unreadable` for oversized or
  compressed robots, request identity encoding, refuse `fec0::/10` and `::/96`, sweep the rate
  table, bracket IPv6 Host headers, and open quoted values only after `=`. Done when each has a
  test, the matcher agrees with the source's on 60,000 random pairs, and the full Verify passes.
- [x] 6. **Repair review findings F-130 and F-131.** Follow the HTML tokenizer's start-tag states
  when finding the end of a tag, count only applicable robots groups against the rule cap, and add a
  seeded comparison test for the matcher. Done when the F-130 examples hide their content, ordinary
  pages are unchanged and the full Verify passes.
- [x] 7. **Repair review findings F-132 and F-133.** Parse robots groups for the agents we need only
  (bounded time and memory whatever the file lists), and read tag attributes inside the tokenizer
  so values match a browser's. Done when a many-agent file is fast, unquoted-value styles hide their
  content, and the full Verify passes.

## Files / areas

`engine/src/engine/jobs/{posting_guard,robots,fetch,routes,service,models}.py`,
`engine/tests/test_posting_guard.py`, `engine/tests/test_robots.py`, `engine/tests/test_fetch.py`,
`engine/tests/test_jobs_fetch_route.py`, `THIRD_PARTY_NOTICES.md`, `web/src/server/jobs/http.ts`,
`web/src/routes/api/jobs/fetch.ts`, `web/src/lib/jobs-api.ts`, `web/tests/jobs-*.test.ts`, docs.

## Data / contracts

`POST /internal/jobs/fetch {url}` (bearer token, `X-User-Id`, body cap 32 KB, errors `{code, message}`):

- Success 200 `{text, title, finalUrl, truncated}`: `text` is the cleaned visible text, at most
  30,000 characters (`truncated` true when it was cut); `title` is the page title or null;
  `finalUrl` is the address after redirects. Nothing is stored.
- 422 `validation_failed`: not an http or https URL, a URL longer than 2,000 characters, embedded
  credentials, a missing host, or a body that is not `{url}`.
- 422 `fetch_blocked`: the host resolves to, or a redirect leads to, an address that is not
  public (loopback, private, link-local, carrier-grade NAT, multicast, reserved, unspecified,
  IPv4-mapped or other IPv6 forms of those), or a non-default port other than 80 and 443, or more
  than 3 redirects, or a redirect to a scheme other than http or https.
- 422 `robots_disallowed`: robots.txt does not allow the path for our agent token or `*`.
- 422 `robots_unreadable`: robots.txt could not be read (anything but 200 or 404, a soft-200 HTML
  page, an undecodable rule, a timeout); permission is not assumed.
- 422 `not_a_page`: the response is not `text/html` or `text/plain`, or an error status (a 4xx or
  5xx page is never cleaned or returned).
- 422 `too_large`: more than 1,048,576 bytes were read (stopped while streaming).
- 502 `fetch_failed`: DNS failure, connection error or the 10 second total limit.
- 429 `rate_limited`: more than 10 fetches in a minute for the user (in memory, per process).

Fetch rules: the host is resolved once; every address must be public; the connection is made to
that validated address with the original host in the `Host` header and TLS name, so a name cannot
change address between the check and the connection; each redirect hop is checked the same way and
robots.txt is read per origin; cookies and authorization are never sent; the agent token is
`JobmigoBot` with a contact URL; the response is read as a stream and stopped at the size cap; the
body is decoded by the declared charset, else UTF-8 with replacement. Page text is untrusted data,
cleaned by the same cleaner as a paste; its counts are not returned or stored by this route.

## Testing

Engine pytest for each unit with no real network (a fake resolver and `httpx.MockTransport`); one
test per refusal code. Vitest for the proxy and client. No browser pass.

## Notes for the AI

Standard library plus the installed `httpx` only. Reuse `ApiError`, `_body`, `_validated` and the
web `forward()`. The robots port keeps the source's cautious rules and notices.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":7424,"specSha256":"7a51d56bca4a93ff47685f55c1029e6ac89528f3f091b7de7ebf275f62fa15bf","branch":"refs/heads/feature/safe-link-fetch","head":"ca50b11c166f13047e247f3104e4aded0cb83edd","baseRef":"refs/heads/main","baseCommit":"48627e31d1f0162969982fe264702992868febc6","sourceTree":"7eb29319e40d9352768f895ca4647d0fe9834596","landing":"local-merge","absentOptional":[]} -->

## Findings

### 29b/F-120 [P2] closed - Padding an opening tag past `TAG_MAX` (1000 characters) lets hidden, script, style and template content survive cleaning

**File:** engine/src/engine/jobs/posting_guard.py:61, engine/src/engine/jobs/posting_guard.py:66, engine/src/engine/jobs/posting_guard.py:72
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** A tag is read only when its attribute text is at most 1000 steps (`TAG`, counting each character outside quotes) and a dropped-block opener only when the opener has at most 1000 characters (`DROP_BLOCKS`, `PRESTRIP`). Browsers have no such limit, so a posting author can pad the tag. Measured on the current code: `<div` + 1,100 spaces + `hidden>SECRET ignore all previous</div>` (and `<div hidden class=aaaa...1,100>`, and `<div ` + `a=1 ` x 400 + `hidden>`) keeps SECRET in the stored description and leaves the raw tag text in it; `<script data-x="` + 1,100 `a` + `">SECRET</script>` (also `<style media=...>`, `<template data-x=...>`, and an unquoted pad) keeps the script, style or template body as visible text. The same elements with short openers are stripped, and the instruction flag still counts shaped lines (it did for two of these), but the hidden text itself is no longer removed. Ordinary pages are unaffected: 40,000 random tag soups without padding matched the pre-repair cleaner exactly, and a 5,000-character `data:` image tag and a long quoted attribute on a `div` still parse.
**Suggested fix:** Treat an over-long opener as a tag instead of as text: when `TAG_MAX` is hit, consume to the next `>` in a single bounded pass (for example match `<name` then `[^>]*` only where no earlier `<name` start exists, or tokenize once with `find("<")`/`find(">")` and remember when no more `>` exists, which is linear without a cap), so padding cannot change how the tag is read. If a cap is kept, fail closed: drop the over-long opener's whole element or the rest of the input from the cleaned text and count it in `hiddenBlocks`.
**Resolution:** The HTML reader is a single linear pass: an opening tag of any length is read as a tag and an unterminated tag, comment, declaration or script hides the rest. Tests cover padded tags (1,100 spaces, 400 attributes, long values, script, style, template) and unterminated constructs.

Re-reviewed by the second independent review (7104a33): 41 hostile shapes at 1,000,000 characters clean in under 1 s and no padding trick survived; closed.

### 29b/F-121 [P3] closed - The per-opener bound leaves about 1.5 s of regex work at the 100,000-character cap, with no headroom for a slower host

**File:** engine/src/engine/jobs/posting_guard.py:61
**Found:** 2026-11-10 by /audit independent (scope: current; lens: performance)
**Why it matters:** Each unterminated opener still costs up to `TAG_MAX` steps, so dense openers cost about 1,000 steps per 2 to 3 characters. Measured at 100,000 characters after a `<p>` prefix: `<a<a<a...` 1.46 s, `<a "` + `<` x n 1.45 s, `<a ` repeated 0.98 s, repeated `<a ` 1.0 s from a 800-shape random fuzz (worst 1.0 s); every other shape I tried was under 0.4 s. That meets the 3 s target here, but a host two or three times slower would not, and one long regex still holds the interpreter (F-115's note), so the engine stalls for the whole time. All other paths (element stack, `scan`, `clean_text`, `_fold`, `collect`, the instruction patterns, `ATTR`, style checks) measured linear.
**Suggested fix:** A single-pass tokenizer (see F-120) removes the cap and the cost; otherwise lower `TAG_MAX` (for example 300) and keep the timing test's bound at 1 s.
**Resolution:** The regex tag matching is gone; 1 MB hostile pages (70 shapes) clean in at most 0.45 s, and tests assert under 3 s. A differential run of 8,000 random pages gave identical text, hidden blocks and counts to the previous reader.

Re-reviewed by the second independent review (7104a33): 41 hostile shapes at 1,000,000 characters clean in under 1 s and no padding trick survived; closed.

### 29b/F-122 [P1] closed - The robots path is not percent-decoded, so any rule written with `%XX` fails open

**File:** engine/src/engine/jobs/fetch.py:158, engine/src/engine/jobs/robots.py:92
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** `_match` percent-decodes the rule (`unquote(pattern)`) because it expects an already-decoded path, as the MIT source does (`unquote(parts.path)` and `unquote(parts.query)` in `gate`). `_robots_ok` passes `parts.path` and `parts.query` raw. So `Disallow: /jobs/senior%20engineer` (or `/~user` against `/%7Euser`, or any encoded rule) never matches `/jobs/senior%20engineer` and the page is fetched. Reproduced through `fetch_page` with a mock transport: the page request was made despite the Disallow. This is the exact fail-open the source guards against, and the feature's goal is to read only what robots.txt allows. The unit test passes the decoded path `/foo bar`, so it cannot see this.
**Suggested fix:** Build the path as the source does: `unquote(parts.path) or "/"` plus `"?" + unquote(parts.query)` when a query exists. Add a `fetch_page` test with an encoded request path and encoded rule that expects `robots_disallowed`.
**Resolution:** The path and query are percent-decoded before matching (`unquote`), as in the source tool; `test_percent_encoded_robots_rules_apply_to_the_decoded_path` covers an encoded rule against encoded and decoded requests.

Re-reviewed by the second independent review (7104a33): the repair was exercised with scratch probes and the new tests; the original defect is gone.

### 29b/F-123 [P1] closed - A hostile robots.txt blocks the whole engine for tens of seconds, past the 10 second limit

**File:** engine/src/engine/jobs/robots.py:97, engine/src/engine/jobs/robots.py:117, engine/src/engine/jobs/fetch.py:176
**Found:** 2026-11-10 by /audit independent (scope: current; lens: performance)
**Why it matters:** `permits` runs synchronously on the event loop, once per rule, and each `_match` is O(pattern x path). The robots body may be 524,288 bytes and the path up to 2,000 characters, and the site owner controls the file. Measured: 10,000 lines of `Disallow: /*a*b*c*d*e*f*g*h$` against a 1,900-character path took 16.5 s through `fetch_page` (limit 10 s); a single 100,000-character pattern took 10.6 s; a full 512 KB file of such rules is several times longer. `asyncio.timeout` cannot interrupt synchronous code, so the total limit does not apply, and no other request is served meanwhile. Any signed-in user can submit a link to their own site, 10 per minute, so the engine can be held down continuously. The "no regex backtracking" design removes the exponential case but leaves this quadratic cost unbounded.
**Suggested fix:** Bound the work: cap the number of rules and the pattern length considered (RFC 9309 allows ignoring beyond 500 KiB; for example ignore patterns over 1,000 characters and stop after a few thousand rules, treating an over-limit file as `robots_unreadable`), and/or cap the path length used for matching. Add a timing test with the 512 KB worst case that asserts a bound well under the total limit.
**Resolution:** Matching is bit-parallel (one integer step per path character; 60,000 random pairs agree with the original table walk), and a robots file with more than 500 rules or a rule over 512 characters is `robots_unreadable`; the 600-rule and long-rule files are refused in well under a second and the largest accepted file is fast against a 1,900-character path.

Re-reviewed by the second independent review (7104a33): the repair was exercised with scratch probes and the new tests; the original defect is gone.

### 29b/F-124 [P2] closed - A host that cannot be IDNA-encoded raises an unhandled `UnicodeError` (HTTP 500)

**File:** engine/src/engine/jobs/fetch.py:100
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `system_resolver` catches only `OSError`. `loop.getaddrinfo` raises `UnicodeEncodeError` for a label over 63 characters or an empty label (`http://a..b/`, `http://` + 70 `a` + `.com/`, long non-ASCII names). Reproduced with `fetch_page("http://a..b/x")`. The caller gets `internal_error` 500 instead of the stable 502 `fetch_failed`/422 `validation_failed`, and an unexpected exception reaches the global handler.
**Suggested fix:** Catch `(OSError, UnicodeError)` in `system_resolver` (or validate the host in `parse_url`) and add a test with an empty label and an over-long label.
**Resolution:** `parse_url` IDNA-encodes the host and refuses an empty or over-long label as `validation_failed`; the Host header and TLS name are the ASCII form; connection-level `UnicodeError` and `OSError` map to `fetch_failed`.

Re-reviewed by the second independent review (7104a33): the repair was exercised with scratch probes and the new tests; the original defect is gone.

### 29b/F-125 [P2] closed - Two refusals use a different code from the contract, and a test pins one of them

**File:** engine/src/engine/jobs/fetch.py:82, engine/src/engine/jobs/fetch.py:128, engine/tests/test_fetch.py:285
**Found:** 2026-11-10 by /audit independent (scope: current; lens: tests)
**Why it matters:** The spec says a redirect to a scheme other than http or https is 422 `fetch_blocked`; the code raises `validation_failed` (from `parse_url` on the next hop) and `test_redirects_are_followed_and_every_hop_is_checked` asserts `validation_failed`, so the test encodes the deviation. Likewise a robots.txt over 524,288 bytes raises `too_large` ("That page is too large.") from `_get`, where the contract says an unreadable robots.txt is `robots_unreadable`; no test covers the robots cap. The client would show the wrong guidance.
**Suggested fix:** Map a redirect target that fails `parse_url` to `fetch_blocked` (or check the scheme in the redirect branch), and catch `too_large` inside `_robots_ok` to raise `robots_unreadable`; fix the test and add one for an oversize robots body.
**Resolution:** A redirect hop that is not a readable address is `fetch_blocked` (test updated); a robots.txt over the cap or with a content encoding is `robots_unreadable`.

Re-reviewed by the second independent review (7104a33): the repair was exercised with scratch probes and the new tests; the original defect is gone.

### 29b/F-126 [P3] closed - `is_public` accepts site-local `fec0::/10` and IPv4-compatible `::/96` addresses

**File:** engine/src/engine/jobs/fetch.py:55
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** `ipaddress` (Python 3.13.18) reports `fec0::1`, `::7f00:1` and `::a00:1` as global. Site-local is deprecated but still used on some private networks, and `::a.b.c.d` embeds an IPv4 address. Modern Linux does not normally route either to a private IPv4 host, so this is defence in depth, not a demonstrated bypass. The tested list omits both forms (`5f00::/16` is also accepted).
**Suggested fix:** Also refuse `fec0::/10` and `::/96` (and, optionally, require the address to fall inside `2000::/3` for IPv6, which excludes all of these at once); add them to the parametrized test.
**Resolution:** `fec0::/10` and `::/96` are refused with the other non-public IPv6 forms; both are in the address tests.

Re-reviewed by the second independent review (7104a33): the repair was exercised with scratch probes and the new tests; the original defect is gone.

### 29b/F-127 [P3] closed - A small gzip body decodes to tens of megabytes in memory before the size cap fires

**File:** engine/src/engine/jobs/fetch.py:127
**Found:** 2026-11-10 by /audit independent (scope: current; lens: performance)
**Why it matters:** `aiter_bytes()` yields decoded bytes and the cap is checked per decoded chunk, but httpx's gzip decoder expands one network chunk (up to 64 KB, about 67 MB at zlib's best ratio) in one step. Measured: a 58 KB gzip body peaked at 60 MB inside `fetch_page` before `too_large`. Bounded and transient (10 requests a minute per user), so P3.
**Suggested fix:** Send `Accept-Encoding: identity` so the body is not compressed, or read with `aiter_raw` and decode with a size-limited decompressor.
**Resolution:** Requests send `Accept-Encoding: identity` and any response with a content encoding is refused, so nothing is inflated past the size cap.

Re-reviewed by the second independent review (7104a33): the repair was exercised with scratch probes and the new tests; the original defect is gone.

### 29b/F-128 [P3] closed - The rate-limit table keeps one entry per user forever

**File:** engine/src/engine/jobs/service.py:172
**Found:** 2026-11-10 by /audit independent (scope: current; lens: performance)
**Why it matters:** `_recent` is a `defaultdict` of deques; old timestamps are removed but an emptied deque and its key are never deleted, so the dict grows with every distinct user who ever fetched. The growth is small and bounded by the user count, so this is low impact.
**Suggested fix:** Delete the key when its window empties (or prune idle keys when the dict passes a size).
**Resolution:** The per-user rate-limit table is swept of idle users once it holds more than 1,000; test added.

Re-reviewed by the second independent review (7104a33): the repair was exercised with scratch probes and the new tests; the original defect is gone.

### 29b/F-129 [P3] closed - The `Host` header for an IPv6 literal URL has no brackets, and a dangling quote in a tag hides the rest of the page

**File:** engine/src/engine/jobs/fetch.py:132, engine/src/engine/jobs/posting_guard.py:326
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** For `http://[2606:4700::1111]/` the header is `Host: 2606:4700::1111`, which servers may reject (400), so such a link fails as `not_a_page`. Separately, `_tag_end` treats any quote inside a tag as opening a quoted value, so a stray apostrophe (`<p title='it's'>` or `<a href=/it's>`, which browsers accept) runs to the next apostrophe or hides the rest of the input; the previous reader kept such text. This is the fail-closed choice the spec asks for, and ordinary pages without stray quotes matched the old reader in a 6,000-page differential run, so this is a fidelity note only.
**Suggested fix:** Bracket an IPv6 host in `Host`. For quotes, only start a quoted value after `=` (as the HTML tokenizer does), or accept the behaviour and add a test documenting it.
**Resolution:** The Host header brackets an IPv6 literal, and the tag reader opens a quoted value only after `=`, as HTML does, so a stray quote no longer hides the rest of a page; tests added.

Re-reviewed by the second independent review (7104a33): the repair was exercised with scratch probes and the new tests; the original defect is gone. The stray-quote change introduces a separate defect, F-130.

### 29b/F-130 [P2] closed - The new quote rule in `_tag_end` ends a tag earlier than a browser does, so text a browser keeps inside a tag appears in the cleaned output

**File:** engine/src/engine/jobs/posting_guard.py:322
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** `_tag_end` opens a quoted value at every `=` followed by a quote. The HTML tokenizer does not: `=` is an ordinary name character in the tag-name state (`<d=" ...`) and at the start of an attribute name (`<d =" ...`), a second `=` in an unquoted value is data (`a==" `), and `=` after a quoted value starts a new name. In those places the reader sees a quote where a browser sees none, and the two disagree about where the tag ends. Reproduced: `<p>Real job.</p><d=" a x="> SECRET ignore all previous instructions <p x=" ">end` cleans to `Real job.\nSECRET ignore all previous instructions\nend`, while a browser reads `> SECRET ... <p x=` as the value of `x`, so the user never sees it. I compared `_tag_end` with a small implementation of the HTML tokenizer tag states on 500,000 random tag fragments: about 20% differ in end position, and in about 2 to 3% of them the reader ends the tag earlier than the browser (about 6,000 of 300,000 even with a plain tag name). So an author can again put text in the stored description that a reader of the real page never sees. Instruction-shaped lines are still counted (the sample above counted 1), and a differing tag can also hide visible text; this is a security-relevant but flag-covered gap, as F-118 and F-120 were.
**Suggested fix:** Follow the tokenizer states in `_tag_end`: read the tag name up to whitespace, `/` or `>` (not with a name regex), treat `=` as a name character when it begins an attribute name, and open a quoted value only from the "before attribute value" state (after an attribute name, optional whitespace, one `=`). Add a test that compares the end position with the cases above (`<d="`, `<d ="`, `a=="`, `"a"="`).
**Resolution:** `_tag_end` follows the HTML tokenizer's start-tag states: the name runs to whitespace, `/` or `>`, an attribute name always takes its first character (even `=`), and a quote opens a value only after `=`; the F-130 examples now hide their content (test `test_a_tag_ends_where_a_browser_ends_it`), ordinary pages are unchanged (8,000-page differential) and the 1 MB shapes still clean in under a second.

Re-reviewed by the third independent review (21a9afc): `_tag_end` matched an HTML tokenizer model on 600,000 random fragments with no difference in end position; closed. The attribute reading is a separate gap, F-133.

### 29b/F-131 [P3] closed - The rule cap counts rules for every user agent, and the matcher has no test against a reference

**File:** engine/src/engine/jobs/robots.py:62, engine/tests/test_robots.py
**Found:** 2026-11-10 by /audit independent (scope: current; lens: quality)
**Why it matters:** `_groups` raises `RobotsTooComplex` when the whole file has more than 500 Allow/Disallow lines, including groups for agents we never match; 600 one-line groups for other bots made `permits` raise. Large ordinary sites will read as `robots_unreadable` (fail closed, so safe, but it blocks pages that allow us). The bit-parallel `_match` replaced the table walk without a test that compares them: it agreed with the old table walk on 150,000 random pairs in my probe, but the repository has only the earlier handful of examples, so a later edit could break it unnoticed. Worst case now measured at 0.23 s (500 rules of 512 characters, 2,000-character path), within bounds.
**Suggested fix:** Apply the cap to the rules in the `jobmigobot` and `*` groups only (evaluate the others lazily), and add a seeded random comparison against a small reference table-walk in `test_robots.py`.
**Resolution:** The rule cap counts only the groups that apply to us (our agent token and `*`), so a large file for other agents is readable; a seeded test now compares the bit-parallel matcher with the original table walk.

Re-reviewed by the third independent review (21a9afc): the cap now applies to our groups and a seeded comparison test exists; closed. Moving the cap out of `_groups` opened a new resource defect, F-132.

### 29b/F-132 [P1] closed - Many `User-agent` lines followed by many rules make `_groups` build billions of entries (seconds of CPU, gigabytes of memory)

**File:** engine/src/engine/jobs/robots.py:62
**Found:** 2026-11-10 by /audit independent (scope: current; lens: performance)
**Why it matters:** Repairing F-131 moved the rule cap out of `_groups`, which previously stopped after 500 rules. `_groups` now appends every Allow/Disallow value once per agent of the current record (`for agent in agents: out[agent].append(...)`), and a record can name any number of agents (`User-agent` lines with no rule between them). The site owner controls the file, up to 524,288 bytes. Measured on `permits` with N distinct `User-agent: aN` lines followed by N `Disallow: /x` lines: N=2,000 (61 KB) 0.4 s and 0.5 GB; N=4,000 (123 KB) 1.7 s and 1.8 GB; N=8,000 (247 KB) 9 s and 4.3 GB peak RSS. Growth is quadratic, so the full 512 KB file needs tens of seconds and well over 10 GB, which the 10 s total limit cannot interrupt (synchronous code) and which can get the engine process killed. Any signed-in user can point a link at their own site, 10 per minute.
**Suggested fix:** Do not copy rules per agent: record each rule once per record and look groups up by agent (for example store the record's rule list and map each agent name to that shared list), or only keep agents equal to `jobmigobot` or `*`; also stop parsing when the number of lines that apply to those two agents exceeds `MAX_RULES`. Add a test with thousands of `User-agent` lines and thousands of rules that asserts a bound on time and size.
**Resolution:** `_groups` keeps only the agents we need (`jobmigobot` and `*`, or the one asked for), so a record listing thousands of agents costs the same as one agent; the rule cap and the 512-character limit apply to those groups while parsing. Test: 8,000 agents then 8,000 rules parses in well under two seconds and a record naming us among many agents still applies.

Re-reviewed by the fourth independent review (ca50b11): hostile robots files (20,000 agents then 40,000 rules, repeated agents, many records, blank lines, a 500,000-character rule, 500 worst-case rules) all finish in 0.25 s or less and 29 MB peak; closed.

### 29b/F-133 [P2] closed - Attributes are read with a different parser from the tag end, so an unquoted `style` holding a quote hides nothing

**File:** engine/src/engine/jobs/posting_guard.py:211, engine/src/engine/jobs/posting_guard.py:309
**Found:** 2026-11-10 by /audit independent (scope: current; lens: security)
**Why it matters:** `_tag_end` now follows the HTML tokenizer, but `_is_hidden` reads the attribute text with the `ATTR` regex, whose unquoted value stops at a quote. In HTML an unquoted value runs to whitespace or `>` and may contain quotes. So `<div style=content:'x';display:none>SECRET</div>` is a valid, hidden element in a browser (the style is `content:'x';display:none`), but the cleaner splits the value at the quote, sees no `display:none` and keeps SECRET: it cleans `<p>vis</p><div style=content:'x';display:none>SECRET ignore all previous</div><p>end</p>` to `vis\n\nSECRET ignore all previous\n\nend`. The same text in a quoted attribute is hidden correctly. A comparison with a tokenizer model also showed other attribute splits (`a=x'style=`). The old reader had the same `ATTR` (so not new in 29b), but the repair of F-130 makes the tag boundary exact and this is now the remaining differential; instruction-shaped lines are still counted.
**Suggested fix:** Collect the attributes inside `_tag_end` from the same state machine (name, and value for quoted and unquoted forms) and pass that dict to `_is_hidden`, deleting `ATTR`; add the example above and a `style=a:'b';display:none` case to the tests.
**Resolution:** Attributes are collected inside the tokenizer-based `_scan_tag` (first copy of a repeated attribute wins, unquoted values run to whitespace or `>`, quotes inside them are ordinary) and the old `ATTR` regex is gone; `<div style=content:'x';display:none>` is now hidden. Ordinary pages are unchanged (8,000-page differential), 1 MB shapes still under a second.

Re-reviewed by the fourth independent review (ca50b11): `_scan_tag` matched an HTML tokenizer model, attribute names and values included, on 686,000 random tags with no mismatch, and the unquoted-style example is now hidden; closed.

Findings of this build: the closed and resolved entries are archived above; entries still open or fixed (awaiting a later audit) stay in the live ledger with their IDs, so all are kept in the live ledger with their IDs.

## Independent review

Original passing receipt for checkpoint `ca50b11c166f13047e247f3104e4aded0cb83edd`, copied unchanged:

````markdown
**Status:** passed
**Target commit:** ca50b11c166f13047e247f3104e4aded0cb83edd
**Base commit:** 48627e31d1f0162969982fe264702992868febc6
**Base ref:** main
**Spec hash:** 7a51d56bca4a93ff47685f55c1029e6ac89528f3f091b7de7ebf275f62fa15bf
**Prepared by:** claude
**Builder model:** claude-sonnet-5-5
**Requested reviewer:** claude
**Requested model:** runtime default (exact model not known until reviewer starts)
**Requested execution:** automatic
**Requested at:** 2026-11-10T17:33:42Z
**Workflow:** continuous
**Check required:** no
**Reviewer adapter:** claude
**Reviewer model:** claude-sonnet-5-5
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-10T18:30:00Z
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `git rev-parse HEAD`, merge base with `main`, `sha256sum blueprint/context/current-feature.md`: pass (match the request; only review.md differed)
- `npm run lint`, `npm run typecheck`, `npm test` (179 passed, 1 skipped), `npm run build` (web): pass
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run --env-file ../.env pytest -q` (462 passed, 9 skipped) (engine): pass
- Scratch probes, no network: 14 hostile robots shapes at 512 KB (time and peak memory); 1,000,000-character timing of about 90 hostile HTML shapes including attribute-heavy and style-heavy tags; `_scan_tag` against an HTML tokenizer model on 600,000 fragments (tag end) and 686,000 fragments (tag end plus `hidden`, `aria-hidden` and `style` values): pass

## Evidence

- F-132 and F-133 re-examined and closed; no mismatch with the tokenizer model, and the `style=content:'x';display:none` example is hidden.
- Robots: every hostile shape finished in 0.25 s or less at 29 MB peak; the worst legitimate case (500 rules of 512 characters, 2,000-character path) is 0.22 s; `_groups` changes keep the record semantics (rules before any agent ignored, blank lines tolerated, percent-decoded path).
- HTML reader: all shapes under 1 s at 1,000,000 characters (slowest 0.9 s, 52,000 hidden elements); peak memory 71 MB.
- SSRF address forms, pinning (httpcore `sni_hostname` for SNI and certificate), redirects, identity encoding, size and time limits, error codes and rate table unchanged from the second review and rechecked; no fetched text or URL is echoed or logged.
- Tests: refusal tests assert status and code and that no page request was made; matcher has a seeded reference comparison; new timing tests assert bounds.

## Findings

- None new. Closed this pass: F-132, F-133.

## Remaining risk

- Real DNS and TLS were not exercised (no network by instruction).
- Hidden-content detection is heuristic by design: hiding through a `<style>` block or class, CSS escapes (`display:\6eone`) or other properties is not recognised; instruction-shaped lines are still counted.
- A server that ignores `Accept-Encoding: identity` and compresses is refused, so the user is asked to paste.
- A robots.txt with more than 500 rules in the groups that apply to us reads as unreadable (fail closed).
````

## Try guide

Skipped: `/check guide` is user-run and was not available to the completing session (the same decision the user made for 3a). Run `/check guide latest` for a walkthrough. The live DeepSeek parse was not run because `.env` had no AI model or key.
