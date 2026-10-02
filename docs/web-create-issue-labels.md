# Proposed labels for web create-issue

Ben accepted every objection in the review on pull request 8. The rows below use those relabels. The review is [docs/web-create-issue-labels-review.md](https://github.com/bkarciauskas/bugnet-greenfield/blob/cursor/web-create-issue-labels-review-bf14/docs/web-create-issue-labels-review.md). The same text is on [the pull request 7 comment](https://github.com/bkarciauskas/bugnet-greenfield/pull/7#issuecomment-5946832561).

The slice is web issue creation on `Issues/CreateIssue.aspx`, plus the new-issue notification email. SOAP is out of scope. The code map for that boundary is [docs/soap-create-issue.md](soap-create-issue.md).

## Label words

- `preserve`. The greenfield slice copies this behaviour.
- `change`. The greenfield slice does this differently on purpose.
- `remove`. The greenfield slice drops this behaviour.
- `defect`. Legacy does this, and the slice must not copy it.
- `unknown`. The recordings do not show this, so it is not a parity target yet.

An unknown on the critical path blocks the slice. A behaviour is on the critical path when the recorded create, or the recorded notification, cannot be recognised without it.

No row is `change`, `remove`, or `defect`. No `unknown` sits on the critical path.

## Evidence

Two creates on `http://15.135.1.105/`, recorded in [docs/web-create-issue-recording.md](https://github.com/bkarciauskas/bugnet-greenfield/blob/cursor/web-create-issue-recording-5ec0/docs/web-create-issue-recording.md) on pull request 6. The branch that holds the recording is `cursor/web-create-issue-recording-5ec0`.

The message copies are [create-issue-1.eml](https://github.com/bkarciauskas/bugnet-greenfield/blob/cursor/web-create-issue-recording-5ec0/docs/recordings/create-issue-1.eml) and [create-issue-2.eml](https://github.com/bkarciauskas/bugnet-greenfield/blob/cursor/web-create-issue-recording-5ec0/docs/recordings/create-issue-2.eml). Their sha256 values match the recording note. Create 1 is `ed067feb4a929ca6d6ab357468078a594f0e48611cf9c53f0f2c75ff0f83cbe5`. Create 2 is `89b4019d5c479423fd3f2618aac33673a32f58902819548a95b62557b7bd5444`.

## Unlabeled host and fixture data

These values appeared in the recording. They are not behaviour labels. A later host can change them and the preserved rules still hold.

- `noreply@mysmtpserver.com` and `BugNET Issue Tracker`.
- `C:\Email`, and collector keys `mail/slot-0002.eml` and `mail/slot-0003.eml`.
- `admin@yourdomain.com`.
- `Administrator`.
- The en-US date and clock on the detail page, including `10/2/2026 4:05 PM` and `10/2/2026 4:06 PM`.
- `charset=us-ascii` and `quoted-printable`.
- `Normal`, `Bug`, and `Slice recording`.
- The posted title and description sentences.
- The English subject wording.
- The link base `http://localhost/BugNet/`.

The host setup before the creates is also unlabeled. The recording added project `Slice recording` with code `BN`, added status `Open`, priority `Normal`, issue type `Bug`, and resolution `Not set`, and subscribed `Admin` to that project. The owner and assignee dropdowns had no user to select.

## Recorded critical path

### B1. A successful save redirects to the new issue

Proposed label `preserve`. On the critical path.

Both saves posted `lnkSave` to `/Issues/CreateIssue/1`. Create 1 returned 302 to `/Issues/IssueDetail.aspx?id=1`. Create 2 returned 302 to `/Issues/IssueDetail.aspx?id=2`.

### B2. The detail page shows the issue key, title, creator, and created-on time

Proposed label `preserve`. On the critical path.

The page shows `Issue.FullId`, the title, `CreatorDisplayName`, and `DateCreated` formatted with the current culture's general short pattern. `Administrator` and the clock values in the recording are unlabeled.

### B3. The issue key is the project code, a hyphen, and the issue id

Proposed label `preserve`. On the critical path.

`FullId` is that shape. The recording's project code `BN`, and the keys `BN-1` and `BN-2`, are the fixture.

### B4. A blank owner and a blank assignee are accepted

Proposed label `preserve`. On the critical path.

A blank owner and a blank assignee are accepted. A checked notify box adds no recipient when the username is empty. Empty owner is not the usual submit. The default owner selection, when the signed-in user is in the project member list, is unrecorded.

### B5. A successful create starts one add-notification for that issue

Proposed label `preserve`. On the critical path.

A successful create starts one add-notification whose subject names that issue. This row does not preserve "the file exists when the 302 returns."

### B6. From is the host title and the host email address

Proposed label `preserve`. On the critical path.

The display name is `ApplicationTitle`. The address is `HostEmailAddress`. The address gains `+iid-{id}` before `@` only when reply-to is on. The recorded header has no plus-tag. That header's strings are unlabeled host data.

### B7. Delivery method

No behaviour label. Host configuration.

Pickup directory, SMTP, and collector object names are this host's mail setup. They are not create-issue behaviour. Message content stays with B5, B9, and B10.

### B8. Subscribers receive the add-notification, and the creator is not removed

Proposed label `preserve`. On the critical path.

One add-notification goes to each approved project subscriber or issue subscriber who has email notifications on. The creator is not removed. `admin@yourdomain.com`, a recipient count of one, and "the recipient is the creator" are unlabeled. U4 remains the case where the creator does not monitor the project.

### B9. The subject uses the add-notification pattern for the recipient culture

Proposed label `preserve`. On the critical path.

The subject is the `IssueAddedSubject` pattern for the recipient culture. The issue key is `{0}`. The project name is omitted. The English sentence in this recording is the default locale.

### B10. The body is the add-issue template for the selected format

Proposed label `preserve`. On the critical path.

The decoded body is the add-issue template text for the selected mail format. Charset and transfer encoding are unlabeled. HTML in this recording is the seed format setting.

### B11. The body carries the template field set

Proposed label `preserve`. On the critical path.

The fields are title, project, created by, milestone, category, priority, type, and description. The recorded names and sentences are unlabeled. Description escaping is not part of this row. The recording's descriptions are plain sentences, so the recording does not show whether markup is escaped.

### B12. A missing milestone or category join renders as Unassigned, and lookups render by name

Proposed label `preserve`. On the critical path.

A milestone or category id that does not join renders as the view's English `Unassigned`. Priority and type render as the joined row name. `Normal` and `Bug` are unlabeled fixture names.

### B13. The add-issue body omits status and resolution

Proposed label `preserve`. On the critical path.

Both posts sent a status id and a resolution id. Neither body contains those fields. The HTML template has no status row and no resolution row. Storage of those ids is U1.

### B14. The detail and profile paths are the legacy page paths

Proposed label `preserve`. On the critical path.

The detail path is `Issues/IssueDetail.aspx?id={id}`. The profile path is `Account/UserProfile.aspx`.

### B15. Both links are DefaultUrl plus the B14 paths

Proposed label `preserve`. On the critical path.

Both links are host setting `DefaultUrl` plus the B14 paths. The recorded base `http://localhost/BugNet/` is unlabeled install data.

### B16. A successful create stores one vote by the creator

Proposed label `preserve`. On the critical path.

A successful create stores one vote by the creator before the notification and the redirect. The on-page vote label text is unlabeled.

### U1. Posted status and resolution ids are stored and selected

Proposed label `preserve`. On the critical path.

The posted status id and the posted resolution id are stored and selected on the detail page. Display names stay unlabeled.

## Off the critical path

### U2. The redirect does not wait for the send

Proposed label `preserve`. Not on the critical path.

The redirect does not wait for the send to finish. Recognising the message body does not depend on this row.

### U3. Who receives mail when an owner or an assignee is selected

Proposed label `unknown`. Not on the critical path.

Both posts left owner and assignee empty. B4 covers a checked notify box with an empty username. This row is the case where a username is selected.

### U4. Who receives mail when the creator does not monitor the project

Proposed label `unknown`. Not on the critical path.

The recording's subscriber is also the creator. B8 does not separate those facts. This row stays the bucket for a creator who does not monitor the project.

### U5. Empty title, attachments, custom fields, non-ASCII text, and a text-format body

Proposed label `unknown`. Not on the critical path.

Neither create exercised those inputs. The HTML body in the recording is the seed format setting, which B10 already treats as unlabeled.
