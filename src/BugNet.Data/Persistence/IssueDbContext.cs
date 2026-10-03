using Microsoft.EntityFrameworkCore;

namespace BugNet.Data.Persistence;

internal sealed class IssueDbContext : DbContext
{
    private readonly string _connectionString;

    public IssueDbContext(string connectionString)
    {
        _connectionString = connectionString;
    }

    public DbSet<UserRow> Users => Set<UserRow>();

    public DbSet<MembershipRow> Memberships => Set<MembershipRow>();

    public DbSet<ProfileRow> Profiles => Set<ProfileRow>();

    public DbSet<ProjectRow> Projects => Set<ProjectRow>();

    public DbSet<IssueRow> Issues => Set<IssueRow>();

    public DbSet<VoteRow> Votes => Set<VoteRow>();

    public DbSet<IssueNotificationRow> IssueNotifications => Set<IssueNotificationRow>();

    public DbSet<ProjectNotificationRow> ProjectNotifications => Set<ProjectNotificationRow>();

    public DbSet<HostSettingRow> HostSettings => Set<HostSettingRow>();

    public DbSet<StatusRow> Statuses => Set<StatusRow>();

    public DbSet<ResolutionRow> Resolutions => Set<ResolutionRow>();

    public DbSet<PriorityRow> Priorities => Set<PriorityRow>();

    public DbSet<IssueTypeRow> IssueTypes => Set<IssueTypeRow>();

    public DbSet<IssueViewRow> IssueViews => Set<IssueViewRow>();

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        optionsBuilder.UseSqlServer(_connectionString);
    }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<UserRow>(entity =>
        {
            entity.ToTable("Users");
            entity.HasKey(row => row.UserId);
        });
        modelBuilder.Entity<MembershipRow>(entity =>
        {
            entity.ToTable("Memberships");
            entity.HasKey(row => row.UserId);
        });
        modelBuilder.Entity<ProfileRow>(entity =>
        {
            entity.ToTable("BugNet_UserProfiles");
            entity.HasKey(row => row.UserName);
            entity.Property(row => row.LastUpdate).HasColumnType("datetime");
        });
        modelBuilder.Entity<ProjectRow>(entity =>
        {
            entity.ToTable("BugNet_Projects");
            entity.HasKey(row => row.ProjectId);
        });
        modelBuilder.Entity<IssueRow>(entity =>
        {
            entity.ToTable("BugNet_Issues");
            entity.HasKey(row => row.IssueId);
            entity.Property(row => row.IssueId).ValueGeneratedOnAdd();
            entity.Property(row => row.IssueEstimation).HasPrecision(5, 2);
            entity.Property(row => row.DateCreated).HasColumnType("datetime").HasDefaultValueSql("getdate()").ValueGeneratedOnAdd();
            entity.Property(row => row.LastUpdate).HasColumnType("datetime").HasDefaultValueSql("getdate()").ValueGeneratedOnAdd();
            entity.Property(row => row.IssueDueDate).HasColumnType("datetime");
        });
        modelBuilder.Entity<VoteRow>(entity =>
        {
            entity.ToTable("BugNet_IssueVotes");
            entity.HasKey(row => row.IssueVoteId);
            entity.Property(row => row.IssueVoteId).ValueGeneratedOnAdd();
            entity.Property(row => row.DateCreated).HasColumnType("datetime");
        });
        modelBuilder.Entity<IssueNotificationRow>(entity =>
        {
            entity.ToTable("BugNet_IssueNotifications");
            entity.HasKey(row => row.IssueNotificationId);
            entity.Property(row => row.IssueNotificationId).ValueGeneratedOnAdd();
        });
        modelBuilder.Entity<ProjectNotificationRow>(entity =>
        {
            entity.ToTable("BugNet_ProjectNotifications");
            entity.HasKey(row => row.ProjectNotificationId);
            entity.Property(row => row.ProjectNotificationId).ValueGeneratedOnAdd();
        });
        modelBuilder.Entity<HostSettingRow>(entity =>
        {
            entity.ToTable("BugNet_HostSettings");
            entity.HasKey(row => row.SettingName);
        });
        modelBuilder.Entity<StatusRow>(entity =>
        {
            entity.ToTable("BugNet_ProjectStatus");
            entity.HasKey(row => row.StatusId);
        });
        modelBuilder.Entity<ResolutionRow>(entity =>
        {
            entity.ToTable("BugNet_ProjectResolutions");
            entity.HasKey(row => row.ResolutionId);
        });
        modelBuilder.Entity<PriorityRow>(entity =>
        {
            entity.ToTable("BugNet_ProjectPriorities");
            entity.HasKey(row => row.PriorityId);
        });
        modelBuilder.Entity<IssueTypeRow>(entity =>
        {
            entity.ToTable("BugNet_ProjectIssueTypes");
            entity.HasKey(row => row.IssueTypeId);
        });
        modelBuilder.Entity<IssueViewRow>(entity =>
        {
            entity.HasNoKey();
            entity.ToView("BugNet_IssuesView");
            entity.Property(row => row.DateCreated).HasColumnType("datetime");
        });
    }
}

internal sealed class UserRow
{
    public Guid ApplicationId { get; set; }

