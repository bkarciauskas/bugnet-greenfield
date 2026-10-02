# Objections to the web create-issue labels

Objections only. The proposals are in `docs/web-create-issue-labels.md` on pull request 7. The evidence used here is the pull request 6 recording, `docs/recordings/create-issue-1.eml`, `docs/recordings/create-issue-2.eml`, and the legacy BugNET source. The sha256 values in the proposal match those two files (`ed067feb4a929ca6d6ab357468078a594f0e48611cf9c53f0f2c75ff0f83cbe5`, `89b4019d5c479423fd3f2618aac33673a32f58902819548a95b62557b7bd5444`).

A characterisation test written from a host setting fails when the setting changes and the behaviour is still right. That is the failure mode behind the high objections.

## B6. From address. Severity: high

`From: "BugNET Issue Tracker" <noreply@mysmtpserver.com>` is the install seed, read back through host settings. `Data.HostSettings.sql` inserts `ApplicationTitle` = `BugNET Issue Tracker` and `HostEmailAddress` = `noreply@mysmtpserver.com`. `SmtpMailDeliveryService.Send` copies those two settings into `MailMessage.From`. When `Pop3AllowReplyToEmail` is true it also inserts `+iid-{issueId}` before the `@`. That setting is seeded `False`, which is why these two messages have no plus-tag.

The recording shows the header. It does not show that anyone left the host settings at the seed. The proposal says the address "is the stock host email address" and then marks the whole header `preserve`.

A test that asserts `noreply@mysmtpserver.com`, the display name `BugNET Issue Tracker`, or the absence of `+iid-` fails on a host where those three settings were edited. The send path is still the same.

Suggested relabel: drop `preserve` for the literal header. The behaviour is: the display name is `ApplicationTitle` and the address is `HostEmailAddress`, plus `+iid-{id}` only when reply-to is on. The recorded strings are unlabeled host data.

## B7. Pickup directory. Severity: high

Pickup to `C:\Email` is `system.net/mailSettings` in the legacy `Web.config` (`deliveryMethod="SpecifiedPickupDirectory"`, `pickupDirectoryLocation="C:\Email"`). `Web.Release.config` removes that `mailSettings` element. `SmtpMailDeliveryService` sets SMTP host and port from host settings and then calls `SmtpClient.SendAsync`. The directory is the process config, not the create-issue behaviour.

The recording says the pickup setting was left unchanged and that the objects were read from S3 (`mail/slot-0002.eml`, `mail/slot-0003.eml`). It does not list `C:\Email`, and those slot names are collector keys. .NET pickup files are not named `slot-000N.eml`. `X-Sender` and `X-Receiver` show that some pickup write produced the bytes. They do not name the directory. "SMTP is off" is this host's config.

A test that the notification is a file in `C:\Email`, or that it is named `slot-0002.eml`, fails on a release host that delivers over SMTP, and on any collector that uses different object keys.

Suggested relabel: drop `preserve`. Delivery method is host configuration. Message content stays with B5, B9, and B10.

## B8. Recipient. Severity: high

`admin@yourdomain.com` is the mailbox the installer creates for `Admin` (`Install.aspx.cs`, `Membership.CreateUser`). The recording subscribed that one user to project 1, and the profile default `ReceiveEmailNotifications` is `true` in `Web.config`.

`SendIssueAddNotifications` mails every approved user returned by `BugNet_IssueNotification_GetIssueNotificationsByIssueId` who still has email notifications on. That procedure unions issue subscribers and project subscribers. The "skip the person who added it" check is commented out on the add path, so a subscribed creator is included. Empty owner and assignee add no issue-subscriber rows (`CreateIssue.SaveIssue` checks the username first).

This recording has one project subscriber, and that person is the creator. U4 already says those two facts are not separated. B8 then marks "the only recipient is the project subscriber who created the issue" as `preserve`.

A test that `To` is `admin@yourdomain.com`, that there is exactly one recipient, or that the recipient is the creator, fails when a second subscriber exists, when the creator is not subscribed, or when Admin's email is not the seed. The subscriber rule can still be right.

