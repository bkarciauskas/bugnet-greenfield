# AWS legacy host — this attempt stopped

Stopped 2026-10-02 04:49 UTC. SQL install was not finished. No fourth instance. Azure resource group `bugnet-dryrun` was not deleted.

Rechecked `http://15.135.1.105/` at 04:49:07Z before writing this: HTTP 200, 703 bytes, title `IIS Windows Server`, `Last-Modified: Fri, 02 Oct 2026 04:01:02 GMT`, `Server: Microsoft-IIS/10.0`. `GET /Webservices/BugNetServices.asmx?WSDL` returned 404. BugNET is not bound. SQL Server Express was not confirmed running. Instance `i-0a94bcf7d45f0d56c` was still `running`, `t3.large`, in the default VPC subnet `subnet-089c75748a31a2d1b`.

## What worked

These calls succeeded. Region `ap-southeast-2` unless noted. Tags on the group, address, and instances: `owner=ben.karciauskas@anysphere.co`, `project=bugnet-dryrun`, `Name=bugnet-legacy`.  // pragma: allowlist secret

AMI `ami-0cf95ca5b969cc689`, name `Windows_Server-2022-English-Full-Base-2026.09.17`. Found with:

```bash
aws ec2 describe-images --owners amazon \
  --filters Name=name,Values='Windows_Server-2022-English-Full-Base-*' Name=state,Values=available
```

Security group `sg-0b65de7cbc9379788` in `vpc-0b5e7df27a1b42637`:

```bash
aws ec2 create-security-group --group-name bugnet-legacy \
  --description "BugNET legacy inbound TCP 80 only" \
  --vpc-id vpc-0b5e7df27a1b42637
aws ec2 authorize-security-group-ingress --group-id sg-0b65de7cbc9379788 \
  --ip-permissions 'IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=0.0.0.0/0,Description=http-anywhere}]'
aws ec2 authorize-security-group-ingress --group-id sg-0b65de7cbc9379788 \
  --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,IpRanges=[{CidrIp=115.70.61.149/32,Description=rdp-admin-only}]'
```

Elastic IP `15.135.1.105`, allocation `eipalloc-0d31e6920ebaa5dd7`:

```bash
aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id i-0a94bcf7d45f0d56c --allocation-id eipalloc-0d31e6920ebaa5dd7
```

Secrets Manager secret `bugnet-dryrun/admin-password` (`arn:aws:secretsmanager:ap-southeast-2:500766168271:secret:bugnet-dryrun/admin-password-z2EGGh`). `CreateSecret` at 02:33:28Z succeeded. The secret value is not in this note.  // pragma: allowlist secret

S3 bucket `bugnet-dryrun-migrate-500766168271`:

```bash
aws s3api create-bucket --bucket bugnet-dryrun-migrate-500766168271 \
  --create-bucket-configuration LocationConstraint=ap-southeast-2  // pragma: allowlist secret
```

Objects that are the backups: `BugNET.bak` (5230592 bytes) and `bugnet-site.zip` (28802902 bytes).

The instance that was still up:

```bash
aws ec2 run-instances --image-id ami-0cf95ca5b969cc689 --instance-type t3.large \
  --key-name bugnet-legacy --subnet-id subnet-089c75748a31a2d1b \
  --security-group-ids sg-0b65de7cbc9379788 \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=50,VolumeType=gp3,DeleteOnTermination=true,Encrypted=true}' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=owner,Value=ben.karciauskas@anysphere.co},{Key=project,Value=bugnet-dryrun},{Key=Name,Value=bugnet-legacy}]'
```

That launch is `i-0a94bcf7d45f0d56c` at 03:57:51Z. No IAM instance profile. User data is not copied here; it contained download URLs. Two earlier launches of the same shape, `i-07b6b0b4da66e9227` and `i-066c6d53504ed9ce9`, were terminated. Their volumes were already gone at 04:49Z. The only volume left was `vol-0212cdeee223eb037`, attached to `i-0a94bcf7d45f0d56c`, `DeleteOnTermination=true`.