    public Guid UserId { get; set; }

    public string UserName { get; set; } = "";

    public bool IsAnonymous { get; set; }

    public DateTime LastActivityDate { get; set; }
}

internal sealed class MembershipRow
{
    public Guid ApplicationId { get; set; }

    public Guid UserId { get; set; }

    public string Password { get; set; } = "";

    public int PasswordFormat { get; set; }

    public string PasswordSalt { get; set; } = "";

    public string? Email { get; set; }

    public string? PasswordQuestion { get; set; }

    public string? PasswordAnswer { get; set; }

    public bool IsApproved { get; set; }

    public bool IsLockedOut { get; set; }

    public DateTime CreateDate { get; set; }

    public DateTime LastLoginDate { get; set; }

    public DateTime LastPasswordChangedDate { get; set; }

    public DateTime LastLockoutDate { get; set; }

    public int FailedPasswordAttemptCount { get; set; }

    public DateTime FailedPasswordAttemptWindowStart { get; set; }

    public int FailedPasswordAnswerAttemptCount { get; set; }

    public DateTime FailedPasswordAnswerAttemptWindowsStart { get; set; }

    public string? Comment { get; set; }
}

internal sealed class ProfileRow
{
    public string UserName { get; set; } = "";

    public string? FirstName { get; set; }

    public string? LastName { get; set; }

    public string? DisplayName { get; set; }

    public int? IssuesPageSize { get; set; }

    public string? PreferredLocale { get; set; }

    public DateTime LastUpdate { get; set; }

    public string? SelectedIssueColumns { get; set; }

    public bool ReceiveEmailNotifications { get; set; }
}

internal sealed class ProjectRow
{
    public int ProjectId { get; set; }

    public string ProjectName { get; set; } = "";

    public string ProjectCode { get; set; } = "";

    public bool ProjectDisabled { get; set; }
}

internal sealed class IssueRow
{
    public int IssueId { get; set; }

    public string IssueTitle { get; set; } = "";

    public string IssueDescription { get; set; } = "";

    public int? IssueStatusId { get; set; }

    public int? IssuePriorityId { get; set; }

    public int? IssueTypeId { get; set; }

    public int? IssueCategoryId { get; set; }

    public int ProjectId { get; set; }

    public int? IssueAffectedMilestoneId { get; set; }

    public int? IssueResolutionId { get; set; }

    public Guid IssueCreatorUserId { get; set; }

    public Guid? IssueAssignedUserId { get; set; }

    public Guid? IssueOwnerUserId { get; set; }

    public DateTime? IssueDueDate { get; set; }

    public int? IssueMilestoneId { get; set; }

    public int IssueVisibility { get; set; }

    public decimal IssueEstimation { get; set; }

    public int IssueProgress { get; set; }

    public DateTime DateCreated { get; set; }

    public DateTime LastUpdate { get; set; }

    public Guid LastUpdateUserId { get; set; }

    public bool Disabled { get; set; }
}

internal sealed class VoteRow
{
    public int IssueVoteId { get; set; }

    public int IssueId { get; set; }

    public Guid UserId { get; set; }

    public DateTime DateCreated { get; set; }
}

internal sealed class IssueNotificationRow
{
    public int IssueNotificationId { get; set; }

    public int IssueId { get; set; }

    public Guid UserId { get; set; }
}

internal sealed class ProjectNotificationRow
{
    public int ProjectNotificationId { get; set; }

    public int ProjectId { get; set; }

    public Guid UserId { get; set; }
}

internal sealed class HostSettingRow
{
    public string SettingName { get; set; } = "";

    public string? SettingValue { get; set; }
}

internal sealed class StatusRow
{
    public int StatusId { get; set; }

    public int ProjectId { get; set; }

    public string StatusName { get; set; } = "";

    public int SortOrder { get; set; }
}

internal sealed class ResolutionRow
{
    public int ResolutionId { get; set; }

    public int ProjectId { get; set; }

    public string ResolutionName { get; set; } = "";

    public int SortOrder { get; set; }
}

internal sealed class PriorityRow
{
    public int PriorityId { get; set; }

    public int ProjectId { get; set; }

    public string PriorityName { get; set; } = "";

    public int SortOrder { get; set; }
}

internal sealed class IssueTypeRow
{
    public int IssueTypeId { get; set; }

    public int ProjectId { get; set; }

    public string IssueTypeName { get; set; } = "";

    public int SortOrder { get; set; }
}

internal sealed class IssueViewRow
{
    public int IssueId { get; set; }

    public int ProjectId { get; set; }

    public string? ProjectCode { get; set; }

    public string? ProjectName { get; set; }

    public string? IssueTitle { get; set; }

    public DateTime DateCreated { get; set; }

    public string? CreatorDisplayName { get; set; }

    public string? MilestoneName { get; set; }

    public string? CategoryName { get; set; }

    public string? PriorityName { get; set; }

    public string? IssueTypeName { get; set; }

    public int IssueVotes { get; set; }

    public int? IssueStatusId { get; set; }

    public int? IssueResolutionId { get; set; }

    public Guid? IssueOwnerUserId { get; set; }

    public Guid? IssueAssignedUserId { get; set; }
}