Suggested relabel: `preserve` only "one add-notification per approved project or issue subscriber who has email notifications on, and the creator is not removed." Leave `admin@yourdomain.com`, the count of one, and "the recipient is the creator" unlabeled. U4 remains the bucket for a creator who does not monitor the project.

## B15. Link base. Severity: high

`http://localhost/BugNet/` is the `DefaultUrl` seed in `Data.HostSettings.sql`. The HTML template concatenates `HostSetting_DefaultUrl` with the paths in B14. `HostSettingManager.DefaultUrl` returns that setting and appends a slash when the stored value has none. The host settings screen exists to change it. The same class of unset seed is the From address in B6.

The recording shows the href. It does not show anyone opening it, so "a reader of the message cannot open the new issue" is not an observed failure. Marking the seed `defect` on the critical path tells the slice to stop copying a setting the code is already honoring.

A characterisation test of this `defect` label either asserts the legacy body contains `http://localhost/BugNet/` (locking the seed) or asserts the public origin `http://15.135.1.105/` (failing against this recording, and against any legacy host whose `DefaultUrl` was set).

Suggested relabel: drop `defect`. The behaviour is "both links are `DefaultUrl` plus the B14 paths." The recorded base is unlabeled install data. Using the public origin would be a `change`, and this recording does not show that change.

## U1. Status and resolution. Severity: high

`BugNet_Issue_CreateNewIssue` writes `@IssueStatusId` and `@IssueResolutionId` on every insert. Both recorded posts sent `1` and `1`. `IssueDetail.BindValues` selects `DropStatus` and `DropResolution` from those ids. The detail page the recording fetched always binds them. The quote in the recording omits them, and the add-issue template omits them (B13). B13 does not cover storage.

Leaving storage `unknown` and off the critical path means a slice can drop status and resolution and still match every `preserve` row and the written quote. The save that produced the 302 wrote both columns.

The names `Open` and `Not set` were created in the host setup and were not read back. A test of those words is unsupported.

Suggested relabel: `preserve`, on the critical path: the posted status id and resolution id are stored and selected on the detail page. Keep the display names unlabeled until a recording quotes them.

## B5 and U2. The 302 and the pickup file. Severity: high

B5 says each successful create produces one notification, and the evidence is a `.eml` observed afterwards. U2 says whether the redirect waits is `unknown` because the recording does not time the file against the response.

The code answers U2. `IssueNotificationManager.SendIssueAddNotifications` calls `SmtpMailDeliveryService.Send` and does not await the returned task. `Send` starts `SmtpClient.SendAsync` inside `Task.Run` and returns when that call has been queued. `CreateIssue.LnkSaveClick` then `Response.Redirect`s. A send exception is logged and does not fail the save.

A characterisation test of B5 that treats the 302 as proof the `.eml` already exists fails when the async send has not finished. That failure is timing, not a wrong notification. A test that requires the file to exist before the response copies a race the recording never measured.

Suggested relabel: B5 stays `preserve` for "a successful create starts one add-notification whose subject names that issue." It does not preserve "the file exists when the 302 is returned." U2 is not `unknown`. Relabel U2 to `preserve`: the redirect does not wait for the send to finish. That fact is off the critical path of recognising the message body.

## B2. Detail-page text. Severity: medium

The behaviour on the detail page is real: `Issue.FullId`, the title, `CreatorDisplayName`, and `DateCreated.ToString("g")` (`IssueDetail.BindValues`). `FullId` is the project code, a hyphen, and the issue id.

`Administrator` is the installer profile (`profile.DisplayName = "Administrator"`). `10/2/2026 4:05 PM` is this host's current culture and clock. The message `Date` is `2 Oct 2026 16:05:39 +1000`, so the page's 4:05 PM is that same local time in a 12-hour `g` pattern. The pattern is en-US month/day on a +10 clock.

A test that asserts the sentence `created by Administrator on 10/2/2026 4:05 PM` fails for another user, another culture, or another time zone while the page is still showing the creator and the created-on time.

Suggested relabel: `preserve` the four fields, with created-on formatted by the current culture's general short pattern. Leave `Administrator` and the clock values unlabeled.

## B4. Empty owner and assignee. Severity: medium

