using System.Globalization;
using System.Security.Claims;
using BugNet.Core;
using BugNet.Data;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace BugNet.Web.Pages;

[AllowAnonymous]
[IgnoreAntiforgeryToken]
public sealed class LoginModel : PageModel
{
    private readonly IssueDatabase _database;

    public LoginModel(IssueDatabase database)
    {
        _database = database;
    }

    public IActionResult OnGet() => Content(Markup.Login(), "text/html; charset=utf-8");

    public async Task<IActionResult> OnPost()
    {
        var name = Request.Form["ctl00$MainContent$LoginView$UserName"].ToString();
        var password = Request.Form["ctl00$MainContent$LoginView$Password"].ToString();
        if (!await _database.PasswordMatchesAsync(name, password, HttpContext.RequestAborted).ConfigureAwait(false))
        {
            return Redirect("/Account/Login.aspx");
        }

        var identity = new ClaimsIdentity(
            [new Claim(ClaimTypes.Name, name)],
            CookieAuthenticationDefaults.AuthenticationScheme);
        await HttpContext.SignInAsync(
            CookieAuthenticationDefaults.AuthenticationScheme,
            new ClaimsPrincipal(identity)).ConfigureAwait(false);
        return Redirect("/Default");
    }
}

[IgnoreAntiforgeryToken]
public sealed class UserProfileModel : PageModel
{
    private readonly IssueDatabase _database;

    public UserProfileModel(IssueDatabase database)
    {
        _database = database;
    }

    public async Task<IActionResult> OnGet()
    {
        var profile = await _database.ReadProfileAsync(Name(), HttpContext.RequestAborted).ConfigureAwait(false);
        return Html(Markup.Profile(profile, "details"));
    }

    public async Task<IActionResult> OnPost()
    {
        var name = Name();
        var target = Request.Form["__EVENTTARGET"].ToString();
        var argument = Request.Form["__EVENTARGUMENT"].ToString();
        var token = HttpContext.RequestAborted;
        if (target == "ctl00$MainContent$SaveCustomSettings")
        {
            var locale = Request.Form["ctl00$MainContent$ddlPreferredLocale"].ToString();
            var pageSize = int.TryParse(Request.Form["ctl00$MainContent$IssueListItems"], NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed)
                ? parsed
                : 10;
            await _database.SaveLocaleAsync(name, locale, pageSize, token).ConfigureAwait(false);
            return Html(Markup.Profile(await _database.ReadProfileAsync(name, token).ConfigureAwait(false), "preferences"));
        }

        if (target == "ctl00$MainContent$LinkButton2")
        {
            var enabled = Request.Form["ctl00$MainContent$AllowNotifications"].Count > 0;
            await _database.SaveNotificationsAsync(name, enabled, token).ConfigureAwait(false);
            return Html(Markup.Profile(await _database.ReadProfileAsync(name, token).ConfigureAwait(false), "notifications"));
        }

        if (target is "ctl00$MainContent$Button1" or "ctl00$MainContent$Button2")
        {
            var field = target.EndsWith("Button1", StringComparison.Ordinal)
                ? "ctl00$MainContent$lstAllProjects"
                : "ctl00$MainContent$lstSelectedProjects";
            if (int.TryParse(Request.Form[field], NumberStyles.Integer, CultureInfo.InvariantCulture, out var projectId))
            {
                await _database.SetSubscribedAsync(name, projectId, target.EndsWith("Button1", StringComparison.Ordinal), token).ConfigureAwait(false);
            }

            return Html(Markup.Profile(await _database.ReadProfileAsync(name, token).ConfigureAwait(false), "notifications"));
        }

        var tab = target == "ctl00$MainContent$BulletedList4" && argument == "1"
            ? "preferences"
            : target == "ctl00$MainContent$BulletedList4" && argument == "2"
                ? "notifications"
                : "details";
        return Html(Markup.Profile(await _database.ReadProfileAsync(name, token).ConfigureAwait(false), tab));
    }

    private string Name() => User.Identity?.Name ?? "";

    private ContentResult Html(string html) => Content(html, "text/html; charset=utf-8");
}

