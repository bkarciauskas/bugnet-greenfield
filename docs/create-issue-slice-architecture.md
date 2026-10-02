# Create-issue slice on .NET 8

This is the architecture for the first greenfield slice. The build has not started. Ben has not said to start it. The live host at http://15.135.1.105/ stays up, and this slice does not connect to it.

The approved behaviour is [web-create-issue-labels.md](web-create-issue-labels.md). The legacy code map is [soap-create-issue.md](soap-create-issue.md). The characterisation drafts merged in `aa3b15e` sit in `characterisation-drafts/` and lock a stricter HTTP and email contract than the labels. SOAP is out of this slice.

## What the slice is

A signed-in user opens the create-issue page, posts a save, and the app stores one issue and one creator vote. It then starts one add-issue notification and answers `302` to the new issue. The redirect does not wait for the send to finish.

The page routes are the ones the labels and the drafts already name.

- `GET` and `POST` `/Issues/CreateIssue/{projectId}`
- `302` to `/Issues/IssueDetail.aspx?id={id}`
- Detail links and mail links use `Issues/IssueDetail.aspx?id={id}` and `Account/UserProfile.aspx`

`BugNet.Web` is ASP.NET Core Razor Pages on .NET 8. Those paths are Razor routes. The `.aspx` segment is part of the preserved URL. It is not a WebForms runtime.

## Where the code lives

Four projects. A fifth name is reserved and is not created for this slice.

| Project | Role |
| --- | --- |
| `src/BugNet.Core` | The create command, the issue key, the recipient rule, and the notification text. No ASP.NET types and no EF types. |
| `src/BugNet.Data` | EF Core on SQL Server. Maps the existing BugNET tables this slice writes and reads. |
| `src/BugNet.Web` | Razor Pages. Parses the posted form into a `CreateIssue` and calls Core. Starts the send. Returns the redirect. |
| `tests/BugNet.Core.Tests` | xUnit. Calls Core the way the page does and asserts the returned issue and the returned message. |

`src/BugNet.Soap` is the later CoreWCF host for `BugNetServices.asmx`. This slice does not add that project. [soap-create-issue.md](soap-create-issue.md) already shows that the ASMX service does not create an issue and does not send the add email. Its operations stay out. `ValidIssue`, `CreateNewIssueRevision`, `CreateNewIssueAttachment`, the category writes, the lookup reads, `LogIn`, and `LogOut` are that later host.

Core exists so the rules xUnit checks have no web framework and no database in the test. The page is a thin boundary. Data is the only project that knows table names.

## The data the page hands to Core

`CreateIssue` is the command. The Razor page fills it from the post and stops. Core does not read form fields.

- `ProjectId` from the route.
- `Title` from `ctl00$MainContent$TitleTextBox`.
- `Description` from `ctl00$MainContent$DescriptionHtmlEditor$DescriptionHtmlEditor`.
- `StatusId`, `ResolutionId`, `PriorityId`, and `TypeId` from the four dropdowns below.
- `OwnerUserName` and `AssigneeUserName`. Empty is valid.
- `NotifyOwner` and `NotifyAssignee`.
- `MilestoneId` and `CategoryId`. Posted `0` means no row.
- `AffectedMilestoneId`, due date, estimation, and progress. The drafts post them. The labels do not describe them. Store them when present, and do not invent behaviour for them.
- `CreatorUserName` from the signed-in user, not from the form.

Dropdown names the drafts post:

- `ctl00$MainContent$DropStatus$dropStatus`
- `ctl00$MainContent$DropResolution$ddlResolution`
- `ctl00$MainContent$DropPriority$ddlPriority`
- `ctl00$MainContent$DropIssueType$ddlType`
- `ctl00$MainContent$DropOwned$ddlUsers`
- `ctl00$MainContent$DropAssignedTo$ddlUsers`
- `ctl00$MainContent$DropMilestone$ddlMilestone`
- `ctl00$MainContent$DropAffectedMilestone$ddlMilestone`
- `ctl00$MainContent$DropCategory$ddlComps`

The save event target is `ctl00$MainContent$lnkSave`. The drafts also post `__VIEWSTATE`, `__VIEWSTATEGENERATOR`, and `__EVENTVALIDATION`. They never assert those values. The page accepts the fields and ignores them. There is no viewstate.

`IssueKey` is `ProjectCode`, a hyphen, and the new integer id. That is `Issue.FullId` in `src/BugNET.Entities/Issue.cs` in the legacy repo. The recording values `BN`, `BN-1`, and `BN-2` are fixture data.

