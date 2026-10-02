# Code-level notes for rows the black-box host cannot show

## U2. The redirect does not wait for the send

The redirect does not wait for the send to finish. A black-box poll of the mail bucket cannot show that. The collector writes the bucket after pickup, so an object missing at the 302 can follow a send the request waited for, and an object already listed can follow a send the request did not wait for.

The source order is the record.

`CreateIssue.LnkSaveClick` calls `SaveIssue` and, when that returns true, calls `Response.Redirect` to the new issue. `SaveIssue` calls `IssueNotificationManager.SendIssueAddNotifications` before it returns. `SendIssueAddNotifications` builds the message and calls `SmtpMailDeliveryService.Send`. `Send` dispatches `SmtpClient.SendAsync` inside `await Task.Run`, so the HTTP request continues to the redirect without waiting for the SMTP send to finish.

Citations:

- `src/BugNET_WAP/Issues/CreateIssue.aspx.cs`, `LnkSaveClick`, `Response.Redirect` after `SaveIssue`
- `src/BugNET_WAP/Issues/CreateIssue.aspx.cs`, `SaveIssue`, `IssueNotificationManager.SendIssueAddNotifications`
- `src/BugNET.BLL/IssueNotificationManager.cs`, `SendIssueAddNotifications`, constructs `SmtpMailDeliveryService` and calls `Send`
- `src/BugNET.BLL/Notifications/SmtpMailDeliveryService.cs`, `Send`, `await Task.Run` around `client.SendAsync`

## B2. An empty preferred locale stays on the web.config culture

`DateCreated` uses the current culture's general short pattern. For an authenticated user, `LocalizationModule.context_PreRequestHandlerExecute` applies `PreferredLocale` only when that value is non-empty. When `PreferredLocale` is empty, the module does not set the thread culture. The detail page stays on the `web.config` globalization culture `en-US`. It does not switch to host setting `ApplicationDefaultLanguage`.

`B2.py` still calls `render_culture`. That helper uses the preferred locale when it is non-empty, and otherwise the host default language. The profile default is `en-US`, so the usual path matches the page. A blank preferred locale with a non-English host default language is the path this note records. The test does not cover that path.

Citations:

- `src/BugNET_WAP/Web.config`, `globalization culture="en-US"`
- `src/Library/HttpModules/Localization/LocalizationModule.cs`, `context_PreRequestHandlerExecute`

## B16. Vote order is not observable on the host

A successful create stores one vote by the creator. The detail page reached by the redirect renders the stored total in the vote count. The same page shows that the signed-in user has voted by hiding `VoteButton` and rendering `VotedLabel`. The test reads both. The signed-in user is the creator, and the total is 1, so that vote is the creator's.

The clause "before the notification and the redirect" is not observable from the HTTP exchange. The 302 is the response, and both the vote write and the notification queue happen before that response is sent. The client cannot see which of those two finished first.

The source order inside `SaveIssue` is the record. `IssueVoteManager.SaveOrUpdate` runs, then the empty-username notify checks, then `IssueNotificationManager.SendIssueAddNotifications`. `LnkSaveClick` redirects only after `SaveIssue` returns.

Citation: `src/BugNET_WAP/Issues/CreateIssue.aspx.cs`, `SaveIssue`, the vote save, then `SendIssueAddNotifications`, then `LnkSaveClick`'s `Response.Redirect`.
