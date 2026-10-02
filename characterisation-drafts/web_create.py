import email
import email.policy
import html
import http.cookiejar
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

BASE = os.environ.get("BUGNET_BASE_URL", "http://15.135.1.105").rstrip("/")
BUCKET = "bugnet-dryrun-migrate-500766168271"
MAIL_PREFIX = "mail/"
MAIL_TIMEOUT_S = 150

GENERAL_SHORT = {
    "de-DE": "dd.MM.yyyy HH:mm",
    "en-US": "M/d/yyyy h:mm tt",
    "es-ES": "dd/MM/yyyy H:mm",
    "fr-CA": "yyyy-MM-dd HH:mm",
    "it-IT": "dd/MM/yyyy HH:mm",
    "nl-NL": "d-M-yyyy HH:mm",
    "ro-RO": "dd.MM.yyyy HH:mm",
    "ru-RU": "dd.MM.yyyy H:mm",
    "zh-CN": "yyyy/M/d H:mm",
}

ISSUE_ADDED_SUBJECT = {
    "": "Issue {0} has been added to a project you are monitoring.",
    "de-DE": "Aufgabe {0} wurde zu einem von Ihnen überwachten Projekt hinzugefügt.",
    "es-ES": "El caso {0} se ha añadido a un proyecto que está monitorizando.",
    "fr-CA": "Anomalie {0} a été ajoutée à un projet que vous surveillez.",
    "it-IT": "La segnalazione {0} è stata aggiunta al progetto che stai osservando.",
    "nl-NL": "Punt {0} is toegevoegd aan een project wat u volgt.",
    "ro-RO": "Problema {0} a fost adaugata la proiectul pe care-l monitorizati.",
    "ru-RU": "Задание {0} было добавлено в наблюдаемый Вами проект.",
    "zh-CN": "你关注的项目添加了一个新问题 {0}",
}

ADDED_TEMPLATE_MARK = "The following issue has been added to a project that you are monitoring."
UPDATED_TEMPLATE_MARK = "The following issue has been updated by"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _password():
    value = os.environ.get("BUGNET_ADMIN_PASSWORD", "")
    if not value:
        raise AssertionError("BUGNET_ADMIN_PASSWORD is not set")
    return value


def _redact(text):
    secret = os.environ.get("BUGNET_ADMIN_PASSWORD", "")
    if secret and secret in text:
        return text.replace(secret, "[redacted]")
    return text


def _input_value(page, name):
    for match in re.finditer(r"<input\b[^>]*>", page, re.I):
        tag = match.group(0)
        found = re.search(r'name="([^"]*)"', tag)
        if not found or found.group(1) != name:
            continue
        value = re.search(r'value="([^"]*)"', tag)
        return html.unescape(value.group(1)) if value else ""
    return ""


def _checked(page, element_id):
    match = re.search(r'<input\b[^>]*id="%s"[^>]*>' % re.escape(element_id), page)
    return bool(match and "checked=" in match.group(0))


def _select_block(page, element_id):
    match = re.search(
        r'<select\b[^>]*id="%s"[^>]*>(.*?)</select>' % re.escape(element_id),
        page,
        re.S,
    )
    if not match:
        raise AssertionError("missing select " + element_id)
    return match.group(1)


def _options(page, element_id):
    options = []
    for match in re.finditer(r"<option([^>]*)>(.*?)</option>", _select_block(page, element_id), re.S):
        attrs = match.group(1)
        value = re.search(r'value="([^"]*)"', attrs)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(2))).strip()
        options.append(
            (
                html.unescape(value.group(1)) if value else "",
                html.unescape(text),
                "selected" in attrs,
            )
        )
    return options


def _selected_value(page, element_id):
    for value, _text, selected in _options(page, element_id):
        if selected:
            return value
    options = _options(page, element_id)
    return options[0][0] if options else ""


def _first_joined(page, element_id):
    for value, text, _selected in _options(page, element_id):
        if value not in ("", "0"):
            return value, text
    raise AssertionError("no joined row in " + element_id)


