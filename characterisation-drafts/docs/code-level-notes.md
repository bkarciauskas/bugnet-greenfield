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

## B16. Vote order is not observable on the host

A successful create stores one vote by the creator. The detail page reached by the redirect renders that stored total in the vote count. The test reads that number.

The clause "before the notification and the redirect" is not observable from the HTTP exchange. The 302 is the response, and both the vote write and the notification queue happen before that response is sent. The client cannot see which of those two finished first.

The source order inside `SaveIssue` is the record. `IssueVoteManager.SaveOrUpdate` runs, then the empty-username notify checks, then `IssueNotificationManager.SendIssueAddNotifications`. `LnkSaveClick` redirects only after `SaveIssue` returns.

Citation: `src/BugNET_WAP/Issues/CreateIssue.aspx.cs`, `SaveIssue`, the vote save, then `SendIssueAddNotifications`, then `LnkSaveClick`'s `Response.Redirect`.
