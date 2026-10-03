namespace BugNet.Core;

public sealed record CreateIssue(
    int ProjectId,
    string Title,
    string Description,
    int StatusId,
    int ResolutionId,
    int PriorityId,
    int TypeId,
    string OwnerUserName,
    string AssigneeUserName,
    bool NotifyOwner,
    bool NotifyAssignee,
    int MilestoneId,
    int CategoryId,
    int AffectedMilestoneId,
    DateTime? DueDate,
    decimal? Estimation,
    int Progress,
    string CreatorUserName);

#pragma warning disable CA1054 // DefaultUrl is an opaque prefix. Parsing it as Uri would insert or drop a slash.
#pragma warning disable CA1056
public sealed record HostMailSettings(
    string ApplicationTitle,
    string HostEmailAddress,
    bool AllowReplyTo,
    string EmailFormat,
    string DefaultUrl,
    string ApplicationDefaultLanguage);
#pragma warning restore CA1056
#pragma warning restore CA1054

public sealed record Subscriber(
    string UserName,
    string Email,
    bool Approved,
    bool ReceiveEmailNotifications,
    string? PreferredLocale);

public sealed record SavedIssue(
    int Id,
    string ProjectCode,
    string ProjectName,
    DateTime DateCreated,
    string CreatorDisplayName,
    string MilestoneName,
    string CategoryName,
    string PriorityName,
    string TypeName,
    int CreatorVoteCount,
    IReadOnlyList<Subscriber> Subscribers);

public sealed record NotificationCopy(string Address, string Culture, string Subject, string Body);

public sealed record AddNotification(
    string FromDisplayName,
    string FromAddress,
    bool IsBodyHtml,
    IReadOnlyList<NotificationCopy> Copies);

public sealed record CreatedIssue(
    int Id,
    string IssueKey,
    DateTime DateCreated,
    int CreatorVoteCount,
    AddNotification Notification,
    StartedSend Send);

public interface IIssueStore
{
    Task<SavedIssue> SaveAsync(
        CreateIssue command,
        IReadOnlyList<string> notificationUserNames,
        CancellationToken cancellationToken);
}

public interface IAddSender
{
    StartedSend Start(AddNotification notification);
}

public sealed class StartedSend
{
    public StartedSend(Task completion)
    {
        ArgumentNullException.ThrowIfNull(completion);
        Completion = completion;
    }

    public Task Completion { get; }
}
