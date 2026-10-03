# Try it yourself

Two apps are running on the same host. The current app stays on port 80. The new app is on port 8080 and has its own database.

- Current app: http://15.135.1.105/
- New app: http://15.135.1.105:8080/

Type the new-app link with `http://` at the front. A browser that guesses `https://` will hang.

Sign in as `Admin` on both. The password is in AWS Secrets Manager under the name `bugnet-dryrun/admin-password`. It is not stored in this repository.

## Checklist

1. Open http://15.135.1.105/ and sign in. Create an issue.
2. After you save, the browser should land on that issue. The address contains `/Issues/IssueDetail.aspx?id=` followed by a number. Write down the issue key shown on the page.
3. Open http://15.135.1.105:8080/ and sign in with the same Admin account. Create an issue. Check that this app also redirects to `/Issues/IssueDetail.aspx?id=` and write down its issue key. The two keys come from two databases, so they do not have to match.
4. List the notification emails. The current app writes to `mail/`. The new app writes to `mail-new/`.

   ```bash
   aws s3 ls s3://bugnet-dryrun-migrate-500766168271/mail-new/ --profile spacexai
   ```

   The same command with `mail/` lists the current app. In the console, open the bucket `bugnet-dryrun-migrate-500766168271` and look in those two folders.
5. Open the new email from each folder and compare them. Each message should name the issue you just created on that app.
