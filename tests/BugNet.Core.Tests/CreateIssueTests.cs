using BugNet.Core;
using Xunit;

namespace BugNet.Core.Tests;

public sealed class CreateIssueTests
{
    private static readonly DateTime Created = new(2026, 10, 2, 16, 5, 0);

    [Fact]
    public async Task IssueKeyIsProjectCodeHyphenAndId()
    {
        var result = await CreateAsync(Sample());

        Assert.Equal("BN-2", result.IssueKey);
        Assert.Equal(2, result.Id);
        Assert.Equal(Created, result.DateCreated);
        Assert.Equal(1, result.CreatorVoteCount);
    }

    [Fact]
    public async Task EmptyOwnerAndAssigneeAddNoNotificationRow()
    {
        var command = Sample() with
        {
            OwnerUserName = "",
            AssigneeUserName = "",
            NotifyOwner = true,
            NotifyAssignee = true,
        };
        var store = new MemoryStore(Snapshot());

        var result = await IssueCreation.CreateAsync(command, store, Settings(), new HoldingSender(store), CancellationToken.None);

        Assert.Empty(IssueCreation.NotificationUserNames(command));
        Assert.Empty(store.Names);
        Assert.Equal("admin@example.com", Assert.Single(result.Notification.Copies).Address);
    }

    [Fact]
    public async Task CreatorVoteExistsBeforeTheNotificationIsBuilt()
    {
        var store = new MemoryStore(Snapshot());
        var sender = new HoldingSender(store);

        var result = await IssueCreation.CreateAsync(Sample(), store, Settings(), sender, CancellationToken.None);

        Assert.True(store.Saved);
        Assert.Equal(1, result.CreatorVoteCount);
        Assert.NotNull(sender.Notification);
        Assert.False(result.Send.Completion.IsCompleted);
        sender.Release();
    }

    [Fact]
    public async Task FailedVoteDoesNotStartTheSend()
    {
        var sender = new HoldingSender(new MemoryStore(Snapshot()));

        await Assert.ThrowsAsync<InvalidOperationException>(() =>
            IssueCreation.CreateAsync(Sample(), new ThrowingStore(), Settings(), sender, CancellationToken.None));

        Assert.False(sender.Started);
    }

    [Fact]
    public async Task SubjectUsesIssueAddedSubjectAndNamesTheIssue()
    {
        var saved = Snapshot() with
        {
            Subscribers =
            [
                Person("de@example.com", "de-DE"),
                Person("es@example.com", "es-ES"),
                Person("fr@example.com", "fr-CA"),
                Person("it@example.com", "it-IT"),
                Person("nl@example.com", "nl-NL"),
                Person("ro@example.com", "ro-RO"),
                Person("ru@example.com", "ru-RU"),
                Person("zh@example.com", "zh-CN"),
                Person("en@example.com", "en-US"),
            ],
        };

        var result = await CreateAsync(Sample(), saved);
        var subjects = result.Notification.Copies.ToDictionary(copy => copy.Address, copy => copy.Subject);

        Assert.Equal("Aufgabe BN-2 wurde zu einem von Ihnen überwachten Projekt hinzugefügt.", subjects["de@example.com"]);
        Assert.Equal("El caso BN-2 se ha añadido a un proyecto que está monitorizando.", subjects["es@example.com"]);
        Assert.Equal("Anomalie BN-2 a été ajoutée à un projet que vous surveillez.", subjects["fr@example.com"]);
        Assert.Equal("La segnalazione BN-2 è stata aggiunta al progetto che stai osservando.", subjects["it@example.com"]);
        Assert.Equal("Punt BN-2 is toegevoegd aan een project wat u volgt.", subjects["nl@example.com"]);
        Assert.Equal("Problema BN-2 a fost adaugata la proiectul pe care-l monitorizati.", subjects["ro@example.com"]);
        Assert.Equal("Задание BN-2 было добавлено в наблюдаемый Вами проект.", subjects["ru@example.com"]);
        Assert.Equal("你关注的项目添加了一个新问题 BN-2", subjects["zh@example.com"]);
        Assert.Equal("Issue BN-2 has been added to a project you are monitoring.", subjects["en@example.com"]);
        Assert.DoesNotContain("{1}", subjects["en@example.com"], StringComparison.Ordinal);
    }

    [Fact]
    public void UnknownCultureHasNoSubject()
    {
        var error = Assert.Throws<InvalidOperationException>(() => AddNotificationText.Subject("xx-XX", "BN-2"));

        Assert.Equal("no IssueAddedSubject for culture xx-XX", error.Message);
    }

    [Fact]
    public async Task MissingMilestoneAndCategoryRenderAsUnassigned()
    {
        var result = await CreateAsync(Sample());
        var body = Assert.Single(result.Notification.Copies).Body;

        Assert.Equal(2, Count(body, "Unassigned"));
        Assert.Contains("Normal", body, StringComparison.Ordinal);
        Assert.Contains("Bug", body, StringComparison.Ordinal);
    }