[AllowAnonymous]
[IgnoreAntiforgeryToken]
public sealed class RegisterModel : PageModel
{
    private readonly IssueDatabase _database;

    public RegisterModel(IssueDatabase database)
    {
        _database = database;
    }

    public IActionResult OnGet() => Content(Markup.Register(), "text/html; charset=utf-8");

    public async Task<IActionResult> OnPost()
    {
        const string prefix = "ctl00$MainContent$RegisterUser$CreateUserStepContainer$";
        var member = new NewMember(
            Request.Form[prefix + "UserName"].ToString(),
            Request.Form[prefix + "Password"].ToString(),
            Request.Form[prefix + "Email"].ToString(),
            Request.Form[prefix + "FirstName"].ToString(),
            Request.Form[prefix + "LastName"].ToString(),
            Request.Form[prefix + "DisplayName"].ToString());
        await _database.RegisterAsync(member, HttpContext.RequestAborted).ConfigureAwait(false);
        return Content(Markup.Register(), "text/html; charset=utf-8");
    }
}

[IgnoreAntiforgeryToken]
public sealed class HostSettingsModel : PageModel
{
    private static readonly Dictionary<string, string> PostedKeys = new(StringComparer.Ordinal)
    {
        ["ctl00$MainContent$ctlHostSetting$ApplicationTitle"] = "ApplicationTitle",
        ["ctl00$MainContent$ctlHostSetting$DefaultUrl"] = "DefaultUrl",
        ["ctl00$MainContent$ctlHostSetting$HostEmail"] = "HostEmailAddress",
        ["ctl00$MainContent$ctlHostSetting$SMTPEmailFormat"] = "SMTPEMailFormat",
        ["ctl00$MainContent$ctlHostSetting$ApplicationDefaultLanguage"] = "ApplicationDefaultLanguage",
        ["ctl00$MainContent$ctlHostSetting$UserRegistration"] = "UserRegistration",
    };

    private readonly IssueDatabase _database;

    public HostSettingsModel(IssueDatabase database)
    {
        _database = database;
    }

    public Task<IActionResult> OnGet() => Render(Tid());

    public async Task<IActionResult> OnPost()
    {
        var tid = Tid();
        var token = HttpContext.RequestAborted;
        foreach (var pair in PostedKeys)
        {
            if (Request.Form.ContainsKey(pair.Key))
            {
                await _database.SetSettingAsync(pair.Value, Request.Form[pair.Key].ToString(), token).ConfigureAwait(false);
            }
        }

        if (tid == "7")
        {
            var on = Request.Form.ContainsKey("ctl00$MainContent$ctlHostSetting$POP3AllowReplyTo");
            await _database.SetSettingAsync("Pop3AllowReplyToEmail", on ? "True" : "False", token).ConfigureAwait(false);
        }

        return await Render(tid).ConfigureAwait(false);
    }

    private async Task<IActionResult> Render(string tid)
    {
        var names = new[]
        {
            "ApplicationTitle",
            "DefaultUrl",
            "HostEmailAddress",
            "SMTPEMailFormat",
            "ApplicationDefaultLanguage",
            "UserRegistration",
            "Pop3AllowReplyToEmail",
        };
        var settings = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var name in names)
        {
            settings[name] = await _database.ReadSettingAsync(name, HttpContext.RequestAborted).ConfigureAwait(false);
        }

        return Content(Markup.Settings(tid, settings), "text/html; charset=utf-8");
    }

    private string Tid() => Request.Query["tid"].ToString();
}

[IgnoreAntiforgeryToken]
public sealed class UserListModel : PageModel
{
    private readonly IssueDatabase _database;

    public UserListModel(IssueDatabase database)
    {
        _database = database;
    }

    public async Task<IActionResult> OnGet()
    {
        var members = await _database.ListMembersAsync(HttpContext.RequestAborted).ConfigureAwait(false);
        return Content(Markup.UserList(members), "text/html; charset=utf-8");
    }
}

[IgnoreAntiforgeryToken]
public sealed class HomeModel : PageModel
{
    private readonly IssueDatabase _database;

    public HomeModel(IssueDatabase database)
    {
        _database = database;
    }