`AddNotification` is the message Core returns. It has the from display name, the from address, one subject per recipient culture, the body, and the recipient addresses. The web project starts delivery with that object and does not wait.

## Save order

This matches `CreateIssue.SaveIssue` in `src/BugNET_WAP/Issues/CreateIssue.aspx.cs` for the steps the labels preserve. Custom fields and attachments are U5, unknown, and off the critical path. This slice has neither step.

1. Insert one `BugNet_Issues` row. Milestone id `0`, category id `0`, and an empty owner or assignee are stored as null, which is what `BugNet_Issue_CreateNewIssue` does with those inputs. `DateCreated` comes from the SQL Server clock, as `GetDate()` does in that procedure.
2. Insert one `BugNet_IssueVotes` row for the creator. A failed vote stops the method before mail and before the redirect. B16 and `characterisation-drafts/docs/code-level-notes.md` record that order.
3. When notify is checked and the username is non-empty, insert one `BugNet_IssueNotifications` row. A checked box with an empty username inserts nothing. That is B4. Return values on this step do not stop the save. The legacy page ignores them.
4. Build one add notification for that issue and start the send.
5. Return. The page then sends `302`.

Those three writes commit together, then the send starts, then the redirect returns. The legacy page has no transaction. The extra steps that made a partial row visible, a custom-field failure and an invalid attachment, are not in this slice. U2 stays true. The redirect does not wait for SMTP.

The creator is not removed from the recipient list. B8 says so. The legacy skip is commented out in `IssueNotificationManager.SendIssueAddNotifications`.

## EF Core and the database

The greenfield uses its own SQL Server database. It does not use the database behind http://15.135.1.105/. A create on the greenfield must not write a row on the live host.

Map the tables. Do not call the legacy stored procedures from the app. The procedure bodies stay in the legacy repo as the description of the write. EF Core is the writer.

Writes:

- `BugNet_Issues`
- `BugNet_IssueVotes`
- `BugNet_IssueNotifications`, only for a selected owner or assignee

Reads:

- `BugNet_IssuesView` for the joined names. Milestone, category, priority, and type use `ISNULL(..., N'Unassigned')` in `src/BugNET.Database/Views/BugNet_IssuesView.sql`. B12 locks the English word `Unassigned` for a milestone or category id that does not join, including when the field label is translated. Read the view. Do not translate that word.
- `BugNet_ProjectNotifications` for project subscribers. The page does not insert those rows.
- Membership approval, `Memberships.Email`, and `BugNet_UserProfiles.ReceiveEmailNotifications`.
- `BugNet_HostSettings` for `ApplicationTitle`, `HostEmailAddress`, `Pop3AllowReplyToEmail`, `SMTPEMailFormat`, `DefaultUrl`, and `ApplicationDefaultLanguage`.

Priority and type names in the mail are the joined row names. `Normal` and `Bug` are fixture names from the recording.

## The notification

Core builds the message. `BugNet.Web` only sends it.

From display name is host setting `ApplicationTitle`. The address is `HostEmailAddress`. When `Pop3AllowReplyToEmail` is on, insert `+iid-{id}` before `@`. Otherwise the address is unchanged. B6 locks that rule. The recorded strings `BugNET Issue Tracker` and `noreply@mysmtpserver.com` are unlabeled host data.

The subject is resource `IssueAddedSubject` for the recipient culture. `{0}` is the issue key. The project name is not a placeholder in that string. B9 locks the wording for the empty culture and for `de-DE`, `es-ES`, `fr-CA`, `it-IT`, `nl-NL`, `ro-RO`, `ru-RU`, and `zh-CN`. Those strings live in `characterisation-drafts/web_create.py` and in `src/BugNET_WAP/App_GlobalResources/Notifications.resx`. Copy them. An unknown culture fails the draft with `no IssueAddedSubject for culture`. Subjects do not fall back.

The body is the add-issue template for `SMTPEMailFormat`. Format `2` is HTML. Format `1` is text. Copy `src/BugNET_WAP/Templates/Html/IssueAdded.xslt` and `src/BugNET_WAP/Templates/Text/IssueAdded.xslt` into Core and render them. The drafts check the result, not the engine. HTML must contain `<b>Title:</b>` and must contain `<b>Label:</b></td><td>` for the fields. Text must contain `Title: `. The lead is `The following issue has been added to a project that you are monitoring.` for the default culture. `nl-NL`, `ru-RU`, and `ro-RO` have their own leads and labels in `web_create.py`. Other cultures use the English labels. The updated-issue lead must not appear.