    [Fact]
    public async Task HtmlBodyHasTheEightFieldsAndOmitsStatusAndResolution()
    {
        var result = await CreateAsync(Sample());
        var copy = Assert.Single(result.Notification.Copies);

        Assert.True(result.Notification.IsBodyHtml);
        Assert.Contains("The following issue has been added to a project that you are monitoring.", copy.Body, StringComparison.Ordinal);
        Assert.DoesNotContain("The following issue has been updated by", copy.Body, StringComparison.Ordinal);
        var cursor = 0;
        foreach (var label in new[]
        {
            "<b>Title:</b>",
            "<b>Project:</b>",
            "<b>Created By:</b>",
            "<b>Milestone:</b>",
            "<b>Category:</b>",
            "<b>Priority:</b>",
            "<b>Type:</b>",
            "<b>Description:</b>",
        })
        {
            var at = copy.Body.IndexOf(label, cursor, StringComparison.Ordinal);
            Assert.True(at >= cursor, label);
            cursor = at + label.Length;
        }

        Assert.Contains("Posted title", copy.Body, StringComparison.Ordinal);
        Assert.Contains("Slice recording", copy.Body, StringComparison.Ordinal);
        Assert.Contains("Administrator", copy.Body, StringComparison.Ordinal);
        Assert.Contains("Posted description", copy.Body, StringComparison.Ordinal);
        Assert.DoesNotContain("Status:", copy.Body, StringComparison.Ordinal);
        Assert.DoesNotContain("Resolution:", copy.Body, StringComparison.Ordinal);
    }

    [Fact]
    public async Task TextBodyUsesTheTextTemplate()
    {
        var result = await CreateAsync(Sample(), Snapshot(), Settings() with { EmailFormat = "1" });
        var body = Assert.Single(result.Notification.Copies).Body;

        Assert.False(result.Notification.IsBodyHtml);
        Assert.Contains("Title: ", body, StringComparison.Ordinal);
        Assert.Contains("The following issue has been added to a project that you are monitoring.", body, StringComparison.Ordinal);
        Assert.DoesNotContain("<b>Title:</b>", body, StringComparison.Ordinal);
    }

    [Fact]
    public async Task DutchBodyUsesTheDutchLeadAndLabels()
    {
        var saved = Snapshot() with { Subscribers = [Person("nl@example.com", "nl-NL")] };

        var body = Assert.Single((await CreateAsync(Sample(), saved)).Notification.Copies).Body;

        Assert.Contains("Het volgende punt is toegevoegd aan een project dat u volgt.", body, StringComparison.Ordinal);
        Assert.Contains("<b>Titel:</b>", body, StringComparison.Ordinal);
        Assert.DoesNotContain("Het volgende punt is bijgewerkt door", body, StringComparison.Ordinal);
    }

    [Fact]
    public async Task LinksAreDefaultUrlPlusTheLegacyPaths()
    {
        var body = Assert.Single((await CreateAsync(Sample())).Notification.Copies).Body;

        Assert.Contains("http://localhost/BugNet/Issues/IssueDetail.aspx?id=2", body, StringComparison.Ordinal);
        Assert.Contains("http://localhost/BugNet/Account/UserProfile.aspx", body, StringComparison.Ordinal);
        Assert.DoesNotContain("http://localhost/BugNet//Issues", body, StringComparison.Ordinal);
    }

    [Fact]
    public async Task FromUsesTheHostTitleAndAddress()
    {
        var plain = await CreateAsync(Sample());
        Assert.Equal("BugNET Issue Tracker", plain.Notification.FromDisplayName);
        Assert.Equal("noreply@example.com", plain.Notification.FromAddress);

        var tagged = await CreateAsync(Sample(), Snapshot(), Settings() with { AllowReplyTo = true });
        Assert.Equal("noreply+iid-2@example.com", tagged.Notification.FromAddress);
    }

    [Fact]
    public async Task CreatorStaysOnTheRecipientList()
    {
        var saved = Snapshot() with
        {
            Subscribers =
            [
                Person("admin@example.com", "en-US", userName: "Admin"),
                Person("other@example.com", ""),
            ],
        };

        var addresses = (await CreateAsync(Sample(), saved)).Notification.Copies.Select(copy => copy.Address).ToArray();

        Assert.Equal(["admin@example.com", "other@example.com"], addresses);
    }

    [Fact]
    public async Task SendIsStartedAndStillIncompleteWhenCreateReturns()
    {
        var store = new MemoryStore(Snapshot());
        var sender = new HoldingSender(store);

        var result = await IssueCreation.CreateAsync(Sample(), store, Settings(), sender, CancellationToken.None);

        Assert.True(sender.Started);
        Assert.False(result.Send.Completion.IsCompleted);
        sender.Release();
        await result.Send.Completion;
        Assert.True(result.Send.Completion.IsCompleted);
    }