Windows features did install on the third instance. IIS 10.0 answered on port 80 and `X-Powered-By: ASP.NET` was present. That is as far as the box got.

## What failed

### SQL Express never came up

The first launches used the SQL Server Express web bootstrapper `SQLEXPR_x64_ENU.exe`. It exited without installing the engine. There was no `SQLEXPRESS` service afterwards.

The third launch switched to the SSEI downloader:

`SQL2019-SSEI-Expr.exe /ACTION=Download /MEDIATYPE=Core /MEDIAPATH=C:\setup\sqlmedia /QUIET`

then `SETUP.EXE /Q /ACTION=Install /FEATURES=SQLENGINE /INSTANCENAME=SQLEXPRESS`.

That stage was not confirmed. From 04:01Z, when IIS started serving the default page, until 04:49Z, the page did not change and the WSDL stayed 404. The EC2 console never printed a SQL line. With no remote exec, a silent install that hangs looks the same as one that already died.

### Logs in the web root, then a stale local file

The bootstrap appended to `C:\inetpub\wwwroot\setup-log.txt` and rewrote `C:\inetpub\wwwroot\setup-status.txt`, and a poll loop requested both on port 80. IIS locked the files. On the second instance the writer used an exclusive append, the lock threw, and the script stopped. The loop then read a status file left on the agent disk from the previous instance and treated that old stage as the new instance's progress. The third script shared the file so the lock would not throw, and it still wrote under `wwwroot`. Do not do that again. The log path has to be `C:\migrate\setup.log`, and nothing under `wwwroot` should be a setup file.

### SSM has no credentials

`aws ssm describe-instance-information` for `i-0a94bcf7d45f0d56c` returned no registrations. Console, 2026-10-02 03:58:50Z, word for word:

```
SSM Agent unable to acquire credentials: <error>no valid credentials could be retrieved for ec2 identity. Default Host Management Err: error calling RequestManagedInstanceRoleToken: AccessDeniedException: Systems Manager's instance management role is not configured for account: 500766168271
	status code: 400, request id: b170c710-22b0-4ad0-a3aa-1669971cdcd0</error>
```

Attaching `fe-lab-ssm-role` at launch failed. `RunInstances` at 02:43:02Z, word for word up to the policy (an encoded authorization failure message followed):

```
You are not authorized to perform this operation. User: arn:aws:iam::500766168271:user/ben.karciauskas@anysphere.co is not authorized to perform: iam:PassRole on resource: arn:aws:iam::500766168271:role/fe-lab-ssm-role with an explicit deny in an identity-based policy: arn:aws:iam::500766168271:policy/FELabOperatorDeny
```

### IAM denies, word for word

`iam:CreateRole` at 02:33:58Z, role `bugnet-dryrun-scheduler`:

```
User: arn:aws:iam::500766168271:user/ben.karciauskas@anysphere.co is not authorized to perform: iam:CreateRole on resource: arn:aws:iam::500766168271:role/bugnet-dryrun-scheduler with an explicit deny in an identity-based policy: arn:aws:iam::500766168271:policy/FELabOperatorDeny
```

`iam:GetRole` at 02:26:24Z:

```
User: arn:aws:iam::500766168271:user/ben.karciauskas@anysphere.co is not authorized to perform: iam:GetRole on resource: role fe-lab-ssm-role because no identity-based policy allows the iam:GetRole action. Go to https://us-east-1.console.aws.amazon.com/iam/home?region=us-east-1#/authorization-details/d3xbfwcsdoam45n7ms6nv5pl0 for complete details, or call the GetRequestAuthorizationDetails API with the following authorization id: d3xbfwcsdoam45n7ms6nv5pl0
```

`iam:ListInstanceProfiles` at 02:26:24Z:

```
User: arn:aws:iam::500766168271:user/ben.karciauskas@anysphere.co is not authorized to perform: iam:ListInstanceProfiles on resource: arn:aws:iam::500766168271:instance-profile/ because no identity-based policy allows the iam:ListInstanceProfiles action
```