The body fields, in order, are title, project, created by, milestone, category, priority, type, and description. Status and resolution are stored and selected on the detail page, which is U1, and they are absent from the body, which is B13.

Both links are the raw `DefaultUrl` value concatenated with the path. Insert no slash. The seed value `http://localhost/BugNet/` already has one, and that base is unlabeled install data.

Recipients are the distinct set of approved project subscribers and issue subscribers who have email notifications on. B8. The address is the membership email. Culture for the subject is the profile `PreferredLocale`, or `ApplicationDefaultLanguage` when the profile has none. An empty preferred locale on the detail page is a separate case. `characterisation-drafts/docs/code-level-notes.md` says the detail page then stays on the `web.config` culture `en-US`. The B2 draft does not cover that case. The slice follows the note for the detail page and follows the profile fallback for mail.

Set `IsBodyHtml` from the format setting. The legacy sender sets it true for both formats. U5 leaves a text-format body unrecorded, so this slice does not copy that flag.

Delivery is host configuration. B7 has no behaviour label. Pickup directory `C:\Email`, SMTP host names, and the collector keys are not create-issue behaviour. xUnit uses an in-memory sender that records the `AddNotification` and returns before a delayed complete. A development config may point SMTP at a pickup directory. That config is not a test oracle.

## What the detail page shows

The redirect target renders the fields the labels name and the elements `Host.create` reads before any row assertion runs. `characterisation-drafts/web_create.py` raises `missing span` or `missing select` without them.

Spans:

- `MainContent_lblIssueNumber` shows the issue key.
- `MainContent_DisplayTitleLabel` shows the title.
- `MainContent_lblReporter` shows the creator display name. B2 compares it to the signed-in profile display name. `Administrator` is unlabeled.
- `MainContent_lblDateCreated` shows `DateCreated` with the current culture's general short pattern. The draft patterns are in `GENERAL_SHORT` in `web_create.py`. The clocks `10/2/2026 4:05 PM` and `10/2/2026 4:06 PM` are unlabeled.

Selects, with the posted id selected for status and resolution:

- `MainContent_DropStatus_dropStatus`
- `MainContent_DropResolution_ddlResolution`
- `MainContent_DropOwned_ddlUsers`
- `MainContent_DropAssignedTo_ddlUsers`

Vote markup from `assert_creator_vote`:

- An element with `class="count"` whose text is `1`.
- No id containing `VoteButton`.
- An id containing `VotedLabel` with non-empty text.

The on-page vote label wording is unlabeled. The create page itself must show the project code as `<span>(code)</span>` and the project name in the `<small>` pattern `web_create.py` searches. The drafts read the code from that markup.

The GET default for owner, when the signed-in user is a project member, is unrecorded. B4 says so. The drafts post an empty owner. The slice does not preset the owner.

## xUnit

xUnit covers Core. It does not call http://15.135.1.105/, and it does not replace `characterisation-drafts/`.

Each test builds a `CreateIssue`, passes a fake clock, fake host settings, and fake subscribers, and asserts a literal result.

- The issue key is the project code, a hyphen, and the id.
- An empty owner and an empty assignee add no notification row, with both notify boxes checked.
- One creator vote exists before the notification is built.
- The subject for each locked culture uses `IssueAddedSubject` and contains the issue key.
- A missing milestone and a missing category render as `Unassigned`. Priority and type render as the given names.
- The body has the eight fields and has neither `Status` nor `Resolution`.
- Links are `DefaultUrl` plus the two paths, with no slash inserted.
- The send handle is started, and the method has returned while the fake sender is still incomplete.

`characterisation-tests/` stays locked. New characterisation tests stay in `characterisation-drafts/` until Ben reviews them. This architecture does not add or edit either tree.

## Preserve

Every row below is `preserve` in [web-create-issue-labels.md](web-create-issue-labels.md). All of them are on the critical path except U2.

