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
MAIL_PREFIX = os.environ.get("BUGNET_MAIL_PREFIX", "mail/")
if MAIL_PREFIX and not MAIL_PREFIX.endswith("/"):
    MAIL_PREFIX = MAIL_PREFIX + "/"
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

@dataclass(frozen=True)
class AddIssueTemplate:
    lead: str
    updated_lead: str
    labels: tuple


_INVARIANT_LABELS = (
    "Title",
    "Project",
    "Created By",
    "Milestone",
    "Category",
    "Priority",
    "Type",
    "Description",
)

ADD_ISSUE_TEMPLATES = {
    "": AddIssueTemplate(
        "The following issue has been added to a project that you are monitoring.",
        "The following issue has been updated by",
        _INVARIANT_LABELS,
    ),
    "nl-NL": AddIssueTemplate(
        "Het volgende punt is toegevoegd aan een project dat u volgt.",
        "Het volgende punt is bijgewerkt door",
        (
            "Titel",
            "Project",
            "Aangemaakt door",
            "Mijlpaal",
            "Categorie",
            "Prioriteit",
            "Type",
            "Omschrijving",
        ),
    ),
    "ru-RU": AddIssueTemplate(
        "В проект добавлено новое задание.",
        "Следующее задание было обновлено пользователем",
        (
            "Заголовок",
            "Проект",
            "Создатель",
            "Этап",
            "Категория",
            "Приоритет",
            "Тип",
            "Описание",
        ),
    ),
    "ro-RO": AddIssueTemplate(
        "Urmatoarea problema a fost adaugata la proiectul pe care-l monitorizati.",
        "Urmatoarea problema a fost actualizata de",
        (
            "Titlu",
            "Proiect",
            "Creat De",
            "Reper",
            "Categorie",
            "Prioritate",
            "Tip",
            "Descriere",
        ),
    ),
}
_SECRETS = []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _password():
    value = os.environ.get("BUGNET_ADMIN_PASSWORD", "")
    if not value:
        raise AssertionError("BUGNET_ADMIN_PASSWORD is not set")
    return value


def _remember_secret(value):
    if value and value not in _SECRETS:
        _SECRETS.append(value)


def _redact(text):
    secrets = [os.environ.get("BUGNET_ADMIN_PASSWORD", "")] + list(_SECRETS)
    for secret in secrets:
        if secret and secret in text:
            text = text.replace(secret, "[redacted]")
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


def _vote_total(page):
    match = re.search(r'class="count"[^>]*>\s*(\d+)\s*<', page)
    if not match:
        raise AssertionError("detail page has no stored vote total")
    return match.group(1)


def _form_values(page):
    values = {}
    for match in re.finditer(r"<input\b[^>]*>", page, re.I):
        tag = match.group(0)
        name_match = re.search(r'name="([^"]*)"', tag)
        if not name_match:
            continue
        name = name_match.group(1)
        type_match = re.search(r'type="([^"]*)"', tag, re.I)
        control_type = type_match.group(1).lower() if type_match else "text"
        value_match = re.search(r'value="([^"]*)"', tag)
        value = html.unescape(value_match.group(1)) if value_match else ""
        if control_type == "radio":
            if "checked" in tag.lower():
                values[name] = value
            continue
        if control_type == "checkbox":
            if "checked" in tag.lower():
                values[name] = value or "on"
            continue
        if control_type in ("submit", "image", "button"):
            continue
        values[name] = value
    return values


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


def render_culture(preferred_locale, default_language):
    return (preferred_locale or "").strip() or (default_language or "").strip()


def issue_added_subject(culture):
    name = (culture or "").strip()
    if name in ("", "en-US", "en"):
        return ISSUE_ADDED_SUBJECT[""]
    if name not in ISSUE_ADDED_SUBJECT:
        raise AssertionError("no IssueAddedSubject for culture " + (name or "(empty)"))
    return ISSUE_ADDED_SUBJECT[name]


