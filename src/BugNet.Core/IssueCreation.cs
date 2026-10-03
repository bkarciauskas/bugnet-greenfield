namespace BugNet.Core;

public static class IssueCreation
{
    public static string IssueKey(string projectCode, int id) =>
        string.Concat(projectCode, "-", id.ToString(System.Globalization.CultureInfo.InvariantCulture));

    public static IReadOnlyList<string> NotificationUserNames(CreateIssue command)
    {
        ArgumentNullException.ThrowIfNull(command);
        var names = new List<string>();
        if (command.NotifyOwner && !string.IsNullOrEmpty(command.OwnerUserName))
        {
            names.Add(command.OwnerUserName);
        }

        if (command.NotifyAssignee
            && !string.IsNullOrEmpty(command.AssigneeUserName)
            && !names.Contains(command.AssigneeUserName, StringComparer.OrdinalIgnoreCase))
        {
            names.Add(command.AssigneeUserName);
        }

        return names;
    }

    public static async Task<CreatedIssue> CreateAsync(
        CreateIssue command,
        IIssueStore store,
        HostMailSettings settings,
        IAddSender sender,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(settings);
        ArgumentNullException.ThrowIfNull(sender);

        var names = NotificationUserNames(command);
        var saved = await store.SaveAsync(command, names, cancellationToken).ConfigureAwait(false);
        var notification = AddNotificationText.Build(command, saved, settings);
        var send = sender.Start(notification);
        return new CreatedIssue(
            saved.Id,
            IssueKey(saved.ProjectCode, saved.Id),
            saved.DateCreated,
            saved.CreatorVoteCount,
            notification,
            send);
    }
}