    public async Task<IActionResult> OnGet()
    {
        var project = await _database.FirstOpenProjectAsync(HttpContext.RequestAborted).ConfigureAwait(false)
            ?? throw new InvalidOperationException("no open project");
        return Content(Markup.Home(project), "text/html; charset=utf-8");
    }
}

[IgnoreAntiforgeryToken]
public sealed class CreateIssueModel : PageModel
{
    private readonly IssueDatabase _database;
    private readonly IAddSender _sender;

    public CreateIssueModel(IssueDatabase database, IAddSender sender)
    {
        _database = database;
        _sender = sender;
    }

    public async Task<IActionResult> OnGet(int projectId)
    {
        var page = await _database.ReadCreatePageAsync(projectId, HttpContext.RequestAborted).ConfigureAwait(false);
        if (page is null)
        {
            return NotFound();
        }

        return Content(Markup.Create(page), "text/html; charset=utf-8");
    }

    public async Task<IActionResult> OnPost(int projectId)
    {
        var token = HttpContext.RequestAborted;
        var command = new CreateIssue(
            projectId,
            Request.Form["ctl00$MainContent$TitleTextBox"].ToString(),
            Request.Form["ctl00$MainContent$DescriptionHtmlEditor$DescriptionHtmlEditor"].ToString(),
            Int("ctl00$MainContent$DropStatus$dropStatus"),
            Int("ctl00$MainContent$DropResolution$ddlResolution"),
            Int("ctl00$MainContent$DropPriority$ddlPriority"),
            Int("ctl00$MainContent$DropIssueType$ddlType"),
            Request.Form["ctl00$MainContent$DropOwned$ddlUsers"].ToString(),
            Request.Form["ctl00$MainContent$DropAssignedTo$ddlUsers"].ToString(),
            Request.Form.ContainsKey("ctl00$MainContent$chkNotifyOwner"),
            Request.Form.ContainsKey("ctl00$MainContent$chkNotifyAssignedTo"),
            Int("ctl00$MainContent$DropMilestone$ddlMilestone"),
            Int("ctl00$MainContent$DropCategory$ddlComps"),
            Int("ctl00$MainContent$DropAffectedMilestone$ddlMilestone"),
            When("ctl00$MainContent$DueDatePicker$DateTextBox"),
            Amount("ctl00$MainContent$txtEstimation"),
            Int("ctl00$MainContent$ProgressSlider"),
            User.Identity?.Name ?? "");
        var settings = await _database.ReadMailSettingsAsync(token).ConfigureAwait(false);
        var created = await IssueCreation.CreateAsync(command, _database, settings, _sender, token).ConfigureAwait(false);
        return Redirect("/Issues/IssueDetail.aspx?id=" + created.Id.ToString(CultureInfo.InvariantCulture));
    }

    private int Int(string name)
    {
        return int.TryParse(Request.Form[name], NumberStyles.Integer, CultureInfo.InvariantCulture, out var value) ? value : 0;
    }

    private DateTime? When(string name)
    {
        var text = Request.Form[name].ToString();
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        return DateTime.TryParse(text, CultureInfo.InvariantCulture, DateTimeStyles.None, out var value) ? value : null;
    }

    private decimal? Amount(string name)
    {
        var text = Request.Form[name].ToString();
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        return decimal.TryParse(text, NumberStyles.Number, CultureInfo.InvariantCulture, out var value) ? value : null;
    }
}

[IgnoreAntiforgeryToken]
public sealed class IssueDetailModel : PageModel
{
    private readonly IssueDatabase _database;

    public IssueDetailModel(IssueDatabase database)
    {
        _database = database;
    }

    public async Task<IActionResult> OnGet()
    {
        if (!int.TryParse(Request.Query["id"], NumberStyles.Integer, CultureInfo.InvariantCulture, out var id))
        {
            return NotFound();
        }

        var token = HttpContext.RequestAborted;
        var issue = await _database.ReadDetailAsync(id, token).ConfigureAwait(false);
        if (issue is null)
        {
            return NotFound();
        }

        var locale = await _database.PreferredLocaleAsync(User.Identity?.Name ?? "", token).ConfigureAwait(false);
        return Content(Markup.Detail(issue, locale), "text/html; charset=utf-8");
    }
}
