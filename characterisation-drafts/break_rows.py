import traceback

from web_create import (
    Mail,
    assert_add_issue_template,
    host,
    issue_added_subject,
    matches_general_short,
    message_recipients,
    render_culture,
)


def _show(label, fn):
    try:
        fn()
    except AssertionError as error:
        print(label + " RED")
        print(str(error).splitlines()[0][:400])
        return False
    except Exception:
        print(label + " RED")
        print(traceback.format_exc().splitlines()[-1][:400])
        return False
    print(label + " GREEN")
    return True


def break_b2():
    admin = host()
    saved = admin.set_preferred_locale("de-DE")
    try:
        issue = admin.create("B2break")
        culture = render_culture(admin.facts.preferred_locale, admin.facts.default_language)

        def wrong_culture():
            matches_general_short(issue.detail_created, "en-US")

        red = _show("B2 broken en-US parser", wrong_culture)
        green = _show(
            "B2 rendered culture",
            lambda: matches_general_short(issue.detail_created, culture),
        )
        return (not red) and green and culture == "de-DE"
    finally:
        admin.set_preferred_locale(saved)


def break_b4():
    admin = host()
    project_id = admin.project_id()
    creator = admin.facts.email.lower()

    def absent(issue, expected):
        if creator in message_recipients(admin.messages_about(issue, expected_count=len(expected))):
            raise AssertionError("checked notify box added the creator")
        if message_recipients(admin.messages_about(issue)) != expected:
            raise AssertionError("recipient set changed")

    issue = admin.create("B4break")
    red = _show("B4 creator already subscribed", lambda: absent(issue, set()))
    was = project_id in admin.facts.subscribed_project_ids
    admin.set_subscribed(project_id, False)
    try:
        quiet = admin.create("B4quiet")

        def restored():
            messages = admin.messages_about(quiet, expected_count=0)
            if creator in message_recipients(messages):
                raise AssertionError("unsubscribed creator was still a recipient")
            if message_recipients(messages):
                raise AssertionError("empty username added a recipient")

        green = _show("B4 unsubscribed creator", restored)
        return (not red) and green
    finally:
        if was:
            admin.set_subscribed(project_id, True)


def break_b5():
    def wrong_subject():
        message = Mail(
            key="",
            sender="",
            to="",
            subject="notice",
            content_type="text/html",
            body="Row B5 subject",
        )
        if "BN-1" not in message.subject:
            raise AssertionError("subject does not name the issue")

    red = _show("B5 wrong subject", wrong_subject)
    issue = host().create("B5break")
    messages = host().messages_about(issue)

    def live():
        if not messages:
            raise AssertionError("no mail arrived")
        for message in messages:
            if issue.full_id not in message.subject:
                raise AssertionError("subject does not name the issue")

    green = _show("B5 live subject", live)
    return (not red) and green


def break_b8():
    admin = host()
    member = admin.register_member(subscribe=True)
    try:
        member.set_notifications(False)
        issue = admin.create("B8break")
        address = member.facts.email.lower()

        def still_expected():
            messages = admin.messages_about(issue, expected_count=1)
            if address not in message_recipients(messages):
                raise AssertionError("notifications-off subscriber was not a recipient")

        red = _show("B8 notifications off", still_expected)
        member.set_notifications(True)
        live = admin.create("B8live")
        expected = {admin.facts.email.lower(), address}

        def restored():
            messages = admin.messages_about(live, expected_count=len(expected))
            if message_recipients(messages) != expected:
                raise AssertionError("subscriber set was not the recipient set")
            if admin.facts.email.lower() not in message_recipients(messages):
                raise AssertionError("creator was removed")

        green = _show("B8 two subscribers", restored)
        return (not red) and green
    finally:
        admin.release_member(member)


def break_b9():
    admin = host()
    saved = admin.set_preferred_locale("de-DE")
    try:
        issue = admin.create("B9break")
        messages = admin.messages_about(issue)
        culture = render_culture(admin.facts.preferred_locale, admin.facts.default_language)
        english = issue_added_subject("en-US").replace("{0}", issue.full_id)
        german = issue_added_subject(culture).replace("{0}", issue.full_id)

        def wrong_pattern():
            for message in messages:
                if message.subject != english:
                    raise AssertionError("subject is not the en-US IssueAddedSubject")

        def right_pattern():
            for message in messages:
                if message.subject != german:
                    raise AssertionError("subject is not the recipient IssueAddedSubject")

        red = _show("B9 en-US pattern", wrong_pattern)
        green = _show("B9 recipient pattern", right_pattern)
        return (not red) and green
    finally:
        admin.set_preferred_locale(saved)


def break_b10():
    admin = host()
    saved = admin.set_email_format("1")
    try:
        issue = admin.create("B10break")
        message = admin.messages_about(issue)[0]

        def html_template():
            assert_add_issue_template(message.body, "2")

        def text_template():
            assert_add_issue_template(message.body, "1")

        red = _show("B10 html template against text body", html_template)
        green = _show("B10 text add-issue template", text_template)
        return (not red) and green
    finally:
        admin.set_email_format(saved)


def break_b16():
    issue = host().create("B16break")

    def zero():
        if issue.vote_count != "0":
            raise AssertionError("stored vote total is " + issue.vote_count)

    def one():
        if issue.vote_count != "1":
            raise AssertionError("stored vote total is " + issue.vote_count)

    red = _show("B16 vote total 0", zero)
    green = _show("B16 vote total 1", one)
    return (not red) and green


def _restore_host(admin, snapshot):
    if admin.facts.preferred_locale != snapshot["locale"]:
        admin.set_preferred_locale(snapshot["locale"])
    if admin.facts.email_format != snapshot["format"]:
        admin.set_email_format(snapshot["format"])
    if admin.facts.notifications_on != snapshot["notifications"]:
        admin.set_notifications(snapshot["notifications"])
    project_id = snapshot["project_id"]
    subscribed = project_id in admin.facts.subscribed_project_ids
    if subscribed != snapshot["subscribed"]:
        admin.set_subscribed(project_id, snapshot["subscribed"])
    registration = admin.set_user_registration(snapshot["registration"])
    if registration != snapshot["registration"]:
        admin.set_user_registration(snapshot["registration"])


def main():
    admin = host()
    project_id = admin.project_id()
    registration = admin.set_user_registration("0")
    if registration != "0":
        admin.set_user_registration(registration)
    snapshot = {
        "locale": admin.facts.preferred_locale,
        "format": admin.facts.email_format,
        "notifications": admin.facts.notifications_on,
        "subscribed": project_id in admin.facts.subscribed_project_ids,
        "project_id": project_id,
        "registration": registration,
    }
    checks = [
        ("B2", break_b2),
        ("B4", break_b4),
        ("B5", break_b5),
        ("B8", break_b8),
        ("B9", break_b9),
        ("B10", break_b10),
        ("B16", break_b16),
    ]
    failed = []
    try:
        for name, fn in checks:
            print("---", name)
            try:
                if not fn():
                    failed.append(name)
            except Exception:
                failed.append(name)
                print(name, "ERROR")
                print(traceback.format_exc()[-800:])
    finally:
        _restore_host(admin, snapshot)
        print(
            "host",
            admin.facts.preferred_locale,
            admin.facts.email_format,
            "notifications",
            admin.facts.notifications_on,
            "subscribed",
            project_id in admin.facts.subscribed_project_ids,
        )
    print("break failed:", ", ".join(failed) if failed else "none")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
