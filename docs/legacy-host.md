# Legacy host

The dry-run BugNET host is http://15.135.1.105/. The WSDL is http://15.135.1.105/Webservices/BugNetServices.asmx?WSDL.

The nightly shutdown task `bugnet-legacy-shutdown` is removed. The instance stays up. Start a stopped instance with `aws ec2 start-instances --instance-ids i-0a5a720ebfc186d69 --region ap-southeast-2`. // pragma: allowlist secret

The Admin password is in AWS Secrets Manager `bugnet-dryrun/admin-password`. The value is not stored in this repo.