A blank owner and a blank assignee do save. The notify-owner and notify-assignee boxes default to checked in `CreateIssue.aspx`, and `SaveIssue` adds an issue subscriber only when the username is non-empty. That part of B4 matches the code and the two 302s.

The empty dropdowns are the fixture. The recording says the owner and assignee lists had no user to select. `CreateIssue.BindOptions` sets the owner selection to `User.Identity.Name` when that user is in the project user list. A normal project with members does not post an empty owner.

A test that a successful create posts an empty owner fails on a project whose member list contains the signed-in user.

Suggested relabel: `preserve` "a blank owner and a blank assignee are accepted, and a checked notify box adds no recipient when the username is empty." Do not preserve empty owner as the form's usual submit. The default owner selection is unrecorded.

## B10. HTML part and MIME headers. Severity: medium

The decoded bodies match `Templates/Html/IssueAdded.xslt`: both reply markers, the monitoring sentence, the field table, and the profile opt-out sentence. That match is real.

`Content-Type: text/html` and the choice of the HTML template come from host setting `SMTPEMailFormat`. The seed is `2`, which is `EmailFormatType.HTML`. The code also sets `IsBodyHtml = true` on every add-notification, including the text-template branch. `charset=us-ascii` and `Content-Transfer-Encoding: quoted-printable` are what `System.Net.Mail` wrote for this ASCII body.

A test that requires `us-ascii`, `quoted-printable`, or HTML regardless of `SMTPEMailFormat` fails for a UTF-8 body, a different mail stack, or a host whose format setting is text (the case U5 left unknown). The template sentences can still be right.

Suggested relabel: `preserve` the decoded add-issue template text for the selected format. Leave charset and transfer encoding unlabeled. HTML in this recording is the seed format setting.

## B9. Subject language. Severity: low

The subject pattern is the `IssueAddedSubject` resource: `Issue {0} has been added to a project you are monitoring.` `FormatContent` is also passed the project name, and the format string ignores it. Culture comes from the subscriber's `PreferredLocale`, whose profile default is `en-US`.

The recorded English sentence matches that default. A test that always expects the English sentence fails for a subscriber with another locale.

Suggested relabel: `preserve` the `IssueAddedSubject` pattern for the recipient culture, with the issue key in `{0}` and the project name omitted. The English wording in this recording is the default locale.

## B11 and B12. Fixture words in the body. Severity: medium

The field set is the template: title, project, created by, milestone, category, priority, type, description. Milestone and category ids that do not join render as `Unassigned` because `BugNet_IssuesView` uses `ISNULL(..., N'Unassigned')`. The mail path reads that view through `GetIssueById`. It does not use `IssueManager.LocalizeUnassigned`. Priority `1` and type `1` render as the joined row names.

`Slice recording`, `Administrator`, `Normal`, `Bug`, and the two description sentences are the project, the installer display name, the lookup rows added before the recording, and the posted text. `Normal` and `Bug` are not product constants.

A body snapshot that requires those words fails on another project whose priority 1 is not named `Normal`, while "posted lookups render by name" is still true. A test that expects a localized `Unassigned` from the resource file is testing a different path than the email.

Suggested relabel: `preserve` the template field set, the view's English `Unassigned` for a missing milestone or category join, and the joined name for priority and type. Leave the recorded names and sentences unlabeled.

The description is written with `disable-output-escaping`. These two bodies are plain sentences, so the recording does not show whether markup is escaped. A test that the description is HTML-escaped is unsupported. Keep that case out of the `preserve` row.

## Missing from the critical path: the creator vote. Severity: medium

`CreateIssue.SaveIssue` stores one `IssueVote` for the signed-in user after the issue insert and before `SendIssueAddNotifications`. If that vote save returns false, the method returns false and `LnkSaveClick` does not redirect. The detail page binds `IssueVoteCount` from the issue. The recording's 302 and both messages happened after that vote save. The detail quote does not mention the vote box.

No proposed row covers it. A slice can skip the vote and still match B1 through B15 as written.

Suggested relabel: add `preserve`, on the critical path: a successful create stores one vote by the creator before the notification and the redirect. The on-page vote text is unrecorded, so leave the visible label text unlabeled.
