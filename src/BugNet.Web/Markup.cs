using System.Globalization;
using System.Net;
using System.Text;
using BugNet.Core;
using BugNet.Data;

namespace BugNet.Web;

internal static class Markup
{
    private static readonly string[] Locales = ["", "en-US", "de-DE", "es-ES", "fr-CA", "it-IT", "nl-NL", "ro-RO", "ru-RU", "zh-CN"];
    private static readonly int[] PageSizes = [5, 10, 15, 20, 25, 50];

    public static string Login() => Page("<h1>Sign in</h1>");

    public static string Profile(ProfileEditor profile, string tab)
    {
        var body = new StringBuilder();
        if (tab == "preferences")
        {
            Select(body, "MainContent_ddlPreferredLocale", "ctl00$MainContent$ddlPreferredLocale", LocaleOptions(profile.PreferredLocale));
            Select(body, "MainContent_IssueListItems", "ctl00$MainContent$IssueListItems", PageSizeOptions(profile.IssuesPageSize));
        }
        else if (tab == "notifications")
        {
            body.Append("<input type=\"checkbox\" id=\"MainContent_AllowNotifications\" name=\"ctl00$MainContent$AllowNotifications\" value=\"on\"");
            if (profile.ReceiveEmailNotifications)
            {
                body.Append(" checked=\"checked\"");
            }

            body.Append(" />");
            Select(body, "MainContent_lstSelectedProjects", "ctl00$MainContent$lstSelectedProjects", ProjectOptions(profile.SubscribedProjects));
            Select(body, "MainContent_lstAllProjects", "ctl00$MainContent$lstAllProjects", ProjectOptions(profile.OtherProjects));
        }
        else
        {
            Text(body, "ctl00$MainContent$UserName", profile.UserName);
            Text(body, "ctl00$MainContent$FullName", profile.DisplayName);
            Text(body, "ctl00$MainContent$Email", profile.Email);
        }

        return Page(body.ToString());
    }

    public static string Register() => Page("<h1>Register</h1>");

    public static string Settings(string tid, IReadOnlyDictionary<string, string> settings)
    {
        var body = new StringBuilder();
        if (tid == "8")
        {
            Select(
                body,
                "MainContent_ctlHostSetting_ApplicationDefaultLanguage",
                "ctl00$MainContent$ctlHostSetting$ApplicationDefaultLanguage",
                LocaleOptions(settings.GetValueOrDefault("ApplicationDefaultLanguage") ?? ""));
        }
        else if (tid == "0")
        {
            Text(body, "ctl00$MainContent$ctlHostSetting$ApplicationTitle", settings.GetValueOrDefault("ApplicationTitle") ?? "");
            Text(body, "ctl00$MainContent$ctlHostSetting$DefaultUrl", settings.GetValueOrDefault("DefaultUrl") ?? "");
        }
        else if (tid == "2")
        {
            Text(body, "ctl00$MainContent$ctlHostSetting$HostEmail", settings.GetValueOrDefault("HostEmailAddress") ?? "");
            var format = settings.GetValueOrDefault("SMTPEMailFormat") ?? "2";
            Radio(body, "ctl00$MainContent$ctlHostSetting$SMTPEmailFormat", "1", format == "1");
            Radio(body, "ctl00$MainContent$ctlHostSetting$SMTPEmailFormat", "2", format == "2");
        }
        else if (tid == "7")
        {
            var on = string.Equals(settings.GetValueOrDefault("Pop3AllowReplyToEmail"), "True", StringComparison.OrdinalIgnoreCase);
            body.Append("<input type=\"checkbox\" id=\"MainContent_ctlHostSetting_POP3AllowReplyTo\" name=\"ctl00$MainContent$ctlHostSetting$POP3AllowReplyTo\" value=\"on\"");
            if (on)
            {
                body.Append(" checked=\"checked\"");
            }

            body.Append(" />");
        }
        else if (tid == "1")
        {
            var current = settings.GetValueOrDefault("UserRegistration") ?? "0";
            foreach (var value in new[] { "0", "1", "2", "3" })
            {
                Radio(body, "ctl00$MainContent$ctlHostSetting$UserRegistration", value, current == value);
            }
        }

        return Page(body.ToString());
    }

    public static string UserList(IReadOnlyList<MemberAccount> members)
    {
        var body = new StringBuilder("<table>");
        foreach (var member in members)
        {
            body.Append("<tr><td></td><td>")
                .Append(WebUtility.HtmlEncode(member.UserName))
                .Append("</td><td>")
                .Append(WebUtility.HtmlEncode(member.Email))
                .Append("</td><td>");
            if (member.Approved)
            {
                body.Append("<input type=\"checkbox\" checked=\"checked\" />");
            }

            body.Append("</td></tr>");
        }

        body.Append("</table>");
        return Page(body.ToString());
    }

    public static string Home(ProjectChoice project)
    {
        return Page("<a href=\"Issues/CreateIssue/" + project.Id.ToString(CultureInfo.InvariantCulture) + "\">Create issue</a>");
    }