def add_issue_template(culture):
    name = (culture or "").strip()
    if name in ("", "en-US", "en"):
        return ADD_ISSUE_TEMPLATES[""]
    return ADD_ISSUE_TEMPLATES.get(name, ADD_ISSUE_TEMPLATES[""])


def subject_names_issue(subject, full_id):
    pattern = r"(?<![A-Za-z0-9])" + re.escape(full_id) + r"(?![A-Za-z0-9])"
    if re.search(pattern, subject or "") is None:
        raise AssertionError("subject does not name " + full_id)


def message_culture(message, people, default_language):
    _name, address = email.utils.parseaddr(message.to)
    for person in people:
        if person.email.lower() == address.lower():
            return render_culture(person.preferred_locale, default_language)
    raise AssertionError("no subscriber for recipient " + address)


def message_recipients(messages):
    found = set()
    for message in messages:
        for part in message.to.split(","):
            _name, address = email.utils.parseaddr(part)
            if address:
                found.add(address.lower())
    return found


def qualifying_subscribers(people, project_id):
    project_id = str(project_id)
    return [
        person
        for person in people
        if person.approved and person.notifications_on and project_id in person.project_ids
    ]


def assert_add_issue_template(body, email_format, culture):
    template = add_issue_template(culture)
    title = template.labels[0]
    html_mark = "<b>" + title + ":</b>"
    text_mark = title + ": "
    if template.lead not in body:
        raise AssertionError("decoded body is not the add-issue template for " + (culture or "invariant"))
    if template.updated_lead in body:
        raise AssertionError("decoded body is the issue-updated template")
    if email_format == "2":
        if html_mark not in body or text_mark in body:
            raise AssertionError("decoded body is not the HTML add-issue template")
        return
    if email_format == "1":
        if html_mark in body or text_mark not in body:
            raise AssertionError("decoded body is not the text add-issue template")
        return
    raise AssertionError("unread mail format setting")


def template_fields(body, culture, email_format):
    template = add_issue_template(culture)
    if email_format == "2":
        return _html_template_fields(body, template.labels)
    if email_format == "1":
        return _text_template_fields(body, template.labels)
    raise AssertionError("unread mail format setting")


def _field_value(raw):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", raw)).strip())


def _html_template_fields(body, labels):
    fields = {}
    description = labels[-1]
    for label in labels:
        if label == description:
            continue
        match = re.search(
            r"<b>\s*" + re.escape(label) + r"\s*:\s*</b>\s*</td>\s*<td[^>]*>(.*?)</td>",
            body,
            re.S,
        )
        if match:
            fields[label] = _field_value(match.group(1))
    match = re.search(
        r"<b>\s*" + re.escape(description) + r"\s*:\s*</b>.*?<td\b[^>]*>(.*?)</td>",
        body,
        re.S,
    )
    if match:
        fields[description] = _field_value(match.group(1))
    return fields


def _text_template_fields(body, labels):
    wanted = set(labels)
    fields = {}
    for line in body.splitlines():
        if ": " not in line:
            continue
        label, value = line.split(": ", 1)
        label = label.strip()
        if label in wanted and label not in fields:
            fields[label] = value.strip()
    return fields


def viewer_has_voted(page):
    button = re.search(r'id="[^"]*VoteButton"', page or "")
    label = re.search(r'id="[^"]*VotedLabel"[^>]*>(.*?)</span>', page or "", re.S)
    voted = _field_value(label.group(1)) if label else ""
    return button is None and voted != ""


def assert_creator_vote(page):
    total = _vote_total(page)
    if total != "1":
        raise AssertionError("stored vote total is " + total)
    if not viewer_has_voted(page):
        raise AssertionError("stored vote is not the signed-in creator's")


@dataclass
class UserRow:
    username: str
    email: str
    approved: bool