def _span_text(page, element_id):
    match = re.search(
        r'<span\b[^>]*id="%s"[^>]*>(.*?)</span>' % re.escape(element_id),
        page,
        re.S,
    )
    if not match:
        raise AssertionError("missing span " + element_id)
    text = re.sub(r"<[^>]+>", "", match.group(1))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _date_token_regex(pattern):
    tokens = [
        ("yyyy", r"\d{4}"),
        ("HH", r"(?:[01]\d|2[0-3])"),
        ("hh", r"(?:0[1-9]|1[0-2])"),
        ("mm", r"[0-5]\d"),
        ("dd", r"(?:0[1-9]|[12]\d|3[01])"),
        ("MM", r"(?:0[1-9]|1[0-2])"),
        ("tt", r"(?:AM|PM)"),
        ("H", r"(?:2[0-3]|1\d|\d)"),
        ("h", r"(?:1[0-2]|[1-9])"),
        ("d", r"(?:[12]\d|3[01]|[1-9])"),
        ("M", r"(?:1[0-2]|[1-9])"),
    ]
    regex = ""
    index = 0
    while index < len(pattern):
        for token, piece in tokens:
            if pattern.startswith(token, index):
                regex += piece
                index += len(token)
                break
        else:
            regex += re.escape(pattern[index])
            index += 1
    return regex


def matches_general_short(text, culture):
    pattern = GENERAL_SHORT.get(culture)
    if not pattern:
        raise AssertionError("no general-short pattern for culture " + culture)
    if re.fullmatch(_date_token_regex(pattern), text.strip()) is None:
        raise AssertionError(
            "created-on text is not the " + culture + " general short pattern: " + text
        )


def issue_added_subject(culture):
    name = (culture or "").strip()
    while name:
        if name in ISSUE_ADDED_SUBJECT:
            return ISSUE_ADDED_SUBJECT[name]
        if "-" in name:
            name = name.split("-", 1)[0]
            continue
        break
    if "" in ISSUE_ADDED_SUBJECT:
        return ISSUE_ADDED_SUBJECT[""]
    raise AssertionError("no IssueAddedSubject for culture " + (culture or ""))


@dataclass
class UserRow:
    username: str
    email: str
    approved: bool


@dataclass
class Facts:
    application_title: str
    default_url: str
    host_email: str
    email_format: str
    allow_reply_to: bool
    default_language: str
    preferred_locale: str
    username: str
    display_name: str
    email: str
    notifications_on: bool
    subscribed_project_ids: list
    users: list


@dataclass
class Mail:
    key: str
    sender: str
    to: str
    subject: str
    content_type: str
    body: str
    fields: dict = field(default_factory=dict)


@dataclass
class Issue:
    row_id: str
    project_id: str
    project_code: str
    project_name: str
    title: str
    description: str
    status_id: str
    resolution_id: str
    priority_id: str
    priority_name: str
    type_id: str
    type_name: str
    milestone_id: str
    category_id: str
    redirect_status: int
    location: str
    issue_id: int
    detail_html: str
    detail_full_id: str
    detail_title: str
    detail_creator: str
    detail_created: str
    detail_status_id: str
    detail_resolution_id: str
    owner_value: str
    assignee_value: str
    vote_count: str
    keys_before: set
    keys_at_redirect: set

    @property
    def full_id(self):
        return f"{self.project_code}-{self.issue_id}"


def html_fields(body):
    fields = {}
    for match in re.finditer(r"<b>\s*([^<:]+):\s*</b>\s*</td>\s*<td[^>]*>(.*?)</td>", body, re.S):
        value = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(2))).strip()
        fields[html.unescape(match.group(1)).strip()] = html.unescape(value)
    description = re.search(
        r"<b>\s*Description:\s*</b>.*?<td\b[^>]*>(.*?)</td>",
        body,
        re.S,
    )
    if description:
        value = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", description.group(1))).strip()
        fields["Description"] = html.unescape(value)
    return fields


