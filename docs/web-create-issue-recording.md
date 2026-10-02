# Web create-issue recording

Two issues were created through the web form on `http://15.135.1.105/`. SOAP was not called. The pickup directory setting was not changed. Each create was a separate success, and each one produced one notification message. The message files below are the objects read from S3.

The From address on both messages is `BugNET Issue Tracker <noreply@mysmtpserver.com>`.

## Host setup used for the creates

`Issues/CreateIssue/1` needs a project. The project wizard at `Administration/Projects/AddProject.aspx` created project id 1, name `Slice recording`, code `BN`. The project administration pages then added status `Open`, priority `Normal`, issue type `Bug`, and resolution `Not set`.

On `Issues/CreateIssue/1` the owner and assignee dropdowns had no user to select. `Account/UserProfile.aspx` already had email notifications checked for `Admin`, and that page was used to subscribe `Admin` to project 1. The notification messages name that subscription.

## Create 1

`POST /Issues/CreateIssue/1` with `lnkSave`.

| Field | Posted value |
| --- | --- |
| Title | Recording one: web create |
| Description | First web create-issue recording. |
| Status | 1 |
| Priority | 1 |
| Type | 1 |
| Resolution | 1 |
| Milestone | 0 |
| Category | 0 |
| Owner | empty |
| Assignee | empty |
| Notify owner | checked |
| Notify assignee | checked |

The response was `302 /Issues/IssueDetail.aspx?id=1`. A later `GET` of that page returned 200 and showed `BN-1: Recording one: web create`, created by Administrator on 10/2/2026 4:05 PM.

The notification object was `s3://bugnet-dryrun-migrate-500766168271/mail/slot-0002.eml` (2048 bytes, sha256 `ed067feb4a929ca6d6ab357468078a594f0e48611cf9c53f0f2c75ff0f83cbe5`). The copy is [create-issue-1.eml](recordings/create-issue-1.eml).

```text
From: BugNET Issue Tracker <noreply@mysmtpserver.com>
To: admin@yourdomain.com
Subject: Issue BN-1 has been added to a project you are monitoring.
Date: Fri, 02 Oct 2026 16:05:39 +1000
Content-Type: text/html; charset="us-ascii"
```

The HTML body contains the title `Recording one: web create`, project `Slice recording`, created by `Administrator`, priority `Normal`, type `Bug`, milestone `Unassigned`, category `Unassigned`, and the description `First web create-issue recording.` The detail link in the body is `http://localhost/BugNet/Issues/IssueDetail.aspx?id=1`.

## Create 2

A second `POST /Issues/CreateIssue/1` with `lnkSave`, after the first message had already been read.

| Field | Posted value |
| --- | --- |
| Title | Recording two: web create |
| Description | Second web create-issue recording. |
| Status | 1 |
| Priority | 1 |
| Type | 1 |
| Resolution | 1 |
| Milestone | 0 |
| Category | 0 |
| Owner | empty |
| Assignee | empty |
| Notify owner | checked |
| Notify assignee | checked |

The response was `302 /Issues/IssueDetail.aspx?id=2`. A later `GET` of that page returned 200 and showed `BN-2: Recording two: web create`, created by Administrator on 10/2/2026 4:06 PM.

The notification object was `s3://bugnet-dryrun-migrate-500766168271/mail/slot-0003.eml` (2049 bytes, sha256 `89b4019d5c479423fd3f2618aac33673a32f58902819548a95b62557b7bd5444`). The copy is [create-issue-2.eml](recordings/create-issue-2.eml).

```text
From: BugNET Issue Tracker <noreply@mysmtpserver.com>
To: admin@yourdomain.com
Subject: Issue BN-2 has been added to a project you are monitoring.
Date: Fri, 02 Oct 2026 16:06:28 +1000
Content-Type: text/html; charset="us-ascii"
```

The HTML body contains the title `Recording two: web create`, project `Slice recording`, created by `Administrator`, priority `Normal`, type `Bug`, milestone `Unassigned`, category `Unassigned`, and the description `Second web create-issue recording.` The detail link in the body is `http://localhost/BugNet/Issues/IssueDetail.aspx?id=2`.