    public static string Create(CreatePageData page)
    {
        var body = new StringBuilder();
        body.Append("<small>")
            .Append(WebUtility.HtmlEncode(page.Project.Name))
            .Append(" <span>(")
            .Append(WebUtility.HtmlEncode(page.Project.Code))
            .Append(")</span></small>");
        Choices(body, "MainContent_DropStatus_dropStatus", "ctl00$MainContent$DropStatus$dropStatus", page.Statuses, null);
        Choices(body, "MainContent_DropResolution_ddlResolution", "ctl00$MainContent$DropResolution$ddlResolution", page.Resolutions, null);
        Choices(body, "MainContent_DropPriority_ddlPriority", "ctl00$MainContent$DropPriority$ddlPriority", page.Priorities, null);
        Choices(body, "MainContent_DropIssueType_ddlType", "ctl00$MainContent$DropIssueType$ddlType", page.Types, null);
        return Page(body.ToString());
    }

    public static string Detail(DetailPageData issue, string? preferredLocale)
    {
        var body = new StringBuilder();
        Span(body, "MainContent_lblIssueNumber", IssueCreation.IssueKey(issue.ProjectCode, issue.Id));
        Span(body, "MainContent_DisplayTitleLabel", issue.Title);
        Span(body, "MainContent_lblReporter", issue.CreatorDisplayName);
        Span(body, "MainContent_lblDateCreated", CreatedOnText.Format(issue.DateCreated, preferredLocale));
        Choices(body, "MainContent_DropStatus_dropStatus", "ctl00$MainContent$DropStatus$dropStatus", issue.Statuses, issue.StatusId);
        Choices(body, "MainContent_DropResolution_ddlResolution", "ctl00$MainContent$DropResolution$ddlResolution", issue.Resolutions, issue.ResolutionId);
        EmptyUser(body, "MainContent_DropOwned_ddlUsers");
        EmptyUser(body, "MainContent_DropAssignedTo_ddlUsers");
        body.Append("<span class=\"count\">")
            .Append(issue.VoteCount.ToString(CultureInfo.InvariantCulture))
            .Append("</span><span id=\"MainContent_VotedLabel\">Voted</span>");
        return Page(body.ToString());
    }

    private static string Page(string body) => "<!DOCTYPE html><html><body>" + body + "</body></html>";

    private static void Text(StringBuilder body, string name, string value)
    {
        body.Append("<input name=\"").Append(name).Append("\" value=\"").Append(WebUtility.HtmlEncode(value)).Append("\" />");
    }

    private static void Radio(StringBuilder body, string name, string value, bool selected)
    {
        body.Append("<input type=\"radio\" name=\"").Append(name).Append("\" value=\"").Append(value).Append('"');
        if (selected)
        {
            body.Append(" checked=\"checked\"");
        }

        body.Append(" />");
    }

    private static void Span(StringBuilder body, string id, string text)
    {
        body.Append("<span id=\"").Append(id).Append("\">").Append(WebUtility.HtmlEncode(text)).Append("</span>");
    }

    private static void EmptyUser(StringBuilder body, string id)
    {
        body.Append("<select id=\"").Append(id).Append("\"><option value=\"\" selected=\"selected\"></option></select>");
    }

    private static void Choices(StringBuilder body, string id, string name, IReadOnlyList<LookupChoice> choices, int? selected)
    {
        var options = new List<(string Value, string Text, bool Selected)>();
        foreach (var choice in choices)
        {
            options.Add((choice.Id.ToString(CultureInfo.InvariantCulture), choice.Name, selected == choice.Id));
        }

        Select(body, id, name, options);
    }

    private static void Select(StringBuilder body, string id, string name, List<(string Value, string Text, bool Selected)> options)
    {
        body.Append("<select id=\"").Append(id).Append("\" name=\"").Append(name).Append("\">");
        foreach (var option in options)
        {
            body.Append("<option value=\"").Append(WebUtility.HtmlEncode(option.Value)).Append('"');
            if (option.Selected)
            {
                body.Append(" selected=\"selected\"");
            }

            body.Append('>').Append(WebUtility.HtmlEncode(option.Text)).Append("</option>");
        }

        body.Append("</select>");
    }

    private static List<(string Value, string Text, bool Selected)> LocaleOptions(string selected)
    {
        var values = Locales.Contains(selected, StringComparer.Ordinal) ? Locales : Locales.Append(selected).ToArray();
        return values.Select(value => (value, value.Length == 0 ? "(default)" : value, value == selected)).ToList();
    }

    private static List<(string Value, string Text, bool Selected)> PageSizeOptions(int selected)
    {
        var values = PageSizes.Contains(selected) ? PageSizes : PageSizes.Append(selected).ToArray();
        return values.Select(value => (value.ToString(CultureInfo.InvariantCulture), value.ToString(CultureInfo.InvariantCulture), value == selected)).ToList();
    }

    private static List<(string Value, string Text, bool Selected)> ProjectOptions(IReadOnlyList<ProjectChoice> projects)
    {
        return projects
            .Select(project => (project.Id.ToString(CultureInfo.InvariantCulture), project.Name, false))
            .ToList();
    }
}