CloudTrail for `ben.karciauskas@anysphere.co` on 2 Oct 2026 has no `iam:CreateUser` event, denied or otherwise. There is no CreateUser error message to quote. Do not invent one. The same search did record two related denials:

```
User: arn:aws:iam::500766168271:user/ben.karciauskas@anysphere.co is not authorized to perform: iam:GetInstanceProfile on resource: instance profile fe-lab-ssm-role because no identity-based policy allows the iam:GetInstanceProfile action. Go to https://us-east-1.console.aws.amazon.com/iam/home?region=us-east-1#/authorization-details/2y1350qq1mmznz1iuzhmrb4n0 for complete details, or call the GetRequestAuthorizationDetails API with the following authorization id: 2y1350qq1mmznz1iuzhmrb4n0
```

```
User: arn:aws:iam::500766168271:user/ben.karciauskas@anysphere.co is not authorized to perform: iam:ListInstanceProfilesForRole on resource: role fe-lab-ssm-role because no identity-based policy allows the iam:ListInstanceProfilesForRole action. Go to https://us-east-1.console.aws.amazon.com/iam/home?region=us-east-1#/authorization-details/7zbp7y3ds4l2uz67fem3hizqi for complete details, or call the GetRequestAuthorizationDetails API with the following authorization id: 7zbp7y3ds4l2uz67fem3hizqi
```

No scheduler role was created. No instance profile was attached. Do not work around `FELabOperatorDeny`.

## Azure, for comparison

The host that actually served BugNET:

- IIS site `BugNET` on port 80. App pool on .NET 4.x.
- SQL Server 2019 Express, instance `SQLEXPRESS`. Database `BugNET`, integrated security, app pool identity.
- Built from the fork `bkarciauskas/bugnet`. `README.md` is the project blurb and the MS-PL license. The build is `appveyor.yml`: `nuget restore src\BugNET.sln`, configuration `Release`, project `src\BugNET.sln`, `publish_wap: true`.

The difference that matters: Azure had `az vm run-command`, which returned the script output. This AWS lab has no remote exec. SSM is not configured for the account, and passing `fe-lab-ssm-role` is an explicit deny. A bootstrap that only writes a local log cannot be read unless the log is published, and publishing it through IIS is what locked the file.

## Leftovers to clean up

- S3 object `admin.pw` in `bugnet-dryrun-migrate-500766168271`. Delete it. Keep the bucket, `BugNET.bak`, and `bugnet-site.zip`.
- Presigned download URLs were issued for those two backups. They are not objects. Do not store them in user data or in git. They expire; the secret material to remove from the bucket is `admin.pw`.
- Volumes for terminated `i-07b6b0b4da66e9227` and `i-066c6d53504ed9ce9` were already gone. After `i-0a94bcf7d45f0d56c` is terminated, `vol-0212cdeee223eb037` should go with it (`DeleteOnTermination=true`). If it stays, delete it.
- Keep `sg-0b65de7cbc9379788`, EIP `15.135.1.105` (`eipalloc-0d31e6920ebaa5dd7`), the Secrets Manager secret, and the two S3 backups.

Leave Azure up.

## Cleanup done

- Deleted S3 object `admin.pw`. Bucket `bugnet-dryrun-migrate-500766168271` still has `BugNET.bak` and `bugnet-site.zip` only.
- `i-0a94bcf7d45f0d56c` is `terminated`. `vol-0212cdeee223eb037` is gone (`InvalidVolume.NotFound`). No `project=bugnet-dryrun` volumes remain. Volumes for `i-07b6b0b4da66e9227` and `i-066c6d53504ed9ce9` were already gone.
- Kept `sg-0b65de7cbc9379788`, Elastic IP `15.135.1.105` (`eipalloc-0d31e6920ebaa5dd7`, now unassociated), secret `bugnet-dryrun/admin-password`, and the two S3 backups.
- `az group show -n bugnet-dryrun` still returns the group. It was not deleted.