def text_fields(body):
    fields = {}
    for line in body.splitlines():
        if ": " not in line:
            continue
        label, value = line.split(": ", 1)
        label = label.strip()
        if label in {
            "Title",
            "Project",
            "Created By",
            "Milestone",
            "Category",
            "Priority",
            "Type",
            "Description",
            "Status",
            "Resolution",
        }:
            fields[label] = value.strip()
    return fields


class Host:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.no_redirect = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            NoRedirect(),
        )
        self._facts = None
        self._project_id = None
        self._mail = {}

    def _request(self, opener, path, data=None):
        payload = None
        headers = {"User-Agent": "bugnet-characterisation"}
        if data is not None:
            payload = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(BASE + path, data=payload, headers=headers)
        try:
            with opener.open(request, timeout=90) as response:
                body = response.read().decode("utf-8", "replace")
                return response.status, response.geturl(), body
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            location = error.headers.get("Location")
            return error.code, location or error.geturl(), body

    def get(self, path):
        status, url, body = self._request(self.opener, path)
        if status != 200:
            raise AssertionError(f"GET {path} returned {status}")
        return body

    def post_once(self, path, data):
        return self._request(self.no_redirect, path, data)

    def login(self):
        page = self.get("/Account/Login.aspx")
        status, location, body = self.post_once(
            "/Account/Login.aspx",
            {
                "__VIEWSTATE": _input_value(page, "__VIEWSTATE"),
                "__VIEWSTATEGENERATOR": _input_value(page, "__VIEWSTATEGENERATOR"),
                "__EVENTVALIDATION": _input_value(page, "__EVENTVALIDATION"),
                "ctl00$MainContent$LoginView$UserName": "Admin",
                "ctl00$MainContent$LoginView$Password": _password(),
                "ctl00$MainContent$LoginView$LoginButton": "Login",
            },
        )
        if status not in (301, 302):
            raise AssertionError("login failed with status " + str(status))
        if location and "Login" in location:
            raise AssertionError("login failed")
        return _redact(body)

    def _hidden(self, page):
        return {
            "__VIEWSTATE": _input_value(page, "__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": _input_value(page, "__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": _input_value(page, "__EVENTVALIDATION"),
        }

    def _postback(self, path, page, target, argument):
        data = self._hidden(page)
        data["__EVENTTARGET"] = target
        data["__EVENTARGUMENT"] = argument
        status, _location, body = self.post_once(path, data)
        if status != 200:
            raise AssertionError(f"postback {target} returned {status}")
        return body

    def _load_facts(self):
        basic = self.get("/Administration/Host/Settings.aspx?tid=0")
        mail = self.get("/Administration/Host/Settings.aspx?tid=2")
        pop3 = self.get("/Administration/Host/Settings.aspx?tid=7")
        language = self.get("/Administration/Host/Settings.aspx?tid=8")
        profile = self.get("/Account/UserProfile.aspx")
        preferences = self._postback(
            "/Account/UserProfile.aspx",
            profile,
            "ctl00$MainContent$BulletedList4",
            "1",
        )
        notifications = self._postback(
            "/Account/UserProfile.aspx",
            profile,
            "ctl00$MainContent$BulletedList4",
            "2",
        )
        users_page = self.get("/Administration/Users/UserList.aspx")
        selected = _options(notifications, "MainContent_lstSelectedProjects")
        format_value = ""
        for match in re.finditer(
            r'<input\b[^>]*name="ctl00\$MainContent\$ctlHostSetting\$SMTPEmailFormat"[^>]*>',
            mail,
        ):
            tag = match.group(0)
            if "checked=" in tag:
                format_value = re.search(r'value="([^"]*)"', tag).group(1)
        language_value = ""
        for value, _text, selected_flag in _options(
            language, "MainContent_ctlHostSetting_ApplicationDefaultLanguage"
        ):
            if selected_flag:
                language_value = value
        self._facts = Facts(
            application_title=_input_value(basic, "ctl00$MainContent$ctlHostSetting$ApplicationTitle"),
            default_url=_input_value(basic, "ctl00$MainContent$ctlHostSetting$DefaultUrl"),
            host_email=_input_value(mail, "ctl00$MainContent$ctlHostSetting$HostEmail"),
            email_format=format_value,
            allow_reply_to=_checked(pop3, "MainContent_ctlHostSetting_POP3AllowReplyTo"),
            default_language=language_value,
            preferred_locale=_selected_value(preferences, "MainContent_ddlPreferredLocale"),
            username=_input_value(profile, "ctl00$MainContent$UserName"),
            display_name=_input_value(profile, "ctl00$MainContent$FullName"),
            email=_input_value(profile, "ctl00$MainContent$Email"),
            notifications_on=_checked(notifications, "MainContent_AllowNotifications"),
            subscribed_project_ids=[value for value, _text, _selected in selected],
            users=_users(users_page),
        )

    @property
    def facts(self):
        if self._facts is None:
            self.login()
            self._load_facts()
        return self._facts

    def project_id(self):
        if self._project_id is None:
            self.facts
            home = self.get("/Default")
            match = re.search(r"Issues/CreateIssue/(\d+)", home)
            if not match:
                raise AssertionError("no create-issue link on the home page")
            self._project_id = match.group(1)
        return self._project_id

    def observable_subscriber_emails(self, project_id):
        facts = self.facts
        user = next((row for row in facts.users if row.username == facts.username), None)
        if user is None or not user.approved or not facts.notifications_on:
            return []
        if project_id not in facts.subscribed_project_ids:
            return []
        return [user.email]

    def list_mail_keys(self):
        completed = subprocess.run(
            [
                "aws",
                "s3api",
                "list-objects-v2",
                "--bucket",
                BUCKET,
                "--prefix",
                MAIL_PREFIX,
                "--query",
                "Contents[].Key",
                "--output",
                "text",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        text = completed.stdout.strip()
        if not text or text == "None":
            return []
        return text.split()

    def _read_mail(self, key):
        raw = subprocess.check_output(["aws", "s3", "cp", f"s3://{BUCKET}/{key}", "-"])
        message = email.message_from_bytes(raw, policy=email.policy.default)
        body = message.get_content()
        if message.get_content_type() == "text/html":
            fields = html_fields(body)
        else:
            fields = text_fields(body)
        return Mail(
            key=key,
            sender=message.get("from", ""),
            to=message.get("to", ""),
            subject=message.get("subject", ""),
            content_type=message.get_content_type(),
            body=body,
            fields=fields,
        )

    def messages_about(self, issue):
        cached = self._mail.get(issue.issue_id)
        if cached is not None:
            return cached
        deadline = time.time() + MAIL_TIMEOUT_S
        while time.time() < deadline:
            keys = [key for key in self.list_mail_keys() if key not in issue.keys_before]
            matched = []
            for key in keys:
                message = self._read_mail(key)
                if issue.title in message.body:
                    matched.append(message)
            if matched:
                self._mail[issue.issue_id] = matched
                return matched
            time.sleep(5)
        raise AssertionError(
            f"no mail whose body contains the posted title within {MAIL_TIMEOUT_S}s"
        )

    def recipient_addresses(self, issue):
        found = set()
        for message in self.messages_about(issue):
            for part in message.to.split(","):
                _name, address = email.utils.parseaddr(part)
                if address:
                    found.add(address)
        return found

    def create(self, row_id):
        facts = self.facts
        project_id = self.project_id()
        page = self.get(f"/Issues/CreateIssue/{project_id}")
        code_match = re.search(r"<span>\(([^)<]+)\)</span>", page)
        name_match = re.search(r"<small>\s*(.*?)\s*<span>\(", page, re.S)
        if not code_match or not name_match:
            raise AssertionError("create page has no project code")
        project_code = html.unescape(code_match.group(1).strip())
        project_name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", name_match.group(1))).strip()
        project_name = html.unescape(project_name)
        status_id, _status_name = _first_joined(page, "MainContent_DropStatus_dropStatus")
        resolution_id, _resolution_name = _first_joined(page, "MainContent_DropResolution_ddlResolution")
        priority_id, priority_name = _first_joined(page, "MainContent_DropPriority_ddlPriority")
        type_id, type_name = _first_joined(page, "MainContent_DropIssueType_ddlType")
        token = f"{row_id}-{int(time.time())}-{os.urandom(2).hex()}"
        title = f"Row {row_id} {token}"
        description = f"Posted description {token}"
        data = self._hidden(page)
        data.update(
            {
                "__EVENTTARGET": "ctl00$MainContent$lnkSave",
                "__EVENTARGUMENT": "",
                "ctl00$MainContent$TitleTextBox": title,
                "ctl00$MainContent$DropStatus$dropStatus": status_id,
                "ctl00$MainContent$DropOwned$ddlUsers": "",
                "ctl00$MainContent$chkNotifyOwner": "on",
                "ctl00$MainContent$DropPriority$ddlPriority": priority_id,
                "ctl00$MainContent$DropAffectedMilestone$ddlMilestone": "0",
                "ctl00$MainContent$DropAssignedTo$ddlUsers": "",
                "ctl00$MainContent$chkNotifyAssignedTo": "on",
                "ctl00$MainContent$DropCategory$ddlComps": "0",
                "ctl00$MainContent$DueDatePicker$DateTextBox": "",
                "ctl00$MainContent$DropIssueType$ddlType": type_id,
                "ctl00$MainContent$ProgressSlider": "0",
                "ctl00$MainContent$DropMilestone$ddlMilestone": "0",
                "ctl00$MainContent$txtEstimation": "",
                "ctl00$MainContent$DropResolution$ddlResolution": resolution_id,
                "ctl00$MainContent$DescriptionHtmlEditor$DescriptionHtmlEditor": description,
            }
        )
        keys_before = set(self.list_mail_keys())
        status, location, body = self.post_once(f"/Issues/CreateIssue/{project_id}", data)
        keys_at_redirect = set(self.list_mail_keys())
        if status not in (301, 302):
            snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _redact(body)))[:240]
            raise AssertionError(f"create returned {status}: {snippet}")
        path = location or ""
        if path.startswith("http"):
            parsed = urllib.parse.urlparse(path)
            path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        id_match = re.search(r"[?&]id=(\d+)", path)
        if not id_match:
            raise AssertionError("redirect did not name an issue id: " + path)
        issue_id = int(id_match.group(1))
        detail = self.get(f"/Issues/IssueDetail.aspx?id={issue_id}")
        return Issue(
            row_id=row_id,
            project_id=project_id,
            project_code=project_code,
            project_name=project_name,
            title=title,
            description=description,
            status_id=status_id,
            resolution_id=resolution_id,
            priority_id=priority_id,
            priority_name=priority_name,
            type_id=type_id,
            type_name=type_name,
            milestone_id="0",
            category_id="0",
            redirect_status=status,
            location=path,
            issue_id=issue_id,
            detail_html=detail,
            detail_full_id=_span_text(detail, "MainContent_lblIssueNumber"),
            detail_title=_span_text(detail, "MainContent_DisplayTitleLabel"),
            detail_creator=_span_text(detail, "MainContent_lblReporter"),
            detail_created=_span_text(detail, "MainContent_lblDateCreated"),
            detail_status_id=_selected_value(detail, "MainContent_DropStatus_dropStatus"),
            detail_resolution_id=_selected_value(detail, "MainContent_DropResolution_ddlResolution"),
            owner_value=_selected_value(detail, "MainContent_DropOwned_ddlUsers"),
            assignee_value=_selected_value(detail, "MainContent_DropAssignedTo_ddlUsers"),
            vote_count=_span_text(detail, "MainContent_IssueVoteCount"),
            keys_before=keys_before,
            keys_at_redirect=keys_at_redirect,
        )


def _users(page):
    users = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", page, re.S):
        cells = [
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cell)).strip()
            for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S)
        ]
        emails = [cell for cell in cells if "@" in cell]
        if not emails:
            continue
        index = cells.index(emails[0])
        if index < 2:
            continue
        users.append(
            UserRow(
                username=cells[index - 2],
                email=emails[0],
                approved='checked="checked"' in row,
            )
        )
    return users


_HOST = None


def host():
    global _HOST
    if _HOST is None:
        _HOST = Host()
    return _HOST