@dataclass
class Subscriber:
    username: str
    email: str
    approved: bool
    notifications_on: bool
    project_ids: tuple
    preferred_locale: str
    display_name: str


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
        self._accounts = {}
        self._user = None
        self._secret = None

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

    def _ensure_login(self):
        if self._user is None:
            self.login()

    def login(self, username="Admin", password=None):
        password = _password() if password is None else password
        _remember_secret(password)
        self._user = username
        self._secret = password
        page = self.get("/Account/Login.aspx")
        status, location, body = self.post_once(
            "/Account/Login.aspx",
            {
                "__VIEWSTATE": _input_value(page, "__VIEWSTATE"),
                "__VIEWSTATEGENERATOR": _input_value(page, "__VIEWSTATEGENERATOR"),
                "__EVENTVALIDATION": _input_value(page, "__EVENTVALIDATION"),
                "ctl00$MainContent$LoginView$UserName": username,
                "ctl00$MainContent$LoginView$Password": password,
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
        selected = _options(notifications, "MainContent_lstSelectedProjects")
        application_title = ""
        default_url = ""
        host_email = ""
        email_format = ""
        allow_reply_to = False
        default_language = ""
        users = []
        language = self.get("/Administration/Host/Settings.aspx?tid=8")
        if "MainContent_ctlHostSetting_ApplicationDefaultLanguage" in language:
            basic = self.get("/Administration/Host/Settings.aspx?tid=0")
            mail = self.get("/Administration/Host/Settings.aspx?tid=2")
            pop3 = self.get("/Administration/Host/Settings.aspx?tid=7")
            users = _users(self.get("/Administration/Users/UserList.aspx"))
            for match in re.finditer(
                r'<input\b[^>]*name="ctl00\$MainContent\$ctlHostSetting\$SMTPEmailFormat"[^>]*>',
                mail,
            ):
                tag = match.group(0)
                if "checked=" in tag:
                    email_format = re.search(r'value="([^"]*)"', tag).group(1)
            for value, _text, selected_flag in _options(
                language, "MainContent_ctlHostSetting_ApplicationDefaultLanguage"
            ):
                if selected_flag:
                    default_language = value
            application_title = _input_value(basic, "ctl00$MainContent$ctlHostSetting$ApplicationTitle")
            default_url = _input_value(basic, "ctl00$MainContent$ctlHostSetting$DefaultUrl")
            host_email = _input_value(mail, "ctl00$MainContent$ctlHostSetting$HostEmail")
            allow_reply_to = _checked(pop3, "MainContent_ctlHostSetting_POP3AllowReplyTo")
        self._facts = Facts(
            application_title=application_title,
            default_url=default_url,
            host_email=host_email,
            email_format=email_format,
            allow_reply_to=allow_reply_to,
            default_language=default_language,
            preferred_locale=_selected_value(preferences, "MainContent_ddlPreferredLocale"),
            username=_input_value(profile, "ctl00$MainContent$UserName"),
            display_name=_input_value(profile, "ctl00$MainContent$FullName"),
            email=_input_value(profile, "ctl00$MainContent$Email"),
            notifications_on=_checked(notifications, "MainContent_AllowNotifications"),
            subscribed_project_ids=[value for value, _text, _selected in selected],
            users=users,
        )

    @property
    def facts(self):
        if self._facts is None:
            self.login(self._user or "Admin", self._secret)
            self._load_facts()
        return self._facts

    def _profile_view(self, index):
        profile = self.get("/Account/UserProfile.aspx")
        return self._postback(
            "/Account/UserProfile.aspx",
            profile,
            "ctl00$MainContent$BulletedList4",
            str(index),
        )

    def set_preferred_locale(self, culture):
        self._ensure_login()
        preferences = self._profile_view("1")
        current = _selected_value(preferences, "MainContent_ddlPreferredLocale")
        page_size = _selected_value(preferences, "MainContent_IssueListItems")
        data = self._hidden(preferences)
        data["__EVENTTARGET"] = "ctl00$MainContent$SaveCustomSettings"
        data["__EVENTARGUMENT"] = ""
        data["ctl00$MainContent$ddlPreferredLocale"] = culture
        data["ctl00$MainContent$IssueListItems"] = page_size
        status, _location, body = self._request(self.opener, "/Account/UserProfile.aspx", data)
        if status != 200 or "Exception Details" in body:
            raise AssertionError("preferred locale save failed")
        self._facts = None
        return current

    def set_notifications(self, enabled):
        self._ensure_login()
        notes = self._profile_view("2")
        data = self._hidden(notes)
        data["__EVENTTARGET"] = "ctl00$MainContent$LinkButton2"
        data["__EVENTARGUMENT"] = ""
        if enabled:
            data["ctl00$MainContent$AllowNotifications"] = "on"
        status, _location, body = self._request(self.opener, "/Account/UserProfile.aspx", data)
        if status != 200 or "Exception Details" in body:
            raise AssertionError("notification save failed")
        self._facts = None

    def set_subscribed(self, project_id, subscribed):
        self._ensure_login()
        project_id = str(project_id)
        notes = self._profile_view("2")
        selected = [value for value, _text, _flag in _options(notes, "MainContent_lstSelectedProjects")]
        if subscribed and project_id not in selected:
            data = self._hidden(notes)
            data["__EVENTTARGET"] = "ctl00$MainContent$Button1"
            data["__EVENTARGUMENT"] = ""
            data["ctl00$MainContent$lstAllProjects"] = project_id
            status, _location, body = self._request(self.opener, "/Account/UserProfile.aspx", data)
            if status != 200 or project_id not in [
                value for value, _text, _flag in _options(body, "MainContent_lstSelectedProjects")
            ]:
                raise AssertionError("project subscribe failed")
        if not subscribed and project_id in selected:
            data = self._hidden(notes)
            data["__EVENTTARGET"] = "ctl00$MainContent$Button2"
            data["__EVENTARGUMENT"] = ""
            data["ctl00$MainContent$lstSelectedProjects"] = project_id
            status, _location, body = self._request(self.opener, "/Account/UserProfile.aspx", data)
            if status != 200 or project_id in [
                value for value, _text, _flag in _options(body, "MainContent_lstSelectedProjects")
            ]:
                raise AssertionError("project unsubscribe failed")
        self._facts = None

    def set_email_format(self, value):
        self._ensure_login()
        path = "/Administration/Host/Settings.aspx?tid=2"
        page = self.get(path)
        current = ""
        for match in re.finditer(
            r'<input\b[^>]*name="ctl00\$MainContent\$ctlHostSetting\$SMTPEmailFormat"[^>]*>',
            page,
        ):
            tag = match.group(0)
            if "checked=" in tag:
                current = re.search(r'value="([^"]*)"', tag).group(1)
        data = _form_values(page)
        data["ctl00$MainContent$ctlHostSetting$SMTPEmailFormat"] = value
        data["__EVENTTARGET"] = "ctl00$MainContent$cmdUpdate"
        data["__EVENTARGUMENT"] = ""
        status, _location, body = self._request(self.opener, path, data)
        if status != 200 or "Exception Details" in body:
            raise AssertionError("mail format save failed")
        self._facts = None
        return current

    def set_user_registration(self, value):
        self._ensure_login()
        path = "/Administration/Host/Settings.aspx?tid=1"
        page = self.get(path)
        current = ""
        for match in re.finditer(
            r'<input\b[^>]*name="ctl00\$MainContent\$ctlHostSetting\$UserRegistration"[^>]*>',
            page,
        ):
            tag = match.group(0)
            if "checked=" in tag.lower():
                current = re.search(r'value="([^"]*)"', tag).group(1)
        data = _form_values(page)
        data["ctl00$MainContent$ctlHostSetting$UserRegistration"] = value
        data["__EVENTTARGET"] = "ctl00$MainContent$cmdUpdate"
        data["__EVENTARGUMENT"] = ""
        status, _location, body = self._request(self.opener, path, data)
        if status != 200 or "Exception Details" in body:
            raise AssertionError("registration save failed")
        return current

    def register_member(self, subscribe):
        self._ensure_login()
        token = os.urandom(3).hex()
        username = "char" + token
        password = "Bn-" + token + "aA9"
        email = username + "@example.com"
        _remember_secret(password)
        previous = self.set_user_registration("1")
        try:
            session = Host()
            page = session.get("/Account/Register.aspx")
            prefix = "ctl00$MainContent$RegisterUser$CreateUserStepContainer$"
            data = _form_values(page)
            data[prefix + "UserName"] = username
            data[prefix + "Email"] = email
            data[prefix + "FirstName"] = "Char"
            data[prefix + "LastName"] = token
            data[prefix + "DisplayName"] = "Char " + token
            data[prefix + "Password"] = password
            data[prefix + "ConfirmPassword"] = password
            data[prefix + "ctl13"] = "Register"
            status, _location, body = session._request(session.opener, "/Account/Register.aspx", data)
            if status != 200 or "Exception Details" in body:
                snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _redact(body)))[:240]
                raise AssertionError("registration failed " + str(status) + " " + snippet)
            listed = self.get("/Administration/Users/UserList.aspx")
            if username not in listed:
                raise AssertionError("registered user is missing from the user list")
        finally:
            self.set_user_registration(previous)
        self._accounts[username] = password
        member = Host()
        member.login(username, password)
        project_id = self.project_id()
        member.set_notifications(True)
        member.set_subscribed(project_id, subscribe)
        return member

    def release_member(self, member):
        self._ensure_login()
        project_id = self.project_id()
        member.set_subscribed(project_id, False)
        member.set_notifications(False)
        self._accounts.pop(member._user, None)
        self._facts = None

    def people(self):
        self._ensure_login()
        self._facts = None
        admin = self.facts
        accounts = {admin.username: _password()}
        accounts.update(self._accounts)
        found = []
        for row in admin.users:
            password = accounts.get(row.username)
            if password is None:
                continue
            if row.username == admin.username:
                facts = admin
            else:
                session = Host()
                session.login(row.username, password)
                facts = session.facts
            found.append(
                Subscriber(
                    username=row.username,
                    email=facts.email,
                    approved=row.approved,
                    notifications_on=facts.notifications_on,
                    project_ids=tuple(facts.subscribed_project_ids),
                    preferred_locale=facts.preferred_locale,
                    display_name=facts.display_name,
                )
            )
        return found

    def project_id(self):
        if self._project_id is None:
            self.facts
            home = self.get("/Default")
            match = re.search(r"Issues/CreateIssue/(\d+)", home)
            if not match:
                raise AssertionError("no create-issue link on the home page")
            self._project_id = match.group(1)
        return self._project_id

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

    def _matching_mail(self, issue):
        matched = []
        for key in self.list_mail_keys():
            if key in issue.keys_before:
                continue
            message = self._read_mail(key)
            if issue.title in message.body:
                matched.append(message)
        return matched

    def messages_about(self, issue, expected_count=None):
        cached = self._mail.get(issue.issue_id)
        if cached is not None:
            return cached
        deadline = time.time() + MAIL_TIMEOUT_S
        last_keys = None
        found = []
        while time.time() < deadline:
            found = self._matching_mail(issue)
            if expected_count == 0:
                if found:
                    self._mail[issue.issue_id] = found
                    return found
            elif expected_count is not None and len(found) >= expected_count:
                self._mail[issue.issue_id] = found
                return found
            elif expected_count is None and found:
                keys = tuple(message.key for message in found)
                if keys == last_keys:
                    self._mail[issue.issue_id] = found
                    return found
                last_keys = keys
            time.sleep(5)
        if expected_count == 0:
            self._mail[issue.issue_id] = []
            return []
        if found and expected_count is None:
            self._mail[issue.issue_id] = found
            return found
        if expected_count is None:
            raise AssertionError(
                f"no mail whose body contains the posted title within {MAIL_TIMEOUT_S}s"
            )
        raise AssertionError(
            f"mail count {len(found)} did not reach {expected_count} within {MAIL_TIMEOUT_S}s"
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
            vote_count=_vote_total(detail),
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

