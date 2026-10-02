import traceback

from web_create import (
    add_issue_template,
    assert_add_issue_template,
    assert_creator_vote,
    host,
    issue_added_subject,
    matches_general_short,
    message_culture,
    message_recipients,
    render_culture,
    subject_names_issue,
    template_fields,
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
    def prefix():
        subject_names_issue(
            "Issue BN-10 has been added to a project you are monitoring.",
            "BN-1",
        )

    red = _show("B5 BN-10 subject", prefix)
    issue = host().create("B5break")
    messages = host().messages_about(issue)

    def live():
        if not messages:
            raise AssertionError("no mail arrived")
        for message in messages:
            subject_names_issue(message.subject, issue.full_id)

    green = _show("B5 exact issue key", live)
    return (not red) and green


def break_b8():
    def prefix():
        subject_names_issue(
            "Issue BN-10 has been added to a project you are monitoring.",
            "BN-1",
        )

    red = _show("B8 BN-10 subject", prefix)
    admin = host()
    member = admin.register_member(subscribe=True)
    try:
        issue = admin.create("B8live")
        address = member.facts.email.lower()
        expected = {admin.facts.email.lower(), address}

        def restored():
            messages = admin.messages_about(issue, expected_count=len(expected))
            if message_recipients(messages) != expected:
                raise AssertionError("subscriber set was not the recipient set")
            if admin.facts.email.lower() not in message_recipients(messages):
                raise AssertionError("creator was removed")
            for message in messages:
                subject_names_issue(message.subject, issue.full_id)

        green = _show("B8 exact issue key", restored)
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


def _localized_message(admin, row_id):
    issue = admin.create(row_id)
    message = admin.messages_about(issue)[0]
    culture = message_culture(message, admin.people(), admin.facts.default_language)
    return issue, message, culture


def break_b10():
    admin = host()
    saved = admin.set_preferred_locale("nl-NL")
    try:
        _issue, message, culture = _localized_message(admin, "B10break")
        mail_format = admin.facts.email_format

        def english_template():
            assert_add_issue_template(message.body, mail_format, "en-US")

        def dutch_template():
            if culture != "nl-NL":
                raise AssertionError("recipient culture is " + culture)
            assert_add_issue_template(message.body, mail_format, culture)

        red = _show("B10 English template for nl-NL", english_template)
        green = _show("B10 nl-NL add-issue template", dutch_template)
        return (not red) and green
    finally:
        admin.set_preferred_locale(saved)


def break_b11():
    admin = host()
    saved = admin.set_preferred_locale("nl-NL")
    try:
        issue, message, culture = _localized_message(admin, "B11break")
        mail_format = admin.facts.email_format
        english = list(add_issue_template("en-US").labels)
        dutch = list(add_issue_template(culture).labels)

        def english_labels():
            fields = template_fields(message.body, "en-US", mail_format)
            if list(fields) != english:
                raise AssertionError("fields are not the English labels")

        def dutch_labels():
            if culture != "nl-NL":
                raise AssertionError("recipient culture is " + culture)
            fields = template_fields(message.body, culture, mail_format)
            if list(fields) != dutch:
                raise AssertionError("fields are not the nl-NL labels")
            if fields[dutch[0]] != issue.title:
                raise AssertionError("title field mismatch")

        red = _show("B11 English labels for nl-NL", english_labels)
        green = _show("B11 nl-NL field labels", dutch_labels)
        return (not red) and green
    finally:
        admin.set_preferred_locale(saved)


def break_b12():
    admin = host()
    saved = admin.set_preferred_locale("nl-NL")
    try:
        issue, message, culture = _localized_message(admin, "B12break")
        mail_format = admin.facts.email_format

        def english_unassigned():
            fields = template_fields(message.body, "en-US", mail_format)
            if fields.get("Milestone") != "Unassigned" or fields.get("Category") != "Unassigned":
                raise AssertionError("English Milestone and Category are not both Unassigned")

        def dutch_unassigned():
            if culture != "nl-NL":
                raise AssertionError("recipient culture is " + culture)
            labels = add_issue_template(culture).labels
            fields = template_fields(message.body, culture, mail_format)
            if fields[labels[3]] != "Unassigned" or fields[labels[4]] != "Unassigned":
                raise AssertionError("localized milestone or category is not Unassigned")
            if fields[labels[5]] != issue.priority_name or fields[labels[6]] != issue.type_name:
                raise AssertionError("priority or type name mismatch")

        red = _show("B12 English labels for nl-NL", english_unassigned)
        green = _show("B12 nl-NL Unassigned", dutch_unassigned)
        return (not red) and green
    finally:
        admin.set_preferred_locale(saved)


def break_b16():
    admin = host()
    member = admin.register_member(subscribe=False)
    try:
        issue = admin.create("B16break")
        other = member.get("/Issues/IssueDetail.aspx?id=" + str(issue.issue_id))

        def non_creator():
            assert_creator_vote(other)

        def creator():
            assert_creator_vote(issue.detail_html)

        red = _show("B16 non-creator vote", non_creator)
        green = _show("B16 creator vote", creator)
        return (not red) and green
    finally:
        admin.release_member(member)


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
        ("B11", break_b11),
        ("B12", break_b12),
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