| Id | Rule |
| --- | --- |
| B1 | A successful save returns 302 to `/Issues/IssueDetail.aspx?id={id}`. |
| B2 | The detail page shows the issue key, the title, the creator display name, and `DateCreated` in the current culture's general short pattern. |
| B3 | The issue key is the project code, a hyphen, and the issue id. |
| B4 | A blank owner and a blank assignee are accepted. A checked notify box adds no recipient when the username is empty. |
| B5 | A successful create starts one add notification whose subject names that issue. The message file need not exist when the 302 is sent. |
| B6 | From is `ApplicationTitle` and `HostEmailAddress`, with `+iid-{id}` only when reply-to is on. |
| B8 | One add notification goes to each approved project subscriber or issue subscriber who has email notifications on. The creator is not removed. |
| B9 | The subject is `IssueAddedSubject` for the recipient culture. `{0}` is the issue key. The project name is omitted. |
| B10 | The decoded body is the add-issue template for the selected mail format. |
| B11 | The body carries title, project, created by, milestone, category, priority, type, and description. |
| B12 | A milestone or category id that does not join renders as English `Unassigned`. Priority and type render as the joined name. |
| B13 | The body omits status and resolution. |
| B14 | The detail path is `Issues/IssueDetail.aspx?id={id}`. The profile path is `Account/UserProfile.aspx`. |
| B15 | Both links are `DefaultUrl` plus the B14 paths. |
| B16 | A successful create stores one vote by the creator before the notification and the redirect. |
| U1 | The posted status id and resolution id are stored and selected on the detail page. |
| U2 | The redirect does not wait for the send. Off the critical path. |

No row is `change`, `remove`, or `defect`.

## Unlabeled host data

These values appeared in the recording or in the draft client. They are not rules. Another host can change them and the preserve rows still hold.

From [web-create-issue-labels.md](web-create-issue-labels.md):

- `noreply@mysmtpserver.com` and `BugNET Issue Tracker`.
- `C:\Email`, and collector keys `mail/slot-0002.eml` and `mail/slot-0003.eml`.
- `admin@yourdomain.com`.
- `Administrator`.
- The en-US clocks on the detail page, including `10/2/2026 4:05 PM` and `10/2/2026 4:06 PM`.
- `charset=us-ascii` and `quoted-printable`.
- `Normal`, `Bug`, and `Slice recording`.
- The posted title and description sentences.
- The English subject wording, as the default locale of that recording.
- The link base `http://localhost/BugNet/`.
- Project code `BN`, keys `BN-1` and `BN-2`, status `Open`, resolution `Not set`, and the fact that the owner and assignee dropdowns had no user to select.

From the drafts, still unlabeled:

- The S3 bucket `bugnet-dryrun-migrate-500766168271` and prefix `mail/`. That is how the draft client observes mail on this host. B7. The 150 second poll is the client, not the product.
- The generated title `Row {row} {token}` and description `Posted description {token}`.
- The Admin password and the display name read from the host profile.
- Priority and type option text read from the live dropdowns.
- `ApplicationTitle`, `HostEmailAddress`, `DefaultUrl`, the format setting, and the reply-to flag, which the drafts read from the host and then expect to see again.

## What the drafts lock

`characterisation-drafts/run_rows.py` loads B1 through B6, B8 through B16, and U1. There is no `B7.py`. There is no `U2.py`, `U3.py`, `U4.py`, or `U5.py`. `break_rows.py` is not part of that suite. The drafts run against http://15.135.1.105/ today. This document does not retarget them.

They lock more than the label sentences, because `web_create.py` posts WebForms field names and reads WebForms element ids. A Razor page that preserved the behaviour with different names would fail these drafts if they were pointed at it. The slice keeps the names and ids listed above so that contract stays stable.

They do not lock viewstate, login, or the home page as product behaviour. `Host.create` does `POST /Account/Login.aspx` and reads `Issues/CreateIssue/{id}` from `GET /Default` before it opens the create page. Those steps are the draft client reaching a host that already has a session and a project. This slice does not rebuild `Login.aspx` or `Default.aspx`. Sign-in is a dependency. The page reads `User.Identity.Name`. How that principal is established is outside the labelled behaviour.

U3, U4, and U5 stay unknown and off the critical path. The slice does not define them.

- U3 is who receives mail when an owner or assignee username is selected. The code path for a non-empty username is the legacy insert into `BugNet_IssueNotifications`. The drafts never select a user, so there is no assertion to satisfy.
- U4 is who receives mail when the creator does not monitor the project. B8 does not separate the creator from the subscriber.
- U5 is an empty title, attachments, custom fields, non-ASCII text, and a text-format body as an unrecorded input. Shipping the text XSLT file answers B10's format branch. It does not close U5.

Description escaping is not part of B11. The slice copies the XSLT, which emits the description with `disable-output-escaping`. That is inheritance of the template, not a new rule.

## What this pull request does not do

No `.csproj`, no Razor page, no EF model, and no xUnit project. `characterisation-tests/` is untouched. `characterisation-drafts/` is untouched. The live host is untouched.

When Ben says to start, the order is Core and its xUnit tests, then the EF mapping against a private SQL Server, then the two Razor pages, then the sender. Each of those can be checked on its own. This document is the map, not the first of those commits.
