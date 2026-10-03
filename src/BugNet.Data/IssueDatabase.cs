using BugNet.Core;
using BugNet.Data.Persistence;
using Microsoft.EntityFrameworkCore;

namespace BugNet.Data;

public sealed class IssueDatabase : IIssueStore
{
    private static readonly DateTime Never = new(1754, 1, 1, 0, 0, 0, DateTimeKind.Unspecified);

    private readonly string _connectionString;

    private IssueDatabase(string connectionString)
    {
        _connectionString = connectionString;
    }

    public static IssueDatabase Open(string connectionString)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(connectionString);
        return new IssueDatabase(connectionString);
    }

    public async Task<SavedIssue> SaveAsync(
        CreateIssue command,
        IReadOnlyList<string> notificationUserNames,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);
        ArgumentNullException.ThrowIfNull(notificationUserNames);
        await using var db = New();
        await using var tx = await db.Database.BeginTransactionAsync(cancellationToken).ConfigureAwait(false);
        var creator = await db.Users.SingleOrDefaultAsync(row => row.UserName == command.CreatorUserName, cancellationToken).ConfigureAwait(false)
            ?? throw new InvalidOperationException("creator is not a user");
        var issue = new IssueRow
        {
            IssueTitle = command.Title,
            IssueDescription = command.Description,
            IssueStatusId = NullIfZero(command.StatusId),
            IssuePriorityId = NullIfZero(command.PriorityId),
            IssueTypeId = NullIfZero(command.TypeId),
            IssueCategoryId = NullIfZero(command.CategoryId),
            ProjectId = command.ProjectId,
            IssueAffectedMilestoneId = NullIfZero(command.AffectedMilestoneId),
            IssueResolutionId = NullIfZero(command.ResolutionId),
            IssueCreatorUserId = creator.UserId,
            IssueAssignedUserId = await UserIdOrNullAsync(db, command.AssigneeUserName, cancellationToken).ConfigureAwait(false),
            IssueOwnerUserId = await UserIdOrNullAsync(db, command.OwnerUserName, cancellationToken).ConfigureAwait(false),
            IssueDueDate = command.DueDate,
            IssueMilestoneId = NullIfZero(command.MilestoneId),
            IssueVisibility = 0,
            IssueEstimation = command.Estimation ?? 0,
            IssueProgress = command.Progress,
            LastUpdate = DateTime.Now,
            LastUpdateUserId = creator.UserId,
        };
        db.Issues.Add(issue);
        await db.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
        db.Votes.Add(new VoteRow
        {
            IssueId = issue.IssueId,
            UserId = creator.UserId,
            DateCreated = issue.DateCreated,
        });
        await db.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
        foreach (var name in notificationUserNames)
        {
            var userId = await UserIdOrNullAsync(db, name, cancellationToken).ConfigureAwait(false);
            if (userId is null)
            {
                continue;
            }

            var exists = await db.IssueNotifications.AnyAsync(
                row => row.IssueId == issue.IssueId && row.UserId == userId.Value,
                cancellationToken).ConfigureAwait(false);
            if (exists)
            {
                continue;
            }

            db.IssueNotifications.Add(new IssueNotificationRow
            {
                IssueId = issue.IssueId,
                UserId = userId.Value,
            });
        }

        await db.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
        var saved = await ReadSavedAsync(db, issue.IssueId, cancellationToken).ConfigureAwait(false);
        await tx.CommitAsync(cancellationToken).ConfigureAwait(false);
        return saved;
    }

    public async Task<HostMailSettings> ReadMailSettingsAsync(CancellationToken cancellationToken)
    {
        await using var db = New();
        var rows = await db.HostSettings.ToListAsync(cancellationToken).ConfigureAwait(false);
        var settings = rows.ToDictionary(row => row.SettingName, row => row.SettingValue ?? "", StringComparer.Ordinal);
        return new HostMailSettings(
            Required(settings, "ApplicationTitle"),
            Required(settings, "HostEmailAddress"),
            IsTrue(settings.GetValueOrDefault("Pop3AllowReplyToEmail")),
            Required(settings, "SMTPEMailFormat"),
            Required(settings, "DefaultUrl"),
            Required(settings, "ApplicationDefaultLanguage"));
    }

    public async Task<string> ReadSettingAsync(string name, CancellationToken cancellationToken)
    {
        await using var db = New();
        var row = await db.HostSettings.SingleOrDefaultAsync(item => item.SettingName == name, cancellationToken).ConfigureAwait(false);
        return row?.SettingValue ?? "";
    }

    public async Task SetSettingAsync(string name, string value, CancellationToken cancellationToken)
    {
        await using var db = New();
        var row = await db.HostSettings.SingleOrDefaultAsync(item => item.SettingName == name, cancellationToken).ConfigureAwait(false);
        if (row is null)
        {
            db.HostSettings.Add(new HostSettingRow { SettingName = name, SettingValue = value });
        }
        else
        {
            row.SettingValue = value;
        }

        await db.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
    }

    public async Task<bool> PasswordMatchesAsync(string userName, string password, CancellationToken cancellationToken)
    {
        await using var db = New();
        var user = await db.Users.SingleOrDefaultAsync(row => row.UserName == userName, cancellationToken).ConfigureAwait(false);
        if (user is null)
        {
            return false;
        }

        var membership = await db.Memberships.SingleOrDefaultAsync(row => row.UserId == user.UserId, cancellationToken).ConfigureAwait(false);
        if (membership is null || !membership.IsApproved || membership.IsLockedOut)
        {
            return false;
        }

        return MembershipPassword.Matches(password, membership.PasswordSalt, membership.Password, membership.PasswordFormat);
    }

    public async Task<ProfileEditor> ReadProfileAsync(string userName, CancellationToken cancellationToken)
    {
        await using var db = New();
        var user = await db.Users.SingleAsync(row => row.UserName == userName, cancellationToken).ConfigureAwait(false);
        var membership = await db.Memberships.SingleAsync(row => row.UserId == user.UserId, cancellationToken).ConfigureAwait(false);
        var profile = await db.Profiles.SingleOrDefaultAsync(row => row.UserName == user.UserName, cancellationToken).ConfigureAwait(false);
        var projects = await OpenProjectsAsync(db, cancellationToken).ConfigureAwait(false);
        var subscribedIds = await db.ProjectNotifications
            .Where(row => row.UserId == user.UserId)
            .Select(row => row.ProjectId)
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
        var subscribed = projects.Where(project => subscribedIds.Contains(project.Id)).ToList();
        var others = projects.Where(project => !subscribedIds.Contains(project.Id)).ToList();
        return new ProfileEditor(
            user.UserName,
            profile?.DisplayName ?? "",
            membership.Email ?? "",
            profile?.PreferredLocale ?? "",
            profile?.IssuesPageSize ?? 10,
            profile?.ReceiveEmailNotifications ?? false,
            subscribed,
            others);
    }

    public async Task SaveLocaleAsync(string userName, string preferredLocale, int issuesPageSize, CancellationToken cancellationToken)
    {
        await using var db = New();
        var profile = await RequireProfileAsync(db, userName, cancellationToken).ConfigureAwait(false);
        profile.PreferredLocale = preferredLocale;
        profile.IssuesPageSize = issuesPageSize;
        profile.LastUpdate = DateTime.Now;
        await db.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
    }

    public async Task SaveNotificationsAsync(string userName, bool enabled, CancellationToken cancellationToken)
    {
        await using var db = New();
        var profile = await RequireProfileAsync(db, userName, cancellationToken).ConfigureAwait(false);
        profile.ReceiveEmailNotifications = enabled;
        profile.LastUpdate = DateTime.Now;
        await db.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
    }

    public async Task SetSubscribedAsync(string userName, int projectId, bool subscribed, CancellationToken cancellationToken)
    {
        await using var db = New();
        var user = await db.Users.SingleAsync(row => row.UserName == userName, cancellationToken).ConfigureAwait(false);
        var existing = await db.ProjectNotifications.SingleOrDefaultAsync(
            row => row.UserId == user.UserId && row.ProjectId == projectId,
            cancellationToken).ConfigureAwait(false);
        if (subscribed && existing is null)
        {
            db.ProjectNotifications.Add(new ProjectNotificationRow { ProjectId = projectId, UserId = user.UserId });
        }

        if (!subscribed && existing is not null)
        {
            db.ProjectNotifications.Remove(existing);
        }

        await db.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
    }

    public async Task<IReadOnlyList<MemberAccount>> ListMembersAsync(CancellationToken cancellationToken)
    {
        await using var db = New();
        var rows = await (
            from user in db.Users
            join membership in db.Memberships on user.UserId equals membership.UserId
            orderby user.UserName
            select new MemberAccount(user.UserName, membership.Email ?? "", membership.IsApproved))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
        return rows;
    }

    public async Task RegisterAsync(NewMember member, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(member);
        await using var db = New();
        var taken = await db.Users.AnyAsync(row => row.UserName == member.UserName, cancellationToken).ConfigureAwait(false);
        if (taken)
        {
            throw new InvalidOperationException("username is taken");
        }

        var applicationId = await db.Users.Select(row => row.ApplicationId).FirstAsync(cancellationToken).ConfigureAwait(false);
        var now = DateTime.Now;
        var userId = Guid.NewGuid();
        var salt = MembershipPassword.CreateSalt();
        db.Users.Add(new UserRow
        {
            ApplicationId = applicationId,
            UserId = userId,
            UserName = member.UserName,
            IsAnonymous = false,
            LastActivityDate = now,
        });
        db.Memberships.Add(new MembershipRow
        {
            ApplicationId = applicationId,
            UserId = userId,
            Password = MembershipPassword.HashForStorage(member.Password, salt),
            PasswordFormat = 1,
            PasswordSalt = salt,
            Email = member.Email,
            IsApproved = true,
            IsLockedOut = false,
            CreateDate = now,
            LastLoginDate = now,
            LastPasswordChangedDate = now,
            LastLockoutDate = Never,
            FailedPasswordAttemptWindowStart = Never,
            FailedPasswordAnswerAttemptWindowsStart = Never,
        });
        db.Profiles.Add(new ProfileRow
        {
            UserName = member.UserName,
            FirstName = member.FirstName,
            LastName = member.LastName,
            DisplayName = member.DisplayName,
            IssuesPageSize = 10,
            PreferredLocale = "",
            LastUpdate = now,
            ReceiveEmailNotifications = true,
        });
        await db.SaveChangesAsync(cancellationToken).ConfigureAwait(false);
    }

    public async Task<ProjectChoice?> FirstOpenProjectAsync(CancellationToken cancellationToken)
    {
        await using var db = New();
        var projects = await OpenProjectsAsync(db, cancellationToken).ConfigureAwait(false);
        return projects.Count == 0 ? null : projects[0];
    }

    public async Task<CreatePageData?> ReadCreatePageAsync(int projectId, CancellationToken cancellationToken)
    {
        await using var db = New();
        var project = await db.Projects.SingleOrDefaultAsync(row => row.ProjectId == projectId, cancellationToken).ConfigureAwait(false);
        if (project is null)
        {
            return null;
        }

        return new CreatePageData(
            new ProjectChoice(project.ProjectId, project.ProjectName, project.ProjectCode),
            await StatusesAsync(db, projectId, cancellationToken).ConfigureAwait(false),
            await ResolutionsAsync(db, projectId, cancellationToken).ConfigureAwait(false),
            await PrioritiesAsync(db, projectId, cancellationToken).ConfigureAwait(false),
            await TypesAsync(db, projectId, cancellationToken).ConfigureAwait(false));
    }

    public async Task<DetailPageData?> ReadDetailAsync(int issueId, CancellationToken cancellationToken)
    {
        await using var db = New();
        var issue = await db.IssueViews.SingleOrDefaultAsync(row => row.IssueId == issueId, cancellationToken).ConfigureAwait(false);
        if (issue is null)
        {
            return null;
        }

        var votes = await db.Votes.CountAsync(row => row.IssueId == issueId, cancellationToken).ConfigureAwait(false);
        return new DetailPageData(
            issue.IssueId,
            issue.ProjectId,
            issue.ProjectCode ?? "",
            issue.IssueTitle ?? "",
            issue.CreatorDisplayName ?? "",
            issue.DateCreated,
            issue.IssueStatusId,
            issue.IssueResolutionId,
            votes,
            await StatusesAsync(db, issue.ProjectId, cancellationToken).ConfigureAwait(false),
            await ResolutionsAsync(db, issue.ProjectId, cancellationToken).ConfigureAwait(false));
    }

    public async Task<string?> PreferredLocaleAsync(string userName, CancellationToken cancellationToken)
    {
        await using var db = New();
        var profile = await db.Profiles.SingleOrDefaultAsync(row => row.UserName == userName, cancellationToken).ConfigureAwait(false);
        return profile?.PreferredLocale;
    }

    private IssueDbContext New() => new(_connectionString);

    private static async Task<SavedIssue> ReadSavedAsync(IssueDbContext db, int issueId, CancellationToken cancellationToken)
    {
        var issue = await db.IssueViews.SingleAsync(row => row.IssueId == issueId, cancellationToken).ConfigureAwait(false);
        var votes = await db.Votes.CountAsync(row => row.IssueId == issueId, cancellationToken).ConfigureAwait(false);
        var projectIds = db.ProjectNotifications.Where(row => row.ProjectId == issue.ProjectId).Select(row => row.UserId);
        var issueIds = db.IssueNotifications.Where(row => row.IssueId == issueId).Select(row => row.UserId);
        var userIds = projectIds.Union(issueIds);
        var people = await (
            from user in db.Users
            join membership in db.Memberships on user.UserId equals membership.UserId
            where userIds.Contains(user.UserId)
            join profile in db.Profiles on user.UserName equals profile.UserName into profiles
            from profile in profiles.DefaultIfEmpty()
            select new Subscriber(
                user.UserName,
                membership.Email ?? "",
                membership.IsApproved,
                profile != null && profile.ReceiveEmailNotifications,
                profile == null ? null : profile.PreferredLocale))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
        return new SavedIssue(
            issue.IssueId,
            issue.ProjectCode ?? "",
            issue.ProjectName ?? "",
            issue.DateCreated,
            issue.CreatorDisplayName ?? "",
            issue.MilestoneName ?? "Unassigned",
            issue.CategoryName ?? "Unassigned",
            issue.PriorityName ?? "Unassigned",
            issue.IssueTypeName ?? "Unassigned",
            votes,
            people);
    }

    private static async Task<Guid?> UserIdOrNullAsync(IssueDbContext db, string? userName, CancellationToken cancellationToken)
    {
        if (string.IsNullOrEmpty(userName))
        {
            return null;
        }

        var user = await db.Users.SingleOrDefaultAsync(row => row.UserName == userName, cancellationToken).ConfigureAwait(false);
        return user?.UserId;
    }

    private static async Task<ProfileRow> RequireProfileAsync(IssueDbContext db, string userName, CancellationToken cancellationToken)
    {
        return await db.Profiles.SingleAsync(row => row.UserName == userName, cancellationToken).ConfigureAwait(false);
    }

    private static async Task<IReadOnlyList<ProjectChoice>> OpenProjectsAsync(IssueDbContext db, CancellationToken cancellationToken)
    {
        return await db.Projects
            .Where(row => !row.ProjectDisabled)
            .OrderBy(row => row.ProjectId)
            .Select(row => new ProjectChoice(row.ProjectId, row.ProjectName, row.ProjectCode))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
    }

    private static async Task<IReadOnlyList<LookupChoice>> StatusesAsync(IssueDbContext db, int projectId, CancellationToken cancellationToken)
    {
        return await db.Statuses
            .Where(row => row.ProjectId == projectId)
            .OrderBy(row => row.SortOrder)
            .Select(row => new LookupChoice(row.StatusId, row.StatusName))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
    }

    private static async Task<IReadOnlyList<LookupChoice>> ResolutionsAsync(IssueDbContext db, int projectId, CancellationToken cancellationToken)
    {
        return await db.Resolutions
            .Where(row => row.ProjectId == projectId)
            .OrderBy(row => row.SortOrder)
            .Select(row => new LookupChoice(row.ResolutionId, row.ResolutionName))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
    }

    private static async Task<IReadOnlyList<LookupChoice>> PrioritiesAsync(IssueDbContext db, int projectId, CancellationToken cancellationToken)
    {
        return await db.Priorities
            .Where(row => row.ProjectId == projectId)
            .OrderBy(row => row.SortOrder)
            .Select(row => new LookupChoice(row.PriorityId, row.PriorityName))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
    }

    private static async Task<IReadOnlyList<LookupChoice>> TypesAsync(IssueDbContext db, int projectId, CancellationToken cancellationToken)
    {
        return await db.IssueTypes
            .Where(row => row.ProjectId == projectId)
            .OrderBy(row => row.SortOrder)
            .Select(row => new LookupChoice(row.IssueTypeId, row.IssueTypeName))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
    }

    private static int? NullIfZero(int id) => id == 0 ? null : id;

    private static string Required(Dictionary<string, string> settings, string name)
    {
        if (!settings.TryGetValue(name, out var value) || string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException("missing host setting " + name);
        }

        return value;
    }

    private static bool IsTrue(string? value)
    {
        return string.Equals(value, "True", StringComparison.OrdinalIgnoreCase)
            || string.Equals(value, "1", StringComparison.Ordinal);
    }
}
