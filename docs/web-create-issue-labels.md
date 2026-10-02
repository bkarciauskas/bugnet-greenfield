# Proposed labels for web create-issue

Every label in this file is a proposal. Ben approves labels. This file does not record an approval.

The slice is web issue creation on `Issues/CreateIssue.aspx`, plus the new-issue notification email. SOAP is out of scope. The code map for that boundary is [docs/soap-create-issue.md](soap-create-issue.md).

## Label words

- `preserve`. The greenfield slice copies this behaviour.
- `change`. The greenfield slice does this differently on purpose.
- `remove`. The greenfield slice drops this behaviour.
- `defect`. Legacy does this, and the slice must not copy it.
- `unknown`. The recordings do not show this, so it is not a parity target yet.

An unknown on the critical path blocks the slice. A behaviour is on the critical path when the recorded create, or the recorded notification, cannot be recognised without it.

Every critical-path behaviour has a proposed label other than `unknown`. No observed behaviour is proposed as `change` or `remove`.

## Evidence

Two creates on `http://15.135.1.105/`, recorded in [docs/web-create-issue-recording.md](https://github.com/bkarciauskas/bugnet-greenfield/blob/cursor/web-create-issue-recording-5ec0/docs/web-create-issue-recording.md) on pull request 6. The branch that holds the recording is `cursor/web-create-issue-recording-5ec0`.

The message copies are [create-issue-1.eml](https://github.com/bkarciauskas/bugnet-greenfield/blob/cursor/web-create-issue-recording-5ec0/docs/recordings/create-issue-1.eml) and [create-issue-2.eml](https://github.com/bkarciauskas/bugnet-greenfield/blob/cursor/web-create-issue-recording-5ec0/docs/recordings/create-issue-2.eml). Their sha256 values match the recording note. Create 1 is `ed067feb4a929ca6d6ab357468078a594f0e48611cf9c53f0f2c75ff0f83cbe5`. Create 2 is `89b4019d5c479423fd3f2618aac33673a32f58902819548a95b62557b7bd5444`.

Mail on this host is pickup to `C:\Email`. SMTP stays off. The live `Web.config` mail section is quoted in [docs/aws-legacy-host-notes.md](https://github.com/bkarciauskas/bugnet-greenfield/blob/cursor/aws-legacy-host-notes-8834/docs/aws-legacy-host-notes.md) on pull request 4. The recording left that setting unchanged.

The host setup before the creates is not a labelled behaviour. The recording added project `Slice recording` with code `BN`, added status `Open`, priority `Normal`, issue type `Bug`, and resolution `Not set`, and subscribed `Admin` to that project. The owner and assignee dropdowns had no user to select.

## Recorded critical path

### B1. A successful save redirects to the new issue

Proposed label `preserve`. On the critical path.

Both saves posted `lnkSave` to `/Issues/CreateIssue/1`. Create 1 returned 302 to `/Issues/IssueDetail.aspx?id=1`. Create 2 returned 302 to `/Issues/IssueDetail.aspx?id=2`.

### B2. The detail page shows the new issue key, title, creator, and local time

Proposed label `preserve`. On the critical path.

A later GET of each detail page returned 200. The page showed `BN-1: Recording one: web create`, created by Administrator on 10/2/2026 4:05 PM. The second page showed `BN-2: Recording two: web create`, created by Administrator on 10/2/2026 4:06 PM.

### B3. The issue key is the project code, a hyphen, and the issue id

Proposed label `preserve`. On the critical path.

The project code is `BN`. The page text and both subjects use `BN-1` and `BN-2`.

### B4. An empty owner and an empty assignee still save

Proposed label `preserve`. On the critical path.

Both posts sent an empty owner, an empty assignee, notify owner checked, and notify assignee checked. Both posts returned the 302 in B1.

### B5. Each successful create produces one notification, and only for that issue

Proposed label `preserve`. On the critical path.

Create 1 was followed by `mail/slot-0002.eml`. Create 2 ran after that message had been read, and was followed by `mail/slot-0003.eml`. The subjects name `BN-1` and `BN-2` respectively.

### B6. From is the application title and the host email address

Proposed label `preserve`. On the critical path.

Both messages have `From: "BugNET Issue Tracker" <noreply@mysmtpserver.com>`. On this host that address is the stock host email address. The pickup setting was not changed.

### B7. The notification is a pickup file in `C:\Email`

Proposed label `preserve`. On the critical path.

The host mail section uses `deliveryMethod="SpecifiedPickupDirectory"` and `pickupDirectoryLocation="C:\Email"`. Both recorded objects are `.eml` files with `X-Sender` and `X-Receiver`, stored as `mail/slot-0002.eml` and `mail/slot-0003.eml`. Pickup to `C:\Email` is the send. SMTP is off.

### B8. The only recipient is the project subscriber who created the issue

Proposed label `preserve`. On the critical path.

Both messages have `To: admin@yourdomain.com`. The recording subscribed `Admin` to project 1, and email notifications were already checked for that user. Owner and assignee were empty. Each message has one recipient, and that recipient is the creator.

### B9. The subject names the issue key

Proposed label `preserve`. On the critical path.

Create 1 subject is `Issue BN-1 has been added to a project you are monitoring.` Create 2 subject is `Issue BN-2 has been added to a project you are monitoring.`

### B10. The body is one HTML part from the add-issue template

Proposed label `preserve`. On the critical path.

Both messages use `Content-Type: text/html; charset=us-ascii` and `Content-Transfer-Encoding: quoted-printable`. The decoded body contains the fixed sentences from `src/BugNET_WAP/Templates/Html/IssueAdded.xslt`. Those sentences are both reply markers, `The following issue has been added to a project that you are monitoring.`, and the profile opt-out sentence.

### B11. The body carries the issue fields the template prints

Proposed label `preserve`. On the critical path.

Both bodies include title, project, created by, milestone, category, priority, type, and description. Create 1 uses title `Recording one: web create`, project `Slice recording`, creator `Administrator`, milestone `Unassigned`, category `Unassigned`, priority `Normal`, type `Bug`, and description `First web create-issue recording.` Create 2 uses title `Recording two: web create` and description `Second web create-issue recording.` The other fields match create 1.

### B12. Unset milestone and category render as Unassigned, and the posted lookups render by name

Proposed label `preserve`. On the critical path.

Both posts sent milestone 0, category 0, priority 1, and type 1. Both bodies show `Unassigned`, `Unassigned`, `Normal`, and `Bug`.

### B13. The add-issue body omits status and resolution

Proposed label `preserve`. On the critical path.

Both posts sent status 1 and resolution 1. Neither body contains those fields. The HTML template has no status row and no resolution row.

### B14. The detail and profile paths are the legacy page paths

Proposed label `preserve`. On the critical path.

Create 1 links to `Issues/IssueDetail.aspx?id=1` and `Account/UserProfile.aspx`. Create 2 links to `Issues/IssueDetail.aspx?id=2` and the same profile path.

### B15. The link base is `http://localhost/BugNet/`

Proposed label `defect`. On the critical path.

Both bodies prefix those paths with `http://localhost/BugNet/`. The creates were sent to `http://15.135.1.105/`. A reader of the message cannot open the new issue on the host that created it. The HTML template builds both links from host setting `DefaultUrl`. The slice must not copy this base URL. B14 still stands. The path stays. The base has to be the site that created the issue.

## Recorded, and not on the critical path

These rows are `unknown`. They do not block the slice. If Ben marks one of them critical, that row blocks the slice until a recording covers it.

### U1. Status and resolution are stored on the issue

Proposed label `unknown`. Not on the critical path.

The form posted status 1 and resolution 1, and the save succeeded. The detail-page quote in the recording does not mention status or resolution. The email omits them, which B13 already labels. Nothing in the recording reads the stored status or resolution back.

### U2. The redirect waits for the pickup write

Proposed label `unknown`. Not on the critical path.

Each save returned 302, and each save had one `.eml` object afterwards. The recording does not time the file against the response.

### U3. Who receives mail when an owner or an assignee is selected

Proposed label `unknown`. Not on the critical path.

Both posts left owner and assignee empty. B8 covers only that path.

### U4. Who receives mail when the creator does not monitor the project

Proposed label `unknown`. Not on the critical path.

The only recipient is the creator, and that user was subscribed to the project. The recording does not separate those two facts.

### U5. Empty title, attachments, custom fields, non-ASCII text, and a text-format body

Proposed label `unknown`. Not on the critical path.

Neither create exercised those inputs. Both bodies are ASCII HTML.