    [Fact]
    public void CreatedOnUsesTheDraftGeneralShortPattern()
    {
        Assert.Equal("10/2/2026 4:05 PM", CreatedOnText.Format(Created, "en-US"));
        Assert.Equal("10/2/2026 4:05 PM", CreatedOnText.Format(Created, null));
        Assert.Equal("10/2/2026 4:05 PM", CreatedOnText.Format(Created, ""));
        Assert.Equal("10/2/2026 9:05 AM", CreatedOnText.Format(new DateTime(2026, 10, 2, 9, 5, 0), "en-US"));
        Assert.Equal("02.10.2026 16:05", CreatedOnText.Format(Created, "de-DE"));
        Assert.Equal("02/10/2026 16:05", CreatedOnText.Format(Created, "es-ES"));
        Assert.Equal("2026-10-02 16:05", CreatedOnText.Format(Created, "fr-CA"));
        Assert.Equal("02/10/2026 16:05", CreatedOnText.Format(Created, "it-IT"));
        Assert.Equal("2-10-2026 16:05", CreatedOnText.Format(Created, "nl-NL"));
        Assert.Equal("02.10.2026 16:05", CreatedOnText.Format(Created, "ro-RO"));
        Assert.Equal("02.10.2026 16:05", CreatedOnText.Format(Created, "ru-RU"));
        Assert.Equal("2026/10/2 16:05", CreatedOnText.Format(Created, "zh-CN"));
    }

    private static async Task<CreatedIssue> CreateAsync(CreateIssue command)
    {
        return await CreateAsync(command, Snapshot());
    }

    private static async Task<CreatedIssue> CreateAsync(CreateIssue command, SavedIssue saved, HostMailSettings? settings = null)
    {
        var store = new MemoryStore(saved);
        var sender = new HoldingSender(store);
        var result = await IssueCreation.CreateAsync(command, store, settings ?? Settings(), sender, CancellationToken.None);
        sender.Release();
        return result;
    }

    private static CreateIssue Sample() => new(
        ProjectId: 1,
        Title: "Posted title",
        Description: "Posted description",
        StatusId: 1,
        ResolutionId: 1,
        PriorityId: 1,
        TypeId: 1,
        OwnerUserName: "",
        AssigneeUserName: "",
        NotifyOwner: true,
        NotifyAssignee: true,
        MilestoneId: 0,
        CategoryId: 0,
        AffectedMilestoneId: 0,
        DueDate: null,
        Estimation: null,
        Progress: 0,
        CreatorUserName: "Admin");

    private static SavedIssue Snapshot() => new(
        Id: 2,
        ProjectCode: "BN",
        ProjectName: "Slice recording",
        DateCreated: Created,
        CreatorDisplayName: "Administrator",
        MilestoneName: "Unassigned",
        CategoryName: "Unassigned",
        PriorityName: "Normal",
        TypeName: "Bug",
        CreatorVoteCount: 1,
        Subscribers: [Person("admin@example.com", "en-US")]);

    private static HostMailSettings Settings() => new(
        ApplicationTitle: "BugNET Issue Tracker",
        HostEmailAddress: "noreply@example.com",
        AllowReplyTo: false,
        EmailFormat: "2",
        DefaultUrl: "http://localhost/BugNet/",
        ApplicationDefaultLanguage: "en-US");

    private static Subscriber Person(string email, string? locale, string userName = "Admin") => new(
        UserName: userName,
        Email: email,
        Approved: true,
        ReceiveEmailNotifications: true,
        PreferredLocale: locale);

    private static int Count(string text, string value)
    {
        var count = 0;
        var cursor = 0;
        while (true)
        {
            var at = text.IndexOf(value, cursor, StringComparison.Ordinal);
            if (at < 0)
            {
                return count;
            }

            count++;
            cursor = at + value.Length;
        }
    }

    private sealed class MemoryStore : IIssueStore
    {
        private readonly SavedIssue _snapshot;

        public MemoryStore(SavedIssue snapshot) => _snapshot = snapshot;

        public bool Saved { get; private set; }

        public IReadOnlyList<string> Names { get; private set; } = [];

        public Task<SavedIssue> SaveAsync(
            CreateIssue command,
            IReadOnlyList<string> notificationUserNames,
            CancellationToken cancellationToken)
        {
            Saved = true;
            Names = notificationUserNames;
            return Task.FromResult(_snapshot);
        }
    }

    private sealed class ThrowingStore : IIssueStore
    {
        public Task<SavedIssue> SaveAsync(
            CreateIssue command,
            IReadOnlyList<string> notificationUserNames,
            CancellationToken cancellationToken) =>
            throw new InvalidOperationException("vote failed");
    }

    private sealed class HoldingSender : IAddSender
    {
        private readonly MemoryStore? _store;
        private readonly TaskCompletionSource _gate = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public HoldingSender(MemoryStore? store) => _store = store;

        public bool Started { get; private set; }

        public AddNotification? Notification { get; private set; }

        public StartedSend Start(AddNotification notification)
        {
            if (_store is not null && !_store.Saved)
            {
                throw new InvalidOperationException("notification before vote");
            }

            Started = true;
            Notification = notification;
            return new StartedSend(_gate.Task);
        }

        public void Release() => _gate.TrySetResult();
    }
}
