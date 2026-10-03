namespace BugNet.Data;

public sealed record MemberAccount(string UserName, string Email, bool Approved);

public sealed record NewMember(
    string UserName,
    string Password,
    string Email,
    string FirstName,
    string LastName,
    string DisplayName);

public sealed record ProjectChoice(int Id, string Name, string Code);

public sealed record LookupChoice(int Id, string Name);

public sealed record ProfileEditor(
    string UserName,
    string DisplayName,
    string Email,
    string PreferredLocale,
    int IssuesPageSize,
    bool ReceiveEmailNotifications,
    IReadOnlyList<ProjectChoice> SubscribedProjects,
    IReadOnlyList<ProjectChoice> OtherProjects);

public sealed record CreatePageData(
    ProjectChoice Project,
    IReadOnlyList<LookupChoice> Statuses,
    IReadOnlyList<LookupChoice> Resolutions,
    IReadOnlyList<LookupChoice> Priorities,
    IReadOnlyList<LookupChoice> Types);

public sealed record DetailPageData(
    int Id,
    int ProjectId,
    string ProjectCode,
    string Title,
    string CreatorDisplayName,
    DateTime DateCreated,
    int? StatusId,
    int? ResolutionId,
    int VoteCount,
    IReadOnlyList<LookupChoice> Statuses,
    IReadOnlyList<LookupChoice> Resolutions);
